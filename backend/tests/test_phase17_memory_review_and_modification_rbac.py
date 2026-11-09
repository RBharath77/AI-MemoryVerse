from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import database as core_db
from app.models.memory import Memory, MemoryCategory, MemoryReview, MemoryStatus


@pytest.mark.asyncio
async def test_memory_update_rbac(client: AsyncClient):
    """Verify that regular workspace members cannot modify memories authored by peers."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_sec_owner@phase17.ai",
            "password": "Password123!",
            "full_name": "Mem Sec Owner",
            "workspace_name": "Memory RBAC WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Creator) and Member B (Unauthorized Member)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_author@phase17.ai",
            "password": "Password123!",
            "full_name": "Mem Author",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_a_id = reg_a.json()["data"]["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_unauth@phase17.ai",
            "password": "Password123!",
            "full_name": "Mem Unauth",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    # Add both to workspace
    for uid in [user_a_id, user_b_id]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 3. Member A creates a memory
    create_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Original confidential strategy plan for 2027.",
            "category": "project",
            "importance": 7,
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    mem_id = create_res.json()["data"]["id"]

    # 4. Member B attempts to edit Member A's memory -> 403 Forbidden
    patch_res_b = await client.patch(
        f"/api/v1/memories/{mem_id}",
        json={"content": "Defaced strategy plan by unprivileged user."},
        headers=headers_b,
    )
    assert patch_res_b.status_code == 403
    assert "Insufficient permissions" in patch_res_b.text

    # 5. Member A updates their own memory -> 200 OK
    patch_res_a = await client.patch(
        f"/api/v1/memories/{mem_id}",
        json={"content": "Updated legitimate strategy plan for 2027."},
        headers=headers_a,
    )
    assert patch_res_a.status_code == 200
    assert patch_res_a.json()["data"]["content"] == "Updated legitimate strategy plan for 2027."


@pytest.mark.asyncio
async def test_memory_restore_version_rbac(client: AsyncClient):
    """Verify that regular workspace members cannot roll back or restore versions of peers' memories."""
    # 1. Register Owner and Member A and Member B
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "restore_owner@phase17.ai",
            "password": "Password123!",
            "full_name": "Restore Owner",
            "workspace_name": "Restore RBAC WS",
        },
    )
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "restore_author@phase17.ai",
            "password": "Password123!",
            "full_name": "Restore Author",
        },
    )
    headers_a = {
        "Authorization": f"Bearer {reg_a.json()['data']['tokens']['access_token']}",
        "X-Workspace-ID": ws_id,
    }

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "restore_unauth@phase17.ai",
            "password": "Password123!",
            "full_name": "Restore Unauth",
        },
    )
    headers_b = {
        "Authorization": f"Bearer {reg_b.json()['data']['tokens']['access_token']}",
        "X-Workspace-ID": ws_id,
    }

    for uid in [reg_a.json()["data"]["user"]["id"], reg_b.json()["data"]["user"]["id"]]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 2. Member A creates a memory (v1) and edits it (v2)
    mem_res = await client.post(
        "/api/v1/memories",
        json={"content": "Version 1 initial fact text.", "category": "semantic"},
        headers=headers_a,
    )
    mem_id = mem_res.json()["data"]["id"]

    await client.patch(
        f"/api/v1/memories/{mem_id}",
        json={"content": "Version 2 updated fact text."},
        headers=headers_a,
    )

    # 3. Member B attempts to restore version 1 -> 403 Forbidden
    restore_res_b = await client.post(
        f"/api/v1/memories/{mem_id}/restore?version_number=1",
        headers=headers_b,
    )
    assert restore_res_b.status_code == 403
    assert "Insufficient permissions" in restore_res_b.text

    # 4. Member A restores version 1 -> 200 OK
    restore_res_a = await client.post(
        f"/api/v1/memories/{mem_id}/restore?version_number=1",
        headers=headers_a,
    )
    assert restore_res_a.status_code == 200
    assert restore_res_a.json()["data"]["content"] == "Version 1 initial fact text."


