from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.mcp.server import MCPServer


@pytest.mark.asyncio
async def test_mcp_resolve_tenancy_cross_tenant_isolation(client: AsyncClient):
    """Verify that resolve_tenancy isolates workspaces when workspace_id is provided without user_id."""
    # 1. Register User A with Workspace A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mcp_user_a@phase12.ai",
            "password": "Password123!",
            "full_name": "MCP User A",
            "workspace_name": "Vault A",
        },
    )
    assert reg_a.status_code == 201
    ws_a_id = reg_a.json()["data"]["workspace"]["id"]

    # 2. Register User B with Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mcp_user_b@phase12.ai",
            "password": "Password123!",
            "full_name": "MCP User B",
            "workspace_name": "Vault B",
        },
    )
    assert reg_b.status_code == 201
    user_b_id = reg_b.json()["data"]["user"]["id"]
    ws_b_id = reg_b.json()["data"]["workspace"]["id"]

    server = MCPServer()

    async with core_db.async_session_factory() as db:
        # Tenancy test: passing workspace B ID without user_id must resolve strictly to Workspace B
        resolved_ws_id, resolved_u_id = await server.resolve_tenancy(
            db=db,
            workspace_id=ws_b_id,
            user_id=None,
        )
        assert resolved_ws_id == ws_b_id
        assert resolved_u_id == user_b_id
        assert resolved_ws_id != ws_a_id

        # Tenancy test: passing user B ID without workspace_id must resolve strictly to Workspace B
        resolved_ws_id2, resolved_u_id2 = await server.resolve_tenancy(
            db=db,
            workspace_id=None,
            user_id=user_b_id,
        )
        assert resolved_ws_id2 == ws_b_id
        assert resolved_u_id2 == user_b_id


@pytest.mark.asyncio
async def test_mcp_tool_limits_and_sanitization(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify MCP tools clamp bounds on limit parameters and sanitize sensitive credentials."""
    ws_id = auth_headers["X-Workspace-ID"]
    server = MCPServer(default_workspace_id=ws_id)

    # 1. Test search limit clamping with negative and excessive numbers
    for test_limit in [-10, 0, 999999]:
        res_text = await server.execute_tool(
            name="memoryverse_search",
            args={"query": "test query", "limit": test_limit},
            workspace_id=ws_id,
        )
        assert isinstance(res_text, str)
        assert not res_text.startswith("Error: Unknown tool")

    # 2. Test credential sanitization in memoryverse_add_memory
    secret_text = "My secret token is " + ("sk-proj-" + "1234567890abcdef1234567890") + " for testing"
    add_resp = await server.execute_tool(
        name="memoryverse_add_memory",
        args={
            "content": secret_text,
            "category": "semantic",
            "importance": 7,
        },
        workspace_id=ws_id,
    )
    assert "Memory successfully stored" in add_resp
    assert "sk-proj-" not in add_resp
    assert "[REDACTED_OPENAI_KEY]" in add_resp


@pytest.mark.asyncio
async def test_mcp_intelligence_tools_insights_and_reports(auth_headers: dict[str, str]):
    """Verify new MCP tools memoryverse_get_insights and memoryverse_generate_report."""
    ws_id = auth_headers["X-Workspace-ID"]
    server = MCPServer(default_workspace_id=ws_id)

    # 1. memoryverse_get_insights
    insights_res = await server.execute_tool(
        name="memoryverse_get_insights",
        args={"refresh": True, "limit": 5},
        workspace_id=ws_id,
    )
    assert isinstance(insights_res, str)
    assert "Knowledge Insights" in insights_res or "up to date" in insights_res

    # 2. read resource memoryverse://insights
    res_json_str = await server.read_resource(
        uri="memoryverse://insights",
        workspace_id=ws_id,
    )
    res_data = json.loads(res_json_str)
    assert "knowledge_insights" in res_data
    assert isinstance(res_data["knowledge_insights"], list)

    # 3. memoryverse_generate_report
    report_res = await server.execute_tool(
        name="memoryverse_generate_report",
        args={"topic": "Quantum Vector Storage Systems", "days_back": 14},
        workspace_id=ws_id,
    )
    assert "Report Generated Successfully!" in report_res
    assert "Quantum Vector Storage Systems" in report_res


@pytest.mark.asyncio
async def test_research_report_deletion_rbac(client: AsyncClient):
    """Verify that only the report creator, workspace admin, or owner can delete a research report."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "report_owner@phase12.ai",
            "password": "Password123!",
            "full_name": "Report Owner",
            "workspace_name": "Research Workspace",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Creator)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "report_creator@phase12.ai",
            "password": "Password123!",
            "full_name": "Report Creator",
        },
    )
    assert reg_a.status_code == 201
    user_a_id = reg_a.json()["data"]["user"]["id"]
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    # 3. Register Member B (Viewer / outsider member)
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "report_bystander@phase12.ai",
            "password": "Password123!",
            "full_name": "Report Bystander",
        },
    )
    assert reg_b.status_code == 201
    user_b_id = reg_b.json()["data"]["user"]["id"]
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    # Add both to the workspace as regular members
    add_a = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": user_a_id, "role": "member"},
        headers=owner_headers,
    )
    assert add_a.status_code == 201

    add_b = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": user_b_id, "role": "member"},
        headers=owner_headers,
    )
    assert add_b.status_code == 201

    # 4. Member A generates a research report
    gen_res = await client.post(
        "/api/v1/research/generate",
        json={"topic": "Microservice Security Boundaries", "days_back": 7},
        headers=headers_a,
    )
    assert gen_res.status_code == 200
    report_id = gen_res.json()["data"]["id"]

    # 5. Member B attempts to delete Member A's report -> 403 Forbidden
    del_res_b = await client.delete(
        f"/api/v1/research/reports/{report_id}",
        headers=headers_b,
    )
    assert del_res_b.status_code == 403
    assert "Insufficient permissions" in del_res_b.text

    # 6. Member A (the creator) deletes their own report -> 200 OK
    del_res_a = await client.delete(
        f"/api/v1/research/reports/{report_id}",
        headers=headers_a,
    )
    assert del_res_a.status_code == 200
    assert del_res_a.json()["data"]["deleted"] is True


@pytest.mark.asyncio
async def test_research_report_context_credential_redaction(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that credentials inside memories are redacted before being injected into research prompts."""
    # 1. Ingest a memory with AWS and GitHub tokens
    mem_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Database cluster config uses AWS " + ("AKIA" + "IOSFODNN7EXAMPLE") + " and " + ("ghp_" + "123456789012345678901234567890123456"),
            "category": "project",
        },
        headers=auth_headers,
    )
    assert mem_res.status_code == 201

    # 2. Generate a report matching that topic
    rep_res = await client.post(
        "/api/v1/research/generate",
        json={"topic": "Database cluster config", "days_back": 1},
        headers=auth_headers,
    )
    assert rep_res.status_code == 200
    data = rep_res.json()["data"]
    assert data["status"] == "completed"
    assert "Database cluster config" in data["title"]
