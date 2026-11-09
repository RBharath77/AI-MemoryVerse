from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.models.memory import Memory, MemoryCategory, MemoryStatus


@pytest.mark.asyncio
async def test_cross_modal_fusion_search_weight_distribution(client: AsyncClient):
    """
    Test Multi-Modal Cross-Attention Memory Fusion:
    verifies modality detection across code, tables, audio transcripts, and dynamic attention weight distribution.
    """
    user_email = f"fusion_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Fusion Researcher",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 1. Seed memories with distinct modalities
    async with core_db.AsyncSessionLocal() as session:
        m1 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="def authenticate_jwt_user(token: str) -> User:\n    payload = decode_jwt(token)\n    return db.query(User).filter_by(id=payload['sub']).first()",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
        )
        m2 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="| Service | Port | Protocol |\n| postgres | 5432 | TCP |\n| redis | 6379 | TCP |",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
        )
        m3 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="Client audio call transcript: We need higher data retention SLA on speech synthesis models.",
            category=MemoryCategory.SEMANTIC,
            status=MemoryStatus.APPROVED,
        )
        session.add_all([m1, m2, m3])
        await session.commit()

    # 2. Search prioritizing code modality
    code_res = await client.post(
        "/api/v1/search/cross-modal-fusion",
        headers=headers,
        json={
            "query": "authenticate jwt token python function",
            "code_weight": 0.60,
            "text_weight": 0.20,
            "table_weight": 0.10,
            "audio_weight": 0.10,
            "top_k": 3,
        },
    )
    assert code_res.status_code == 200
    c_data = code_res.json()["data"]
    assert c_data["workspace_id"] == ws_id
    assert c_data["total_candidates_evaluated"] == 3
    assert len(c_data["results"]) >= 1

    top_result = c_data["results"][0]
    assert top_result["primary_modality"] == "code"
    assert "CODE" in top_result["modality_badges"]
    assert top_result["modal_scores"]["code_score"] > 0.0

    # 3. Search prioritizing audio transcripts
    audio_res = await client.post(
        "/api/v1/search/cross-modal-fusion",
        headers=headers,
        json={
            "query": "Client audio call transcript retention speech",
            "code_weight": 0.10,
            "text_weight": 0.10,
            "table_weight": 0.10,
            "audio_weight": 0.70,
            "top_k": 3,
        },
    )
    assert audio_res.status_code == 200
    a_data = audio_res.json()["data"]
    top_audio = a_data["results"][0]
    assert top_audio["primary_modality"] == "audio"
    assert "AUDIO" in top_audio["modality_badges"]


@pytest.mark.asyncio
async def test_spaced_repetition_schedule_and_sm2_review(client: AsyncClient):
    """
    Test Autonomous Spaced Repetition Scheduling:
    verifies SM-2 algorithm progression, ease factor updates, interval calculation, and review date scheduling.
    """
    user_email = f"sm2_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "SM2 Specialist",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 1. Seed memory in workspace
    async with core_db.AsyncSessionLocal() as session:
        m = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="RFC 6238 TOTP requires 30-second time steps and SHA-1 HMAC computation.",
            category=MemoryCategory.SEMANTIC,
            status=MemoryStatus.APPROVED,
            importance=8,
        )
        session.add(m)
        await session.commit()
        mem_id = m.id

    # 2. Get initial spaced repetition schedule
    sched_res = await client.get(
        "/api/v1/memories/spaced-repetition/schedule",
        headers=headers,
    )
    assert sched_res.status_code == 200
    s_data = sched_res.json()["data"]
    assert s_data["workspace_id"] == ws_id
    assert s_data["total_cards"] >= 1
    card = next(c for c in s_data["cards"] if c["memory_id"] == mem_id)
    assert card["repetition_number"] == 0
    assert card["ease_factor"] == 2.5
    assert card["interval_days"] == 1

    # 3. Submit first review (rating 5 = perfect recall)
    review_res1 = await client.post(
        "/api/v1/memories/spaced-repetition/review",
        headers=headers,
        json={"memory_id": mem_id, "rating": 5},
    )
    assert review_res1.status_code == 200
    r1 = review_res1.json()["data"]
    assert r1["previous_repetition"] == 0
    assert r1["new_repetition"] == 1
    assert r1["new_interval_days"] == 1
    assert r1["new_ease_factor"] == 2.5  # Clamped at 2.5 max

    # 4. Submit second review (rating 4 = correct with hesitation)
    review_res2 = await client.post(
        "/api/v1/memories/spaced-repetition/review",
        headers=headers,
        json={"memory_id": mem_id, "rating": 4},
    )
    assert review_res2.status_code == 200
    r2 = review_res2.json()["data"]
    assert r2["previous_repetition"] == 1
    assert r2["new_repetition"] == 2
    assert r2["new_interval_days"] == 6  # Second repetition standard SM-2 interval is 6 days


