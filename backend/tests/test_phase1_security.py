import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_demo_login_disabled_by_default(client: AsyncClient):
    """Phase 1: Demo backdoor must be disabled by default and return 403."""
    response = await client.post("/api/v1/auth/demo")
    assert response.status_code == 403
    assert "disabled" in str(response.json()).lower()


@pytest.mark.asyncio
async def test_mcp_unauthenticated_request_blocked(client: AsyncClient):
    """Phase 1: MCP endpoint must reject unauthenticated requests with 401."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    response = await client.post("/api/v1/mcp", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_idor_unauthorized_workspace_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Phase 1: Arbitrary X-Workspace-ID header must return 403 Forbidden if user is not a member."""
    foreign_workspace_id = str(uuid.uuid4())
    headers = {
        **auth_headers,
        "X-Workspace-ID": foreign_workspace_id,
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    response = await client.post("/api/v1/mcp", json=payload, headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert "Forbidden" in data["error"]["message"]


@pytest.mark.asyncio
async def test_admin_overview_bfla_protection(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """Phase 1: Standard user receives 403 on admin telemetry; superuser succeeds."""
    forbidden_res = await client.get("/api/v1/admin/overview", headers=auth_headers)
    assert forbidden_res.status_code == 403

    allowed_res = await client.get("/api/v1/admin/overview", headers=admin_headers)
    assert allowed_res.status_code == 200


@pytest.mark.asyncio
async def test_programmatic_api_token_authentication(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Phase 1: Programmatic tokens (mv_live_...) must authenticate through deps.py."""
    # 1. Create an API token via /api/v1/tokens
    create_res = await client.post(
        "/api/v1/tokens",
        headers=auth_headers,
        json={"name": "CLI Integration Token", "scopes": ["memories:read"]},
    )
    assert create_res.status_code == 201
    raw_token = create_res.json()["data"]["token"]
    assert raw_token.startswith("mv_live_")

    # 2. Use the programmatic token to authenticate to /api/v1/auth/me
    token_headers = {
        "Authorization": f"Bearer {raw_token}",
        "X-Workspace-ID": auth_headers["X-Workspace-ID"],
    }
    me_res = await client.get("/api/v1/auth/me", headers=token_headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "testuser@memoryverse.ai"


def test_production_secret_key_validation():
    """Verify that insecure default SECRET_KEY is rejected when APP_ENV is production."""
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="insecure-dev-secret-key-change-in-production-min-32-chars",
        )
    assert "SECRET_KEY must be a secure" in str(exc.value)

    # Valid secret in production must succeed
    valid_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="a" * 32,
    )
    assert valid_settings.SECRET_KEY == "a" * 32



def test_production_secret_key_validation():
    """Verify that insecure default SECRET_KEY is rejected when APP_ENV is production."""
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="insecure-dev-secret-key-change-in-production-min-32-chars",
        )
    assert "SECRET_KEY must be a secure" in str(exc.value)

    # Valid secret in production must succeed
    valid_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="a" * 32,
    )
    assert valid_settings.SECRET_KEY == "a" * 32