@pytest.mark.asyncio
async def test_memory_review_action_rbac(client: AsyncClient):
    """Verify that only the memory creator or workspace admin can act on pending memory reviews."""
    # 1. Register Owner, Member A, Member B
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rev_owner@phase17.ai",
            "password": "Password123!",
            "full_name": "Rev Owner",
            "workspace_name": "Review RBAC WS",
        },
    )
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {
        "Authorization": f"Bearer {reg_owner.json()['data']['tokens']['access_token']}",
        "X-Workspace-ID": ws_id,
    }

    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rev_author@phase17.ai",
            "password": "Password123!",
            "full_name": "Rev Author",
        },
    )
    uid_a = reg_a.json()["data"]["user"]["id"]
    headers_a = {
        "Authorization": f"Bearer {reg_a.json()['data']['tokens']['access_token']}",
        "X-Workspace-ID": ws_id,
    }

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rev_unauth@phase17.ai",
            "password": "Password123!",
            "full_name": "Rev Unauth",
        },
    )
    uid_b = reg_b.json()["data"]["user"]["id"]
    headers_b = {
        "Authorization": f"Bearer {reg_b.json()['data']['tokens']['access_token']}",
        "X-Workspace-ID": ws_id,
    }

    for uid in [uid_a, uid_b]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 2. Insert a memory and pending MemoryReview for Member A
    async with core_db.async_session_factory() as db:
        mem = Memory(
            workspace_id=ws_id,
            user_id=uid_a,
            content="Candidate memory text pending verification.",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.PENDING_REVIEW,
        )
        db.add(mem)
        await db.commit()
        await db.refresh(mem)

        review = MemoryReview(
            workspace_id=ws_id,
            memory_id=mem.id,
            review_status="pending",
            original_text=mem.content,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        review_id = review.id

    # 3. Member B attempts to reject/approve Member A's review item -> 403 Forbidden
    act_res_b = await client.post(
        f"/api/v1/memory-reviews/{review_id}/action",
        json={"review_status": "rejected", "review_notes": "Unauthorized rejection attempt."},
        headers=headers_b,
    )
    assert act_res_b.status_code == 403
    assert "Insufficient permissions" in act_res_b.text

    # 4. Member A approves their own review item -> 200 OK
    act_res_a = await client.post(
        f"/api/v1/memory-reviews/{review_id}/action",
        json={"review_status": "approved", "review_notes": "Looks accurate."},
        headers=headers_a,
    )
    assert act_res_a.status_code == 200
    assert act_res_a.json()["data"]["review_status"] == "approved"


@pytest.mark.asyncio
async def test_memory_review_corrected_credential_sanitization(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that correcting a memory review redacts embedded API credentials."""
    ws_id = auth_headers["X-Workspace-ID"]

    # 1. Create a memory in pending review status
    async with core_db.async_session_factory() as db:
        mem = Memory(
            workspace_id=ws_id,
            user_id="test_user",
            content="Initial candidate fact.",
            category=MemoryCategory.SEMANTIC,
            status=MemoryStatus.PENDING_REVIEW,
        )
        db.add(mem)
        await db.commit()
        await db.refresh(mem)

        review = MemoryReview(
            workspace_id=ws_id,
            memory_id=mem.id,
            review_status="pending",
            original_text=mem.content,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        review_id = review.id
        mem_id = mem.id

    # 2. Correct the memory review supplying raw OpenAI and AWS credentials
    raw_secret_correction = (
        "Corrected with OpenAI sk-proj-1234567890abcdef1234567890 and AWS AKIAIOSFODNN7EXAMPLE"
    )
    act_res = await client.post(
        f"/api/v1/memory-reviews/{review_id}/action",
        json={"review_status": "corrected", "corrected_text": raw_secret_correction},
        headers=auth_headers,
    )
    assert act_res.status_code == 200

    # 3. Check that the persisted memory and review text have scrubbed tokens
    async with core_db.async_session_factory() as db:
        persisted_mem = await db.get(Memory, mem_id)
        assert persisted_mem is not None
        assert "sk-proj-" not in persisted_mem.content
        assert "AKIAIOSFODNN7EXAMPLE" not in persisted_mem.content
        assert "[REDACTED_OPENAI_KEY]" in persisted_mem.content
        assert "[REDACTED_AWS_KEY]" in persisted_mem.content


@pytest.mark.asyncio
async def test_memory_extraction_credential_sanitization(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that unstructured fact extraction redacts credentials before storing into memories."""
    raw_text = (
        "Project setup notes: our OpenAI token is sk-proj-1234567890abcdef1234567890 "
        "and production AWS access key is AKIAIOSFODNN7EXAMPLE. We deploy weekly."
    )

    ext_res = await client.post(
        "/api/v1/memories/extract",
        json={"text": raw_text, "source_type": "notes", "auto_approve": True},
        headers=auth_headers,
    )
    assert ext_res.status_code == 200

    ws_id = auth_headers["X-Workspace-ID"]

    async with core_db.async_session_factory() as db:
        q = select(Memory).where(Memory.workspace_id == ws_id).order_by(Memory.created_at.desc())
        memories = (await db.execute(q)).scalars().all()
        assert len(memories) > 0
        for m in memories:
            assert "sk-proj-" not in m.content
            assert "AKIAIOSFODNN7EXAMPLE" not in m.content