@pytest.mark.asyncio
async def test_time_locked_vault_burn_after_reading(client: AsyncClient):
    """
    Test Zero-Knowledge Ephemeral Memory Vault:
    verifies encryption, single-view decrypt, and automatic burn-on-read zeroization.
    """
    user_email = f"vault_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Vault Guardian",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 1. Create burn-after-reading time-locked secret
    create_res = await client.post(
        "/api/v1/memories/time-locked",
        headers=headers,
        json={
            "secret_content": "SuperSecretDatabaseMasterPassword_2026!",
            "ttl_seconds": 3600,
            "max_views": 1,
            "hint": "Emergency DB Credential",
        },
    )
    assert create_res.status_code == 201
    v_data = create_res.json()["data"]
    vault_id = v_data["vault_id"]
    assert v_data["views_remaining"] == 1
    assert v_data["is_burned"] is False

    # 2. First Read -> Success and Burned
    reveal_res = await client.get(
        f"/api/v1/memories/time-locked/{vault_id}",
        headers=headers,
    )
    assert reveal_res.status_code == 200
    rev_data = reveal_res.json()["data"]
    assert rev_data["decrypted_content"] == "SuperSecretDatabaseMasterPassword_2026!"
    assert rev_data["views_remaining"] == 0
    assert rev_data["is_burned"] is True

    # 3. Second Read -> 404 (Key zeroized and record shredded)
    burned_res = await client.get(
        f"/api/v1/memories/time-locked/{vault_id}",
        headers=headers,
    )
    assert burned_res.status_code == 404


@pytest.mark.asyncio
async def test_time_locked_vault_timelock_unlock_window(client: AsyncClient):
    """
    Test Time-Locked Vault Delay Window:
    verifies that an unexpired secret cannot be unlocked prior to the unlock_at timestamp (HTTP 423 Locked).
    """
    user_email = f"timelock_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "TimeLock Keeper",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Create secret locked for 300 seconds (5 minutes in future)
    create_res = await client.post(
        "/api/v1/memories/time-locked",
        headers=headers,
        json={
            "secret_content": "BoardMeetingAcquisitionPriceTarget_80M",
            "ttl_seconds": 3600,
            "unlock_delay_seconds": 300,
            "max_views": 3,
        },
    )
    assert create_res.status_code == 201
    vault_id = create_res.json()["data"]["vault_id"]

    # Read attempt before unlock_at -> 423 Locked
    locked_res = await client.get(
        f"/api/v1/memories/time-locked/{vault_id}",
        headers=headers,
    )
    assert locked_res.status_code == 423
    err_msg = locked_res.json().get("error", {}).get("message", "") or locked_res.json().get("detail", "")
    assert "locked until" in err_msg


@pytest.mark.asyncio
async def test_time_locked_vault_immediate_crypto_shred(client: AsyncClient):
    """
    Test premature cryptographic shredding:
    verifies manual deletion zeros keys and destroys ephemeral vault items immediately.
    """
    user_email = f"shred_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Crypto Shredder",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    create_res = await client.post(
        "/api/v1/memories/time-locked",
        headers=headers,
        json={
            "secret_content": "ImmediateZeroizationCandidate",
            "ttl_seconds": 3600,
            "max_views": 5,
        },
    )
    assert create_res.status_code == 201
    vault_id = create_res.json()["data"]["vault_id"]

    # Manual immediate cryptographic shredding
    del_res = await client.delete(
        f"/api/v1/memories/time-locked/{vault_id}",
        headers=headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["shredded"] is True

    # Confirm record is gone
    get_res = await client.get(
        f"/api/v1/memories/time-locked/{vault_id}",
        headers=headers,
    )
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_phase38_multi_tenant_isolation(client: AsyncClient):
    """
    Test Phase 38 multi-tenant security boundaries:
    verifies Tenant B cannot read or shred Tenant A's time-locked vault memories.
    """
    # 1. Setup Tenant A
    user_a = f"tenant_a_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": user_a, "password": "SecurePassword123!", "full_name": "Tenant A"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a}

    # 2. Setup Tenant B
    user_b = f"tenant_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": user_b, "password": "SecurePassword123!", "full_name": "Tenant B"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b}

    # 3. Tenant A creates time-locked secret
    create_a = await client.post(
        "/api/v1/memories/time-locked",
        headers=headers_a,
        json={"secret_content": "Tenant A Secret Keys", "ttl_seconds": 3600},
    )
    assert create_a.status_code == 201
    vault_a_id = create_a.json()["data"]["vault_id"]

    # 4. Tenant B attempts to read Tenant A secret -> 404 Not Found
    get_b = await client.get(
        f"/api/v1/memories/time-locked/{vault_a_id}",
        headers=headers_b,
    )
    assert get_b.status_code == 404

    # 5. Tenant B attempts to delete Tenant A secret -> shredded False
    del_b = await client.delete(
        f"/api/v1/memories/time-locked/{vault_a_id}",
        headers=headers_b,
    )
    assert del_b.status_code == 200
    assert del_b.json()["data"]["shredded"] is False
