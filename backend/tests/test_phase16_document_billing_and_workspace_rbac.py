from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.models.document import Document


@pytest.mark.asyncio
async def test_document_deletion_rbac(client: AsyncClient):
    """Verify that regular workspace members cannot delete documents uploaded by peers."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doc_owner@phase16.ai",
            "password": "Password123!",
            "full_name": "Doc Owner",
            "workspace_name": "Doc Security WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Uploader) and Member B (Unauthorized Member)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doc_author@phase16.ai",
            "password": "Password123!",
            "full_name": "Doc Author",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_a_id = reg_a.json()["data"]["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doc_unauth@phase16.ai",
            "password": "Password123!",
            "full_name": "Doc Unauth",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    # Add both to workspace as regular members
    for uid in [user_a_id, user_b_id]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 3. Create a Document uploaded by Member A
    async with core_db.async_session_factory() as db:
        doc = Document(
            workspace_id=ws_id,
            user_id=user_a_id,
            title="Q3 Strategy Plan",
            filename="q3_plan.txt",
            file_key=f"{ws_id}/q3_plan.txt",
            file_size=120,
            mime_type="text/plain",
            file_hash="dummy_hash_123",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    # 4. Member B attempts to delete Member A's document -> 403 Forbidden
    del_res_b = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert del_res_b.status_code == 403
    assert "Insufficient permissions" in del_res_b.text

    # 5. Member A (the uploader) deletes the document -> 200 OK
    del_res_a = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
    assert del_res_a.status_code == 200


@pytest.mark.asyncio
async def test_billing_financial_operations_rbac(client: AsyncClient):
    """Verify that regular workspace members cannot checkout, upgrade, or cancel subscriptions."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bill_owner@phase16.ai",
            "password": "Password123!",
            "full_name": "Bill Owner",
            "workspace_name": "Billing RBAC WS",
        },
    )
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member
    reg_mem = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bill_member@phase16.ai",
            "password": "Password123!",
            "full_name": "Bill Member",
        },
    )
    mem_token = reg_mem.json()["data"]["tokens"]["access_token"]
    mem_user_id = reg_mem.json()["data"]["user"]["id"]
    mem_headers = {"Authorization": f"Bearer {mem_token}", "X-Workspace-ID": ws_id}

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": mem_user_id, "role": "member"},
        headers=owner_headers,
    )

    # 3. Regular member attempts checkout -> 403 Forbidden
    res_chk = await client.post(
        "/api/v1/billing/checkout",
        json={
            "plan_tier": "pro",
            "success_url": "http://localhost:3000/billing?status=success",
            "cancel_url": "http://localhost:3000/billing?status=canceled",
        },
        headers=mem_headers,
    )
    assert res_chk.status_code == 403
    assert "Admin or Owner" in res_chk.text

    # 4. Regular member attempts upgrade -> 403 Forbidden
    res_upg = await client.post(
        "/api/v1/billing/upgrade",
        json={"plan_tier": "pro"},
        headers=mem_headers,
    )
    assert res_upg.status_code == 403
    assert "Admin or Owner" in res_upg.text

    # 5. Regular member attempts cancel -> 403 Forbidden
    res_can = await client.post("/api/v1/billing/cancel", headers=mem_headers)
    assert res_can.status_code == 403
    assert "Admin or Owner" in res_can.text

    # 6. Owner executes cancel -> 200 OK
    res_owner_can = await client.post("/api/v1/billing/cancel", headers=owner_headers)
    assert res_owner_can.status_code == 200
    assert res_owner_can.json()["data"]["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_workspace_member_invite_and_eject_privilege_escalation_defense(client: AsyncClient):
    """Verify that admins cannot invite owners or remove other admins/owners."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ws_sec_owner@phase16.ai",
            "password": "Password123!",
            "full_name": "WS Sec Owner",
            "workspace_name": "Privilege Escalation WS",
        },
    )
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    owner_id = reg_owner.json()["data"]["user"]["id"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Admin 1 and Admin 2
    reg_a1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin1@phase16.ai", "password": "Password123!", "full_name": "Admin One"},
    )
    a1_token = reg_a1.json()["data"]["tokens"]["access_token"]
    a1_id = reg_a1.json()["data"]["user"]["id"]
    a1_headers = {"Authorization": f"Bearer {a1_token}", "X-Workspace-ID": ws_id}

    reg_a2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin2@phase16.ai", "password": "Password123!", "full_name": "Admin Two"},
    )
    a2_id = reg_a2.json()["data"]["user"]["id"]

    reg_new = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@phase16.ai", "password": "Password123!", "full_name": "New User"},
    )
    new_user_id = reg_new.json()["data"]["user"]["id"]

    # Owner adds Admin 1 and Admin 2 as admins
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": a1_id, "role": "admin"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": a2_id, "role": "admin"},
        headers=owner_headers,
    )

    # 3. Admin 1 attempts to invite new user as OWNER -> 403 Forbidden
    inv_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": new_user_id, "role": "owner"},
        headers=a1_headers,
    )
    assert inv_res.status_code == 403
    assert "Only workspace owners can assign the OWNER role" in inv_res.text

    # 4. Admin 1 attempts to eject the workspace OWNER -> 400 Bad Request
    eject_owner_res = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        headers=a1_headers,
    )
    assert eject_owner_res.status_code == 400
    assert "Cannot remove the workspace owner" in eject_owner_res.text

    # 5. Admin 1 attempts to eject Admin 2 -> 403 Forbidden
    eject_a2_res = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{a2_id}",
        headers=a1_headers,
    )
    assert eject_a2_res.status_code == 403
    assert "Only workspace owners can remove admin members" in eject_a2_res.text


@pytest.mark.asyncio
async def test_workspace_member_role_update_rbac(client: AsyncClient):
    """Verify that only the workspace owner can promote members to Admin or demote them."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "role_owner@phase16.ai",
            "password": "Password123!",
            "full_name": "Role Owner",
            "workspace_name": "Role RBAC WS",
        },
    )
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    owner_id = reg_owner.json()["data"]["user"]["id"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Admin and Member
    reg_admin = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "role_admin@phase16.ai",
            "password": "Password123!",
            "full_name": "Role Admin",
        },
    )
    admin_token = reg_admin.json()["data"]["tokens"]["access_token"]
    admin_id = reg_admin.json()["data"]["user"]["id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Workspace-ID": ws_id}

    reg_member = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "role_member@phase16.ai",
            "password": "Password123!",
            "full_name": "Role Member",
        },
    )
    member_id = reg_member.json()["data"]["user"]["id"]

    # Add both to workspace
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": admin_id, "role": "admin"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "role": "member"},
        headers=owner_headers,
    )

    # 3. Admin attempts to promote regular member to ADMIN -> 403 Forbidden
    patch_by_admin = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        json={"role": "admin"},
        headers=admin_headers,
    )
    assert patch_by_admin.status_code == 403
    assert "Only workspace owners can promote members to Admin" in patch_by_admin.text

    # 4. Admin attempts to demote owner -> 400 Bad Request
    patch_owner = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        json={"role": "member"},
        headers=admin_headers,
    )
    assert patch_owner.status_code == 400
    assert "Cannot change the workspace owner's role directly" in patch_owner.text

    # 5. Owner promotes member to ADMIN -> 200 OK
    patch_by_owner = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert patch_by_owner.status_code == 200
    assert patch_by_owner.json()["data"]["role"] == "admin"


