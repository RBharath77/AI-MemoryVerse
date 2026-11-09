from __future__ import annotations

import io
from datetime import datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import database as core_db
from app.core.config import settings
from app.core.rate_limit import RateLimiter
from app.core.ssrf import validate_and_resolve_url_safe
from app.models.document import Document
from app.models.user import User


@pytest.mark.asyncio
async def test_dns_rebinding_and_ssrf_resolution_validation():
    """Verify that validate_and_resolve_url_safe validates public IPs and denies private/cloud metadata."""
    # 1. Valid public domain returns URL and public IPs
    with patch(
        "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 80))]
    ):
        safe_url, ips = validate_and_resolve_url_safe("http://example.com/data")
        assert safe_url == "http://example.com/data"
        assert "93.184.216.34" in ips

    # 2. DNS resolving to loopback or metadata triggers immediate HTTP 400 rejection
    with patch(
        "socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 80))]
    ):
        with pytest.raises(Exception) as exc:
            validate_and_resolve_url_safe("http://malicious-rebinding.com/steal")
        assert exc.value.status_code == 400
        assert "SSRF Protection" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_account_lockout_after_five_failed_logins(client: AsyncClient):
    """Verify that 5 consecutive failed login attempts locks the account and returns HTTP 429."""
    # 1. Register test user
    email = f"lockout_user_{datetime.now().timestamp()}@phase18.ai"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Lockout Test User",
            "workspace_name": "Lockout WS",
        },
    )
    assert reg.status_code == 201

    # 2. Execute 4 failed login attempts -> all return 401
    for _ in range(4):
        fail_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword123!"},
        )
        assert fail_res.status_code == 401
        assert "Incorrect email or password" in fail_res.json()["error"]["message"]

    # 3. 5th failed attempt triggers 15-minute account lockout -> returns 429
    fifth_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert fifth_res.status_code == 429
    assert "temporarily locked for 15 minutes" in fifth_res.json()["error"]["message"]

    # 4. 6th attempt with CORRECT password is still locked out -> returns 429
    locked_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert locked_res.status_code == 429
    assert "temporarily locked" in locked_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempt_counter(client: AsyncClient):
    """Verify that a successful login resets the consecutive failed attempt counter."""
    email = f"reset_counter_{datetime.now().timestamp()}@phase18.ai"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Reset Counter User",
            "workspace_name": "Reset Counter WS",
        },
    )
    assert reg.status_code == 201

    # 2 failed attempts
    for _ in range(2):
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )

    # Verify counter is 2 in DB
    async with core_db.async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        assert user.failed_login_attempts == 2

    # Successful login
    succ_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert succ_res.status_code == 200

    # Verify counter is reset to 0 in DB
    async with core_db.async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


@pytest.mark.asyncio
async def test_rate_limiter_burst_and_reset():
    """Verify RateLimiter blocks requests exceeding limits and allows reset."""
    from fastapi import HTTPException

    class DummyRequest:
        def __init__(self, ip: str):
            self.client = type("Client", (), {"host": ip})()
            self.headers = {}

    limiter = RateLimiter(times=3, seconds=5)
    mock_request = DummyRequest("192.0.2.100")

    old_setting = getattr(settings, "RATE_LIMIT_ENABLED", True)
    try:
        settings.RATE_LIMIT_ENABLED = True

        # First 3 requests succeed
        for _ in range(3):
            await limiter(mock_request)

        # 4th request within 5s raises HTTP 429
        with pytest.raises(HTTPException) as exc:
            await limiter(mock_request)
        assert exc.value.status_code == 429
        assert "Retry-After" in exc.value.headers

        # Reset clears records
        limiter.reset()
        await limiter(mock_request)  # Should succeed again without exception
    finally:
        settings.RATE_LIMIT_ENABLED = old_setting


@pytest.mark.asyncio
async def test_workspace_aggregate_storage_quota_enforcement(client: AsyncClient):
    """Verify that a workspace cannot upload documents beyond its plan tier storage quota."""
    # 1. Register owner with free tier workspace
    email = f"quota_test_{datetime.now().timestamp()}@phase18.ai"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Quota Test User",
            "workspace_name": "Quota WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Simulate existing storage utilization right below the 500MB free quota
    # Free tier quota is 500MB (524,288,000 bytes)
    async with core_db.async_session_factory() as db:
        dummy_doc = Document(
            workspace_id=ws_id,
            user_id=reg.json()["data"]["user"]["id"],
            title="Pre-existing Large File",
            filename="large_file.dat",
            file_key="dummy_key",
            file_size=520 * 1024 * 1024,  # 520 MB already used (> 500MB quota)
            mime_type="application/octet-stream",
            file_hash="dummy_hash",
        )
        db.add(dummy_doc)
        await db.commit()

    # 3. Attempt to upload another document (e.g. 10MB text file) -> Must be rejected with HTTP 402
    file_content = b"New document content " * 1000
    files = {"file": ("new_doc.txt", io.BytesIO(file_content), "text/plain")}

    res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers=headers,
    )

    assert res.status_code == 402
    assert "Workspace storage quota exceeded" in res.json()["error"]["message"]
