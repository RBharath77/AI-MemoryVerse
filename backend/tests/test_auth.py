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
    payload = {
        "email": "weak@memoryverse.ai",
        "password": "short",  # Less than 8 chars
        "full_name": "Weak Pass",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False


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
