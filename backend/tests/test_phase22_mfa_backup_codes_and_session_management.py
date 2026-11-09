import re

import pytest
from httpx import AsyncClient

from app.core.security import generate_totp_code


@pytest.mark.asyncio
async def test_mfa_enable_generates_backup_recovery_codes(client: AsyncClient):
    """Verify enabling MFA returns 8 valid single-use backup recovery codes."""
    # 1. Register test user
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mfa_backup_gen@example.com",
            "password": "SecurePassword123!",
            "full_name": "MFA Backup Gen",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Setup MFA to get secret
    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup_res.status_code == 200
    secret = setup_res.json()["data"]["secret"]

    # 3. Enable MFA with TOTP code
    totp_code = generate_totp_code(secret)
    enable_res = await client.post(
        "/api/v1/auth/mfa/enable",
        json={"code": totp_code},
        headers=headers,
    )
    assert enable_res.status_code == 200
    data = enable_res.json()["data"]
    assert "backup_codes" in data
    codes = data["backup_codes"]
    assert len(codes) == 8
    assert data["count"] == 8

    # Verify each code adheres to 'XXXX-XXXX' hex format
    hex_code_pattern = re.compile(r"^[A-F0-9]{4}-[A-F0-9]{4}$")
    for c in codes:
        assert hex_code_pattern.match(c), f"Code {c} does not match expected format"

    # 4. Check /mfa/backup-codes endpoint reports count = 8
    count_res = await client.get("/api/v1/auth/mfa/backup-codes", headers=headers)
    assert count_res.status_code == 200
    assert count_res.json()["data"]["count"] == 8


@pytest.mark.asyncio
async def test_mfa_recovery_login_and_burn_on_use(client: AsyncClient):
    """Verify single-use backup recovery code authentication, replay protection, and burn-on-use."""
    email = "mfa_recovery_user@example.com"
    password = "SecurePassword123!"

    # 1. Register & enable MFA
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Recovery User"},
    )
    assert reg.status_code == 201
    auth_header = {"Authorization": f"Bearer {reg.json()['data']['tokens']['access_token']}"}

    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=auth_header)
    secret = setup_res.json()["data"]["secret"]

    enable_res = await client.post(
        "/api/v1/auth/mfa/enable",
        json={"code": generate_totp_code(secret)},
        headers=auth_header,
    )
    assert enable_res.status_code == 200
    backup_codes = enable_res.json()["data"]["backup_codes"]
    first_code = backup_codes[0]
    second_code = backup_codes[1]

    # 2. Trigger login challenge requiring MFA
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    login_data = login_res.json()["data"]
    assert login_data["mfa_required"] is True
    mfa_token = login_data["mfa_token"]

    # 3. Attempt recovery with bogus code -> 401
    bad_res = await client.post(
        "/api/v1/auth/mfa/recovery",
        json={"mfa_token": mfa_token, "recovery_code": "0000-0000"},
    )
    assert bad_res.status_code == 401

    # 4. Authenticate using first backup recovery code -> 200
    rec_res = await client.post(
        "/api/v1/auth/mfa/recovery",
        json={"mfa_token": mfa_token, "recovery_code": first_code},
    )
    assert rec_res.status_code == 200
    session_token = rec_res.json()["data"]["tokens"]["access_token"]
    session_headers = {"Authorization": f"Bearer {session_token}"}

    # 5. Check remaining backup codes count is now 7
    count_res = await client.get("/api/v1/auth/mfa/backup-codes", headers=session_headers)
    assert count_res.status_code == 200
    assert count_res.json()["data"]["count"] == 7

    # 6. Replay attack: try using the exact same first code again in a new login attempt
    login_res2 = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    mfa_token2 = login_res2.json()["data"]["mfa_token"]

    replay_res = await client.post(
        "/api/v1/auth/mfa/recovery",
        json={"mfa_token": mfa_token2, "recovery_code": first_code},
    )
    assert replay_res.status_code == 401, "Burned code must not be reusable"

    # 7. Authenticate using second code with lowercase and hyphen stripped
    stripped_code = second_code.replace("-", "").lower()
    rec_res2 = await client.post(
        "/api/v1/auth/mfa/recovery",
        json={"mfa_token": mfa_token2, "recovery_code": stripped_code},
    )
    assert rec_res2.status_code == 200
    session_token2 = rec_res2.json()["data"]["tokens"]["access_token"]
    session_headers2 = {"Authorization": f"Bearer {session_token2}"}

    # 8. Check remaining backup codes count is now 6
    count_res2 = await client.get("/api/v1/auth/mfa/backup-codes", headers=session_headers2)
    assert count_res2.status_code == 200
    assert count_res2.json()["data"]["count"] == 6


