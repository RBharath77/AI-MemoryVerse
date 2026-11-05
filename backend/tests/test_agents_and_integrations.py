import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.core.ssrf import validate_url_safe
from app.services.url_service import WebpageImporter


def test_ssrf_protection_guardrails():
    # Loopback targets
    with pytest.raises(HTTPException) as exc_info:
        validate_url_safe("http://127.0.0.1:8000/api/v1/health")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException):
        validate_url_safe("http://localhost:8000")

    # Cloud metadata target
    with pytest.raises(HTTPException):
        validate_url_safe("http://169.254.169.254/latest/meta-data/")

    # Unsupported scheme
    with pytest.raises(HTTPException):
        validate_url_safe("ftp://ftp.example.com/file.txt")

    # Private RFC 1918 range
    with pytest.raises(HTTPException):
        validate_url_safe("http://192.168.1.1/admin")

    with pytest.raises(HTTPException):
        validate_url_safe("http://10.0.0.5:9000/secret")


def test_webpage_html_cleaner():
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>FastAPI and Next.js Best Practices</title>
        <style>body { color: red; }</style>
        <script>alert("malicious script");</script>
      </head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <h1>System Architecture Overview</h1>
        <p>AI-MemoryVerse is built with Next.js 14, FastAPI, and PostgreSQL.</p>
        <footer>Copyright 2026 MemoryVerse Inc</footer>
      </body>
    </html>
    """
    title, text = WebpageImporter._clean_html(sample_html)
    assert title == "FastAPI and Next.js Best Practices"
    assert "malicious script" not in text
    assert "System Architecture Overview" in text
    assert "AI-MemoryVerse is built with Next.js 14" in text
    assert "Copyright" not in text


@pytest.mark.asyncio
async def test_agent_task_creation_and_execution(client: AsyncClient, auth_headers: dict):
    # Seed a memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Python 3.11 with FastAPI provides high performance asynchronous routing.",
            "category": "technology",
            "importance": 8,
        },
        headers=auth_headers,
    )

    # Launch autonomous agent task
    res = await client.post(
        "/api/v1/agents/tasks",
        json={
            "title": "Analyze Python Architecture",
            "goal": (
                "Search our knowledge vault for Python technologies "
                "and summarize key advantages."
            ),
            "steps_limit": 5,
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    task = res.json()["data"]
    task_id = task["id"]
    assert task["title"] == "Analyze Python Architecture"
    assert task["steps_taken"] >= 1
    assert task["status"] in ("running", "completed")

    # List tasks
    list_res = await client.get("/api/v1/agents/tasks", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert any(t["id"] == task_id for t in items)

    # Get single task with action logs
    get_res = await client.get(f"/api/v1/agents/tasks/{task_id}", headers=auth_headers)
    assert get_res.status_code == 200
    details = get_res.json()["data"]
    assert len(details["actions"]) >= 1
    assert details["actions"][0]["tool_name"] == "search_memories"


@pytest.mark.asyncio
async def test_human_in_the_loop_approval_checkpoint(client: AsyncClient, auth_headers: dict):
    # 1. Seed memory to be deleted
    mem_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Temporary obsolete draft note to be pruned by agent.",
            "category": "episodic",
            "importance": 3,
        },
        headers=auth_headers,
    )
    memory_id = mem_res.json()["data"]["id"]

    # 2. Launch task that triggers high-risk delete_memory
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={
            "title": "Prune Obsolete Notes",
            "goal": f"Please delete_memory {memory_id} because it is obsolete.",
            "steps_limit": 5,
        },
        headers=auth_headers,
    )
    assert task_res.status_code == 201
    task_data = task_res.json()["data"]
    assert task_data["status"] == "waiting_approval"
    assert len(task_data["actions"]) >= 1
    action_id = task_data["actions"][0]["id"]

    # 3. User Approves Checkpoint
    appr_res = await client.post(
        f"/api/v1/agents/actions/{action_id}/approve",
        headers=auth_headers,
    )
    assert appr_res.status_code == 200
    updated_task = appr_res.json()["data"]
    assert updated_task["status"] == "completed"

    # 4. Verify target memory was actually deleted
    mem_check = await client.get(f"/api/v1/memories/{memory_id}", headers=auth_headers)
    assert mem_check.status_code == 404


@pytest.mark.asyncio
async def test_human_in_the_loop_rejection_checkpoint(client: AsyncClient, auth_headers: dict):
    # Launch task that triggers high-risk trigger_webhook
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={
            "title": "Dispatch External Webhook",
            "goal": "Please trigger_webhook to notify external monitoring system.",
            "steps_limit": 5,
        },
        headers=auth_headers,
    )
    assert task_res.status_code == 201
    task_data = task_res.json()["data"]
    assert task_data["status"] == "waiting_approval"
    assert len(task_data["actions"]) >= 1
    action_id = task_data["actions"][0]["id"]

    # Reject action
    rej_res = await client.post(
        f"/api/v1/agents/actions/{action_id}/reject?reason=PermissionDenied",
        headers=auth_headers,
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["data"]["status"] == "completed"
    assert "rejected by user" in rej_res.json()["data"]["result_summary"]


@pytest.mark.asyncio
async def test_api_token_management_lifecycle(client: AsyncClient, auth_headers: dict):
    # 1. Create API Token
    create_res = await client.post(
        "/api/v1/tokens",
        json={
            "name": "CI Deployment Bot",
            "scopes": ["memories:read", "memories:write", "search"],
            "expires_in_days": 30,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    token_data = create_res.json()["data"]
    token_id = token_data["id"]
    plaintext_token = token_data["token"]
    assert plaintext_token.startswith("mv_live_")
    assert token_data["name"] == "CI Deployment Bot"

    # 2. List API Tokens
    list_res = await client.get("/api/v1/tokens", headers=auth_headers)
    assert list_res.status_code == 200
    tokens = list_res.json()["data"]
    assert any(t["id"] == token_id for t in tokens)
    # Ensure plaintext token is NOT exposed in list view
    found_token = next(t for t in tokens if t["id"] == token_id)
    assert "token" not in found_token
    assert found_token["token_prefix"].startswith("mv_live_")

    # 3. Revoke API Token
    rev_res = await client.delete(f"/api/v1/tokens/{token_id}", headers=auth_headers)
    assert rev_res.status_code == 200
    assert rev_res.json()["data"]["revoked"] is True

    # Confirm token is excluded from active tokens
    after_res = await client.get("/api/v1/tokens", headers=auth_headers)
    assert not any(t["id"] == token_id for t in after_res.json()["data"])


@pytest.mark.asyncio
async def test_agents_and_tokens_multi_tenant_isolation(client: AsyncClient, auth_headers: dict):
    # User 1 creates task and token
    task_res = await client.post(
        "/api/v1/agents/tasks",
        json={"title": "Private Tenant Task", "goal": "Confidential goal"},
        headers=auth_headers,
    )
    task_id = task_res.json()["data"]["id"]

    tok_res = await client.post(
        "/api/v1/tokens",
        json={"name": "Tenant A Secret Key"},
        headers=auth_headers,
    )
    tok_id = tok_res.json()["data"]["id"]

    # Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_user_b@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Agent User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User B attempts to access User A's task -> 404
    view_task = await client.get(f"/api/v1/agents/tasks/{task_id}", headers=headers_b)
    assert view_task.status_code == 404

    # User B attempts to cancel User A's task -> 404
    cancel_task = await client.post(f"/api/v1/agents/tasks/{task_id}/cancel", headers=headers_b)
    assert cancel_task.status_code == 404

    # User B attempts to revoke User A's token -> 404
    del_tok = await client.delete(f"/api/v1/tokens/{tok_id}", headers=headers_b)
    assert del_tok.status_code == 404