@pytest.mark.asyncio
async def test_password_reset_token_invalidation_lifecycle(client: AsyncClient):
    """Verify that requesting a new reset token invalidates previously issued active tokens."""
    # 1. Register user
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset_cycle@phase16.ai",
            "password": "Password123!",
            "full_name": "Reset Cycle User",
        },
    )
    assert reg.status_code == 201

    # 2. Request first reset token
    res1 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset_cycle@phase16.ai"},
    )
    assert res1.status_code == 200
    token1 = res1.json()["data"]["debug_token"]
    assert token1 is not None

    # 3. Request second reset token (should invalidate token1)
    res2 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset_cycle@phase16.ai"},
    )
    assert res2.status_code == 200
    token2 = res2.json()["data"]["debug_token"]
    assert token2 is not None
    assert token1 != token2

    # 4. Attempt to use Token 1 -> Should fail (400 Bad Request)
    fail_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token1, "new_password": "NewSecretPassword123!"},
    )
    assert fail_res.status_code == 400
    assert "Invalid or expired reset token" in fail_res.text

    # 5. Use Token 2 -> Should succeed (200 OK)
    succ_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token2, "new_password": "NewSecretPassword123!"},
    )
    assert succ_res.status_code == 200
    assert "successfully reset" in succ_res.text