@pytest.mark.asyncio
async def test_regenerate_backup_codes(client: AsyncClient):
    """Verify regenerating backup recovery codes resets the pool to 8 new valid codes."""
    email = "mfa_regen_user@example.com"
    password = "SecurePassword123!"

    # 1. Register & enable MFA
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Regen User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup_res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_res.json()["data"]["secret"]

    enable_res = await client.post(
        "/api/v1/auth/mfa/enable",
        json={"code": generate_totp_code(secret)},
        headers=headers,
    )
    initial_codes = set(enable_res.json()["data"]["backup_codes"])

    # 2. Attempt regeneration with incorrect password -> 401
    bad_pass = await client.post(
        "/api/v1/auth/mfa/backup-codes/regenerate",
        json={"password": "WrongPassword!", "code": generate_totp_code(secret)},
        headers=headers,
    )
    assert bad_pass.status_code == 401

    # 3. Attempt regeneration with invalid TOTP -> 400
    bad_totp = await client.post(
        "/api/v1/auth/mfa/backup-codes/regenerate",
        json={"password": password, "code": "000000"},
        headers=headers,
    )
    assert bad_totp.status_code == 400

    # 4. Regenerate with valid password and TOTP -> 200
    regen_res = await client.post(
        "/api/v1/auth/mfa/backup-codes/regenerate",
        json={"password": password, "code": generate_totp_code(secret)},
        headers=headers,
    )
    assert regen_res.status_code == 200
    new_codes = regen_res.json()["data"]["backup_codes"]
    assert len(new_codes) == 8
    assert regen_res.json()["data"]["count"] == 8

    # The new codes should be completely fresh
    assert set(new_codes) != initial_codes

    # 5. Verify count endpoint reports 8
    count_res = await client.get("/api/v1/auth/mfa/backup-codes", headers=headers)
    assert count_res.json()["data"]["count"] == 8


@pytest.mark.asyncio
async def test_active_sessions_listing_and_device_parsing(client: AsyncClient):
    """Verify session management lists active unrevoked sessions with readable device info."""
    email = "sessions_test@example.com"
    password = "SecurePassword123!"

    # 1. Register user (creates initial session 1)
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Sessions User"},
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        },
    )
    assert reg.status_code == 201

    # 2. Login from a second device (Windows Firefox)
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        },
    )
    assert login2.status_code == 200
    token2 = login2.json()["data"]["tokens"]["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 3. Fetch active sessions using device 2's token
    sess_res = await client.get("/api/v1/auth/sessions", headers=headers2)
    assert sess_res.status_code == 200
    sessions = sess_res.json()["data"]
    assert len(sessions) >= 2

    # Verify device 2 session has is_current = True
    current_session = next((s for s in sessions if s["is_current"] is True), None)
    assert current_session is not None
    assert "Firefox" in current_session["device_info"]
    assert "Windows" in current_session["device_info"]

    # Verify device 1 session is present with is_current = False
    other_session = next((s for s in sessions if s["is_current"] is False), None)
    assert other_session is not None


@pytest.mark.asyncio
async def test_remote_session_revocation(client: AsyncClient):
    """Verify remote session revocation immediately terminates access on that specific token."""
    email = "remote_revoke@example.com"
    password = "SecurePassword123!"

    # 1. Register user on Device 1
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Remote Revoke User"},
        headers={"User-Agent": "Device1-Agent"},
    )
    token1 = reg.json()["data"]["tokens"]["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 2. Login on Device 2
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"User-Agent": "Device2-Agent"},
    )
    token2 = login2.json()["data"]["tokens"]["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Verify Device 1 can call /auth/me
    me1 = await client.get("/api/v1/auth/me", headers=headers1)
    assert me1.status_code == 200

    # 3. List sessions from Device 2 and find Device 1's session ID
    sess_res = await client.get("/api/v1/auth/sessions", headers=headers2)
    sessions = sess_res.json()["data"]
    dev1_sess = next(s for s in sessions if s["is_current"] is False)

    # 4. Revoke Device 1's session remotely from Device 2
    del_res = await client.delete(f"/api/v1/auth/sessions/{dev1_sess['id']}", headers=headers2)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 5. Device 1 should now be rejected immediately with 401
    me1_after = await client.get("/api/v1/auth/me", headers=headers1)
    assert me1_after.status_code == 401
    assert "revoked" in me1_after.json()["error"]["message"].lower()

    # 6. Device 2 continues to be authenticated and functional
    me2 = await client.get("/api/v1/auth/me", headers=headers2)
    assert me2.status_code == 200


@pytest.mark.asyncio
async def test_revoke_other_sessions(client: AsyncClient):
    """Verify 'Revoke All Other Sessions' terminates other sessions while keeping the current session active."""
    email = "revoke_others@example.com"
    password = "SecurePassword123!"

    # 1. Register Device 1
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Revoke Others User"},
    )
    token1 = reg.json()["data"]["tokens"]["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 2. Login on Device 2
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"User-Agent": "Device 2"},
    )
    token2 = login2.json()["data"]["tokens"]["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 3. Login on Device 3
    login3 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"User-Agent": "Device 3"},
    )
    token3 = login3.json()["data"]["tokens"]["access_token"]
    headers3 = {"Authorization": f"Bearer {token3}"}

    # 4. From Device 3, call DELETE /api/v1/auth/sessions/other
    revoke_res = await client.delete("/api/v1/auth/sessions/other", headers=headers3)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["data"]["revoked_count"] >= 2

    # 5. Device 1 and Device 2 should now be revoked (401)
    assert (await client.get("/api/v1/auth/me", headers=headers1)).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=headers2)).status_code == 401

    # 6. Device 3 remains active and authenticated (200)
    assert (await client.get("/api/v1/auth/me", headers=headers3)).status_code == 200

    # 7. Listing sessions from Device 3 shows only 1 active session
    active_sessions = (await client.get("/api/v1/auth/sessions", headers=headers3)).json()["data"]
    assert len(active_sessions) == 1
    assert active_sessions[0]["is_current"] is True
