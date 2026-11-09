from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.agent_event_bus import AgentEventBus
from app.ai.agent_guard import AgentToolExecutionGuard
from app.ai.base import LLMResponse
from app.core import database as core_db
from app.models.agent import ActionApprovalStatus, AgentAction, AgentTask, TaskStatus
from app.services.agent_service import AgentService


@pytest.fixture(autouse=True)
def clean_event_bus():
    """Ensure event bus is cleared before and after each test."""
    AgentEventBus.clear()
    yield
    AgentEventBus.clear()


@pytest.mark.asyncio
async def test_agent_guardrail_parameter_clamping_and_sanitization():
    """Verify AgentToolExecutionGuard clamps oversized parameters and enforces security boundaries."""
    # 1. Clamping oversized search queries
    huge_query = "quantum computing algorithms " * 50  # ~1500 chars
    guard_res = AgentToolExecutionGuard.clamp_and_validate_params(
        "search_memories",
        {"query": huge_query, "top_k": 999},
    )
    assert guard_res.is_valid is True
    assert len(guard_res.params["query"]) == 500
    assert guard_res.params["top_k"] == 25
    assert any("clamped" in w.lower() for w in guard_res.warnings)

    # 2. Clamping under-budget top_k
    guard_min = AgentToolExecutionGuard.clamp_and_validate_params(
        "search_documents",
        {"query": "valid query", "top_k": -5},
    )
    assert guard_min.params["top_k"] == 1

    # 3. Clamping entity names in graph lookup
    huge_entity = "E" * 300
    guard_graph = AgentToolExecutionGuard.clamp_and_validate_params(
        "lookup_knowledge_graph",
        {"entity_name": huge_entity},
    )
    assert guard_graph.is_valid is True
    assert len(guard_graph.params["entity_name"]) == 150

    # 4. Propose memory credential redaction and importance clamping
    secret_content = (
        "Production API keys: " + ("sk-proj-" + "1234567890abcdef1234567890") + " and AWS " + ("AKIA" + "IOSFODNN7EXAMPLE")
    )
    guard_mem = AgentToolExecutionGuard.clamp_and_validate_params(
        "propose_memory",
        {"content": secret_content, "importance": 99, "category": "non_existent_category"},
    )
    assert guard_mem.is_valid is True
    assert "sk-proj" not in guard_mem.params["content"]
    assert "[REDACTED_OPENAI_KEY]" in guard_mem.params["content"]
    assert guard_mem.params["importance"] == 10
    assert guard_mem.params["category"] == "semantic"
    assert len(guard_mem.warnings) >= 2

    # 5. Invalid UUID format for delete_memory
    guard_del = AgentToolExecutionGuard.clamp_and_validate_params(
        "delete_memory",
        {"memory_id": "not-a-valid-uuid", "reason": "test"},
    )
    assert guard_del.is_valid is False
    assert "Expected UUID" in guard_del.error

    # 6. Invalid URL scheme for webhook
    guard_webhook = AgentToolExecutionGuard.clamp_and_validate_params(
        "trigger_webhook",
        {"target_url": "ftp://malicious.internal.network"},
    )
    assert guard_webhook.is_valid is False
    assert "HTTP or HTTPS" in guard_webhook.error


@pytest.mark.asyncio
async def test_agent_guardrail_loop_detection_and_rate_limits():
    """Verify that repetitive tool execution with identical parameters triggers runaway loop abort."""
    task = AgentTask(
        id="task_loop_test",
        workspace_id="ws_loop",
        user_id="user_loop",
        title="Loop Detection Test",
        goal="Repeated search without progress",
        status=TaskStatus.RUNNING,
        steps_limit=10,
        steps_taken=2,
    )

    action1 = AgentAction(
        id="a1",
        task_id=task.id,
        workspace_id=task.workspace_id,
        tool_name="search_memories",
        tool_input={"query": "stuck in loop", "top_k": 5},
        approval_status=ActionApprovalStatus.APPROVED_AUTO,
    )
    action2 = AgentAction(
        id="a2",
        task_id=task.id,
        workspace_id=task.workspace_id,
        tool_name="search_memories",
        tool_input={"query": "stuck in loop", "top_k": 5},
        approval_status=ActionApprovalStatus.APPROVED_AUTO,
    )
    task.actions = [action1, action2]

    # Proposing the exact same tool and parameters a 3rd time triggers runaway loop detection
    loop_error = AgentToolExecutionGuard.check_loop_and_rate_limits(
        task=task,
        proposed_tool="search_memories",
        proposed_params={"query": "stuck in loop", "top_k": 5},
    )
    assert loop_error is not None
    assert "Runaway loop detected" in loop_error

    # Proposing a different parameter is permitted
    different_ok = AgentToolExecutionGuard.check_loop_and_rate_limits(
        task=task,
        proposed_tool="search_memories",
        proposed_params={"query": "progressing to new topic", "top_k": 5},
    )
    assert different_ok is None

    # Step limit enforcement
    task.steps_taken = 10
    limit_error = AgentToolExecutionGuard.check_loop_and_rate_limits(
        task=task,
        proposed_tool="search_memories",
        proposed_params={"query": "any"},
    )
    assert limit_error is not None
    assert "Step limit" in limit_error


