import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "email": "sarah.connor@memoryverse.ai",
        "password": "SecurePassword999!",
        "full_name": "Sarah Connor",
        "workspace_name": "Cyberdyne Research",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    data = body["data"]

    assert data["user"]["email"] == "sarah.connor@memoryverse.ai"
    assert data["user"]["full_name"] == "Sarah Connor"
    assert "tokens" in data
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert data["workspace"]["name"] == "Cyberdyne Research"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@memoryverse.ai",
        "password": "Password123!",
        "full_name": "First User",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second attempt with same email
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    body = res2.json()
    assert body["success"] is False
    assert "already exists" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_register_weak_password_validation(client: AsyncClient):
    # Case 1: Less than 8 characters
    res_short = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@memoryverse.ai", "password": "Sh0!", "full_name": "Short Pass"},
    )
    assert res_short.status_code == 422
    assert res_short.json()["success"] is False

    # Case 2: Missing uppercase
    res_no_upper = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "noupper@memoryverse.ai",
            "password": "password123!",
            "full_name": "No Upper",
        },
    )
    assert res_no_upper.status_code == 422
    assert "uppercase" in str(res_no_upper.json()).lower()

    # Case 3: Missing lowercase
    res_no_lower = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nolower@memoryverse.ai",
            "password": "PASSWORD123!",
            "full_name": "No Lower",
        },
    )
    assert res_no_lower.status_code == 422
    assert "lowercase" in str(res_no_lower.json()).lower()

    # Case 4: Missing numeric digit
    res_no_digit = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nodigit@memoryverse.ai",
            "password": "PasswordSpecial!",
            "full_name": "No Digit",
        },
    )
    assert res_no_digit.status_code == 422
    assert "digit" in str(res_no_digit.json()).lower()

    # Case 5: Missing special symbol
    res_no_symbol = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nosymbol@memoryverse.ai",
            "password": "Password12345",
            "full_name": "No Symbol",
        },
    )
    assert res_no_symbol.status_code == 422
    assert "symbol" in str(res_no_symbol.json()).lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register user first
    reg_payload = {
        "email": "loginuser@memoryverse.ai",
        "password": "CorrectPassword123!",
        "full_name": "Login User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Attempt login
    login_payload = {
        "email": "loginuser@memoryverse.ai",
        "password": "CorrectPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "tokens" in body["data"]
    assert body["data"]["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    reg_payload = {
        "email": "wrongpass@memoryverse.ai",
        "password": "CorrectPassword123!",
        "full_name": "Wrong Pass User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrongpass@memoryverse.ai",
        "password": "WrongPassword456!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_auth_me_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "testuser@memoryverse.ai"


@pytest.mark.asyncio
async def test_auth_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    reg_payload = {
        "email": "refresh@memoryverse.ai",
        "password": "Password123!",
        "full_name": "Refresh Tester",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    refresh_token = reg_res.json()["data"]["tokens"]["refresh_token"]

    # Refresh
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()["data"]
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    assert new_tokens["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_forgot_and_reset_password(client: AsyncClient):
    # Register user
    reg_payload = {
        "email": "resetuser@memoryverse.ai",
        "password": "OldPassword123!",
        "full_name": "Reset Tester",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    old_token = reg_res.json()["data"]["tokens"]["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # Verify old token works before reset
    pre_res = await client.get("/api/v1/auth/me", headers=old_headers)
    assert pre_res.status_code == 200

    # Request password reset
    forgot_res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "resetuser@memoryverse.ai"},
    )
    assert forgot_res.status_code == 200
    debug_token = forgot_res.json()["data"]["debug_token"]
    assert debug_token

    # Reset password using token
    reset_res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": debug_token,
            "new_password": "BrandNewPassword999!",
        },
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True

    # Phase 4 Hardening: Old access token must now be rejected with 401
    post_res = await client.get("/api/v1/auth/me", headers=old_headers)
    assert post_res.status_code == 401
    assert "revoked" in post_res.json()["error"]["message"].lower()

    # Old password should now fail
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetuser@memoryverse.ai", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password should succeed
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetuser@memoryverse.ai", "password": "BrandNewPassword999!"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["success"] is True


@pytest.mark.asyncio
async def test_request_and_verify_email(client: AsyncClient, auth_headers: dict):
    # Request verification token
    req_res = await client.post(
        "/api/v1/auth/request-verification",
        headers=auth_headers,
    )
    assert req_res.status_code == 200
    debug_token = req_res.json()["data"]["debug_token"]
    assert debug_token

    # Verify email
    verify_res = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": debug_token},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True

    # Check profile to verify is_verified is now True
    me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["is_verified"] is True


@pytest.mark.asyncio
async def test_update_and_delete_user_account(client: AsyncClient, auth_headers: dict):
    # Update profile
    patch_payload = {
        "full_name": "Updated Name",
        "profile": {
            "bio": "AI Researcher and Knowledge Architect",
            "preferences": {"theme": "dark", "stream_responses": True},
        },
    }
    patch_res = await client.patch(
        "/api/v1/users/me",
        json=patch_payload,
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()["data"]
    assert data["full_name"] == "Updated Name"
    assert data["profile"]["bio"] == "AI Researcher and Knowledge Architect"
    assert data["profile"]["preferences"]["theme"] == "dark"

    # Delete account
    del_res = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify account no longer exists
    verify_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert verify_res.status_code == 401
