import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_session_revocation_on_password_reset(client: AsyncClient):
    """Phase 4: Instantaneous JWT session revocation upon password reset (Token Versioning)."""
    # 1. Register user
    reg_payload = {
        "email": "revocation_pilot@memoryverse.ai",
        "password": "InitialPassword123!",
        "full_name": "Revocation Pilot",
        "workspace_name": "Security Labs",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    old_access_token = reg_res.json()["data"]["tokens"]["access_token"]
    old_headers = {"Authorization": f"Bearer {old_access_token}"}

    # 2. Verify old token works before reset
    me_res = await client.get("/api/v1/auth/me", headers=old_headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "revocation_pilot@memoryverse.ai"

    # 3. Request password reset
    forgot_res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "revocation_pilot@memoryverse.ai"},
    )
    assert forgot_res.status_code == 200
    reset_token = forgot_res.json()["data"]["debug_token"]
    assert reset_token

    # 4. Perform password reset
    reset_res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "NewSecretPassword999!",
        },
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True

    # 5. Security Assertion: Old token must be immediately revoked
    revoked_res = await client.get("/api/v1/auth/me", headers=old_headers)
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.json()["error"]["message"].lower()

    # 6. Log in with new password -> must succeed and issue active token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "revocation_pilot@memoryverse.ai",
            "password": "NewSecretPassword999!",
        },
    )
    assert login_res.status_code == 200
    new_token = login_res.json()["data"]["tokens"]["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 7. New token must work cleanly
    new_me = await client.get("/api/v1/auth/me", headers=new_headers)
    assert new_me.status_code == 200
    assert new_me.json()["data"]["email"] == "revocation_pilot@memoryverse.ai"


@pytest.mark.asyncio
async def test_health_and_liveness_probes_nominal(client: AsyncClient):
    """Phase 4: Health, readiness, and liveness probes return 200 OK."""
    # Liveness
    live_res = await client.get("/health")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "healthy"

    # Readiness
    ready_res = await client.get("/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_waf_and_invalid_route_filtering(client: AsyncClient):
    """Phase 4: Missing routes and invalid paths return 404 cleanly."""
    res = await client.get("/api/v1/non_existent_route_probe")
    assert res.status_code == 404