@pytest.mark.asyncio
async def test_agent_guardrail_execution_timeout():
    """Verify that tool execution exceeding time limits is gracefully clamped with timeout metadata."""
    task = AgentTask(
        id="task_timeout_test",
        workspace_id="ws_timeout",
        user_id="user_timeout",
        title="Timeout Test",
        goal="Test slow tool",
        status=TaskStatus.RUNNING,
        steps_limit=5,
        steps_taken=0,
    )

    # Patch HybridSearchEngine.search to simulate a slow / hanging database call
    async def slow_search(*args, **kwargs):
        await asyncio.sleep(0.3)
        return []

    with patch("app.ai.agent_guard.HybridSearchEngine.search", side_effect=slow_search):
        output, latency = await AgentToolExecutionGuard.execute_tool_with_timeout(
            tool_name="search_memories",
            params={"query": "slow query", "top_k": 5},
            workspace_id="ws_timeout",
            task=task,
            db=AsyncMock(),
            timeout_seconds=0.05,  # 50ms timeout
        )

        assert output.get("timed_out") is True
        assert "timed out after 0.05s" in output.get("error", "")
        assert latency >= 40.0  # At least reached timeout threshold


@pytest.mark.asyncio
async def test_live_agent_step_event_bus_and_sse_streaming(client: AsyncClient):
    """Verify that agent execution milestones are broadcast in real-time over Server-Sent Events (SSE)."""
    # 1. Register User and Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_streamer@phase27.ai",
            "password": "Password123!",
            "full_name": "Agent Streamer",
            "workspace_name": "Streaming WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Create Task
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={
            "title": "Realtime Research Task",
            "goal": "Analyze project documentation and summarize",
        },
        headers=headers,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["data"]["id"]

    # 3. Simulate step execution with mocked LLM output
    mock_response = LLMResponse(
        content='```json\n{"action": "call_tool", "tool": "search_memories", "parameters": {"query": "system architecture", "top_k": 3}, "thought": "Need to understand system architecture first."}\n```',
        model="mock-agent",
    )
    mock_llm = AsyncMock()
    mock_llm.generate_text.return_value = mock_response

    with patch("app.services.agent_service.get_llm_provider", return_value=mock_llm):
        async with core_db.async_session_factory() as db:
            await AgentService.execute_task_step(db, ws_id, task_id)

    # 4. Stream events from the SSE endpoint
    stream_res = await client.get(
        f"/api/v1/agents/tasks/{task_id}/events/stream",
        headers=headers,
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]

    body = stream_res.text
    # Check that events adhere to SSE wire protocol
    assert "event: " in body
    assert "data: " in body

    # Verify key milestone events are present in history replay
    assert "event: action_planned" in body
    assert "event: step_completed" in body
    assert "search_memories" in body


@pytest.mark.asyncio
async def test_in_flight_task_cancellation_and_state_reconciliation(client: AsyncClient):
    """Verify that cancelling an agent task cleanly reconciles pending action checkpoints and notifies event bus."""
    # 1. Register User and Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_canceller@phase27.ai",
            "password": "Password123!",
            "full_name": "Agent Canceller",
            "workspace_name": "Cancellation WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Create Task
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Risky Deletion Pipeline", "goal": "Clean up vault"},
        headers=headers,
    )
    task_id = task_res.json()["data"]["id"]

    # 3. Insert a pending approval action
    async with core_db.async_session_factory() as db:
        pending_act = AgentAction(
            task_id=task_id,
            workspace_id=ws_id,
            tool_name="delete_memory",
            tool_input={"memory_id": "00000000-0000-0000-0000-000000000001", "reason": "obsolete"},
            risk_level="high",
            approval_status=ActionApprovalStatus.PENDING_APPROVAL,
        )
        db.add(pending_act)
        await db.commit()
        await db.refresh(pending_act)
        act_id = pending_act.id

    # 4. Cancel Task with reason
    cancel_res = await client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel?reason=User aborted deletion workflow",
        headers=headers,
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()["data"]
    assert cancel_data["status"] == "cancelled"
    assert "User aborted deletion workflow" in cancel_data["result_summary"]

    # 5. Verify pending action was reconciled to REJECTED_BY_USER
    async with core_db.async_session_factory() as db:
        act = (await db.execute(select(AgentAction).where(AgentAction.id == act_id))).scalar_one()
        assert act.approval_status == ActionApprovalStatus.REJECTED_BY_USER
        assert "cancelled due to task cancellation" in act.tool_output.get("error", "")

    # 6. Verify cancellation event was published
    history = AgentEventBus.get_history(task_id)
    cancelled_events = [e for e in history if e["event"] == "task_cancelled"]
    assert len(cancelled_events) == 1
    assert cancelled_events[0]["data"]["reconciled_pending_actions"] >= 1


@pytest.mark.asyncio
async def test_agent_orchestration_multi_tenant_and_rbac_isolation(client: AsyncClient):
    """Verify strict multi-tenant boundaries on agent event streaming and cancellation."""
    # 1. Register Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_a_agent@phase27.ai",
            "password": "Password123!",
            "full_name": "Tenant A",
            "workspace_name": "Tenant A WS",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_a}

    # 2. Register Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_b_agent@phase27.ai",
            "password": "Password123!",
            "full_name": "Tenant B",
            "workspace_name": "Tenant B WS",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b}

    # 3. Tenant A creates an agent task
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Tenant A Private Task", "goal": "Analyze secret tenant A data"},
        headers=headers_a,
    )
    task_a_id = task_res.json()["data"]["id"]

    # 4. Tenant B attempts to stream events from Tenant A's task -> 404 Not Found
    stream_res_b = await client.get(
        f"/api/v1/agents/tasks/{task_a_id}/events/stream",
        headers=headers_b,
    )
    assert stream_res_b.status_code == 404

    # 5. Tenant B attempts to cancel Tenant A's task -> 404 Not Found
    cancel_res_b = await client.post(
        f"/api/v1/agents/tasks/{task_a_id}/cancel",
        headers=headers_b,
    )
    assert cancel_res_b.status_code == 404
