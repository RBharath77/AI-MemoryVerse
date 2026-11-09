import time

import pytest
from httpx import AsyncClient

from app.core.security import (
    generate_totp_code,
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
)


@pytest.mark.asyncio
async def test_totp_rfc6238_pure_functions():
    """Verify RFC 6238 standard TOTP secret generation, URI construction, and code validation."""
    secret = generate_totp_secret()
    assert isinstance(secret, str)
    assert len(secret) >= 16

    uri = get_totp_uri(secret, "alice@example.com")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={secret}" in uri
    assert "issuer=AI-MemoryVerse" in uri

    # Verify code generation at current time step
    code = generate_totp_code(secret)
    assert len(code) == 6
    assert code.isdigit()

    # Verify validity within window
    assert verify_totp_code(secret, code, window=1) is True

    # Current step +/- 1 should be accepted with window=1
    current_step = int(time.time() // 30)
    prev_code = generate_totp_code(secret, time_step=current_step - 1)
    next_code = generate_totp_code(secret, time_step=current_step + 1)
    assert verify_totp_code(secret, prev_code, window=1) is True
    assert verify_totp_code(secret, next_code, window=1) is True

    # Beyond window (offset = 5) should fail
    far_code = generate_totp_code(secret, time_step=current_step + 5)
    assert verify_totp_code(secret, far_code, window=1) is False

    # Invalid codes
    assert verify_totp_code(secret, "00000", window=1) is False
    assert verify_totp_code(secret, "abcdef", window=1) is False
    assert verify_totp_code(secret, "", window=1) is False


@pytest.mark.asyncio
async def test_mfa_setup_and_enable(client: AsyncClient):
    """Verify MFA setup and activation endpoints."""
    # Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mfa_setup_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "MFA Setup User",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup MFA
    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup_res.status_code == 200
    setup_data = setup_res.json()["data"]
    secret = setup_data["secret"]
    assert "totp_uri" in setup_data
    assert secret

    # Attempt to enable with wrong code
    bad_enable = await client.post(
        "/api/v1/auth/mfa/enable", json={"code": "000000"}, headers=headers
    )
    assert bad_enable.status_code == 400

    # Enable with correct code
    valid_code = generate_totp_code(secret)
    enable_res = await client.post(
        "/api/v1/auth/mfa/enable", json={"code": valid_code}, headers=headers
    )
    assert enable_res.status_code == 200
    assert enable_res.json()["success"] is True

    # Check /me reports is_mfa_enabled == True
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["is_mfa_enabled"] is True


@pytest.mark.asyncio
async def test_login_mfa_challenge_and_authenticate(client: AsyncClient):
    """Verify 2FA login challenge enforcement and token issuance."""
    # Register and setup MFA
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mfa_challenger@example.com",
            "password": "SecurePassword123!",
            "full_name": "MFA Challenger",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_res.json()["data"]["secret"]
    valid_code = generate_totp_code(secret)
    await client.post("/api/v1/auth/mfa/enable", json={"code": valid_code}, headers=headers)

    # Now attempt login with credentials
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "mfa_challenger@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()["data"]
    assert login_data["mfa_required"] is True
    assert "mfa_token" in login_data
    assert "tokens" not in login_data

    mfa_token = login_data["mfa_token"]

    # Attempt to authenticate with invalid code
    bad_auth = await client.post(
        "/api/v1/auth/mfa/authenticate",
        json={"mfa_token": mfa_token, "code": "999999"},
    )
    assert bad_auth.status_code == 401

    # Authenticate with valid TOTP code
    current_code = generate_totp_code(secret)
    auth_res = await client.post(
        "/api/v1/auth/mfa/authenticate",
        json={"mfa_token": mfa_token, "code": current_code},
    )
    assert auth_res.status_code == 200
    auth_data = auth_res.json()["data"]
    assert "tokens" in auth_data
    assert auth_data["tokens"]["access_token"]
    assert auth_data["user"]["email"] == "mfa_challenger@example.com"


@pytest.mark.asyncio
async def test_mfa_disable_and_normal_login(client: AsyncClient):
    """Verify MFA disable flow with password re-check and subsequent login behavior."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mfa_disabler@example.com",
            "password": "SecurePassword123!",
            "full_name": "MFA Disabler",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_res.json()["data"]["secret"]
    await client.post(
        "/api/v1/auth/mfa/enable",
        json={"code": generate_totp_code(secret)},
        headers=headers,
    )

    # Disable with wrong password
    bad_pw = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "WrongPassword123!", "code": generate_totp_code(secret)},
        headers=headers,
    )
    assert bad_pw.status_code == 401

    # Disable with wrong TOTP code
    bad_code = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "SecurePassword123!", "code": "000000"},
        headers=headers,
    )
    assert bad_code.status_code == 400

    # Disable with correct password and valid code
    disable_res = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "SecurePassword123!", "code": generate_totp_code(secret)},
        headers=headers,
    )
    assert disable_res.status_code == 200

    # Verify /me shows is_mfa_enabled == False
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.json()["data"]["is_mfa_enabled"] is False

    # Normal login should now return tokens directly
    normal_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "mfa_disabler@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert normal_login.status_code == 200
    assert normal_login.json()["data"]["mfa_required"] is False
    assert "tokens" in normal_login.json()["data"]


@pytest.mark.asyncio
async def test_chat_sse_streaming_response(client: AsyncClient):
    """Verify Server-Sent Events (SSE) token streaming from /chat/conversations/{id}/messages."""
    # Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "stream_chatter@example.com",
            "password": "SecurePassword123!",
            "full_name": "Stream Chatter",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Streaming Test Conversation"},
        headers=headers,
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["data"]["id"]

    # Send streaming message
    stream_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"content": "What is AI-MemoryVerse?", "stream": True},
        headers=headers,
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")

    # Parse SSE stream
    stream_body = stream_res.text
    assert "event: citations" in stream_body
    assert "event: token" in stream_body
    assert "event: done" in stream_body

    # Check database persistence
    msgs_res = await client.get(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=headers,
    )
    assert msgs_res.status_code == 200
    messages = msgs_res.json()["data"]
    assert len(messages) == 2  # user + assistant
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is AI-MemoryVerse?"
    assert messages[1]["role"] == "assistant"
    assert len(messages[1]["content"]) > 0
