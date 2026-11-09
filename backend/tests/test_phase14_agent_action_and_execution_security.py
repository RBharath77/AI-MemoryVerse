from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import database as core_db
from app.models.agent import ActionApprovalStatus, AgentAction, AgentTask, TaskStatus
from app.models.memory import Memory
from app.services.agent_service import AgentService


@pytest.mark.asyncio
async def test_agent_action_approval_and_rejection_rbac(client: AsyncClient):
    """Verify that only the task owner or workspace admin can approve or reject gated agent actions."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_owner@phase14.ai",
            "password": "Password123!",
            "full_name": "Agent Owner",
            "workspace_name": "Agent Security WS",
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
            "email": "agent_author@phase14.ai",
            "password": "Password123!",
            "full_name": "Agent Author",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_a_id = reg_a.json()["data"]["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_unauth@phase14.ai",
            "password": "Password123!",
            "full_name": "Agent Unauth",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    # Add both to the workspace
    for uid in [user_a_id, user_b_id]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 3. Member A launches an autonomous agent task
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Data Cleanup Workflow", "goal": "Remove obsolete memories and audit vault"},
        headers=headers_a,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["data"]["id"]

    # 4. Insert an action checkpoint in PENDING_APPROVAL status
    async with core_db.async_session_factory() as db:
        action1 = AgentAction(
            task_id=task_id,
            workspace_id=ws_id,
            tool_name="delete_memory",
            tool_input={"memory_id": "dummy_mem_id"},
            risk_level="high",
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        )
        action2 = AgentAction(
            task_id=task_id,
            workspace_id=ws_id,
            tool_name="delete_memory",
            tool_input={"memory_id": "dummy_mem_id2"},
            risk_level="high",
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        )
        db.add_all([action1, action2])
        await db.commit()
        await db.refresh(action1)
        await db.refresh(action2)
        action1_id = action1.id
        action2_id = action2.id

    # 5. Member B attempts to approve action1 -> 403 Forbidden
    appr_res_b = await client.post(
        f"/api/v1/agents/actions/{action1_id}/approve",
        headers=headers_b,
    )
    assert appr_res_b.status_code == 403
    assert "Insufficient permissions" in appr_res_b.text

    # 6. Member A (the task author) approves action1 -> 200 OK
    appr_res_a = await client.post(
        f"/api/v1/agents/actions/{action1_id}/approve",
        headers=headers_a,
    )
    assert appr_res_a.status_code == 200
    assert appr_res_a.json()["data"]["status"] == "completed"

    # 7. Member B attempts to reject action2 -> 403 Forbidden
    rej_res_b = await client.post(
        f"/api/v1/agents/actions/{action2_id}/reject",
        headers=headers_b,
    )
    assert rej_res_b.status_code == 403
    assert "Insufficient permissions" in rej_res_b.text

    # 8. Member A rejects action2 -> 200 OK
    rej_res_a = await client.post(
        f"/api/v1/agents/actions/{action2_id}/reject",
        headers=headers_a,
    )
    assert rej_res_a.status_code == 200
    assert rej_res_a.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_task_cancel_rbac(client: AsyncClient):
    """Verify that regular members cannot cancel another user's agent task."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cancel_owner@phase14.ai",
            "password": "Password123!",
            "full_name": "Cancel Owner",
            "workspace_name": "Cancel Security WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Creator) and Member B
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cancel_author@phase14.ai",
            "password": "Password123!",
            "full_name": "Cancel Author",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_a_id = reg_a.json()["data"]["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cancel_unauth@phase14.ai",
            "password": "Password123!",
            "full_name": "Cancel Unauth",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    for uid in [user_a_id, user_b_id]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 3. Member A creates task
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Long Running Computation", "goal": "Analyze workspace trends over time"},
        headers=headers_a,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["data"]["id"]

    # 4. Member B attempts to cancel Member A's task -> 403 Forbidden
    can_res_b = await client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=headers_b,
    )
    assert can_res_b.status_code == 403
    assert "Insufficient permissions" in can_res_b.text

    # 5. Member A cancels their own task -> 200 OK
    can_res_a = await client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=headers_a,
    )
    assert can_res_a.status_code == 200
    assert can_res_a.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_agent_webhook_ssrf_protection_on_approval(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that approving a trigger_webhook action blocks SSRF targets like AWS metadata or localhost."""
    ws_id = auth_headers["X-Workspace-ID"]

    # 1. Create a task
    t_res = await client.post(
        "/api/v1/agents/tasks",
        json={
            "title": "Webhook Dispatcher",
            "goal": "Notify external service upon task completion",
        },
        headers=auth_headers,
    )
    assert t_res.status_code == 201
    task_id = t_res.json()["data"]["id"]

    # 2. Insert action checkpoint targeting cloud metadata IP
    async with core_db.async_session_factory() as db:
        action = AgentAction(
            task_id=task_id,
            workspace_id=ws_id,
            tool_name="trigger_webhook",
            tool_input={"target_url": "http://169.254.169.254/latest/meta-data/"},
            risk_level="high",
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        action_id = action.id

    # 3. User attempts to approve the webhook action -> should be BLOCKED by SSRF defense
    appr_res = await client.post(
        f"/api/v1/agents/actions/{action_id}/approve",
        headers=auth_headers,
    )
    assert appr_res.status_code == 400
    assert "SSRF" in appr_res.text or "restricted" in appr_res.text


@pytest.mark.asyncio
async def test_agent_propose_memory_credential_sanitization(
    auth_headers: dict[str, str],
):
    """Verify that autonomous memory proposals sanitize sensitive tokens before persisting."""
    from unittest.mock import AsyncMock, patch

    from app.ai.base import LLMResponse

    ws_id = auth_headers["X-Workspace-ID"]

    async with core_db.async_session_factory() as db:
        # Create a task
        task = AgentTask(
            workspace_id=ws_id,
            user_id="test_user",
            title="Credential Discovery Test",
            goal="Identify and record configuration parameters",
            status=TaskStatus.RUNNING,
            steps_limit=5,
            steps_taken=0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # Mock LLM to return a propose_memory action containing raw secrets
        raw_secret_text = (
            "Discovered OpenAI sk-proj-1234567890abcdef1234567890 and AWS AKIAIOSFODNN7EXAMPLE"
        )
        mock_response = LLMResponse(
            content=f'```json\n{{"action": "call_tool", "tool": "propose_memory", "parameters": {{"content": "{raw_secret_text}", "category": "project", "importance": 8}}}}\n```',
            model="mock-agent",
        )

        mock_llm = AsyncMock()
        mock_llm.generate_text.return_value = mock_response

        with patch("app.services.agent_service.get_llm_provider", return_value=mock_llm):
            stepped_task = await AgentService.execute_task_step(
                db=db,
                workspace_id=ws_id,
                task_id=task.id,
            )

        assert stepped_task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED)

        # Verify the created memory has redacted credentials
        mem_q = (
            select(Memory).where(Memory.workspace_id == ws_id).order_by(Memory.created_at.desc())
        )
        mem = (await db.execute(mem_q)).scalars().first()
        assert mem is not None
        assert "sk-proj-" not in mem.content
        assert "AKIAIOSFODNN7EXAMPLE" not in mem.content
        assert "[REDACTED_OPENAI_KEY]" in mem.content
        assert "[REDACTED_AWS_KEY]" in mem.content


@pytest.mark.asyncio
async def test_agent_cross_tenant_isolation(client: AsyncClient):
    """Verify that agent tasks and actions are strictly isolated between different workspaces."""
    # 1. Register Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_a_agent@test.ai",
            "password": "Password123!",
            "full_name": "Tenant A Agent",
            "workspace_name": "Workspace A Agent",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a_id = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_a_id}

    # 2. Register Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_b_agent@test.ai",
            "password": "Password123!",
            "full_name": "Tenant B Agent",
            "workspace_name": "Workspace B Agent",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b_id = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b_id}

    # 3. Tenant A creates a task
    res_task = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Private Tenant A Task", "goal": "Analyze secret corporate roadmap"},
        headers=headers_a,
    )
    assert res_task.status_code == 201
    task_id = res_task.json()["data"]["id"]

    # 4. Insert an action for Tenant A
    async with core_db.async_session_factory() as db:
        action = AgentAction(
            task_id=task_id,
            workspace_id=ws_a_id,
            tool_name="delete_memory",
            tool_input={"memory_id": "dummy_secret_id"},
            risk_level="high",
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        action_id = action.id

    # 5. Tenant B attempts cross-tenant access -> All return 404 Not Found
    get_res = await client.get(f"/api/v1/agents/tasks/{task_id}", headers=headers_b)
    assert get_res.status_code == 404

    cancel_res = await client.post(f"/api/v1/agents/tasks/{task_id}/cancel", headers=headers_b)
    assert cancel_res.status_code == 404

    appr_res = await client.post(f"/api/v1/agents/actions/{action_id}/approve", headers=headers_b)
    assert appr_res.status_code == 404

    rej_res = await client.post(f"/api/v1/agents/actions/{action_id}/reject", headers=headers_b)
    assert rej_res.status_code == 404
