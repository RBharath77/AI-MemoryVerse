import pytest
from httpx import AsyncClient

from app.mcp.server import MCPServer


@pytest.mark.asyncio
async def test_mcp_initialize():
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "claude-ai", "version": "1.0"},
        },
    }
    resp = await server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]
    assert resp["result"]["serverInfo"]["name"] == "ai-memoryverse"


@pytest.mark.asyncio
async def test_mcp_ping():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
    resp = await server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    assert resp["result"] == {}


@pytest.mark.asyncio
async def test_mcp_tools_list():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
    resp = await server.handle_request(req)
    assert "result" in resp
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "memoryverse_search" in tool_names
    assert "memoryverse_add_memory" in tool_names
    assert "memoryverse_get_graph" in tool_names
    assert "memoryverse_list_documents" in tool_names
    assert "memoryverse_get_stats" in tool_names
    assert "memoryverse_review_inbox" in tool_names


@pytest.mark.asyncio
async def test_mcp_resources_list_and_read(auth_headers: dict[str, str]):
    ws_id = auth_headers["X-Workspace-ID"]
    server = MCPServer(default_workspace_id=ws_id)

    # 1. List
    list_req = {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}}
    list_resp = await server.handle_request(list_req)
    assert "resources" in list_resp["result"]
    uris = [r["uri"] for r in list_resp["result"]["resources"]]
    assert "memoryverse://vault/recent" in uris
    assert "memoryverse://stats" in uris

    # 2. Read stats resource
    read_req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "resources/read",
        "params": {"uri": "memoryverse://stats"},
    }
    read_resp = await server.handle_request(read_req, workspace_id=ws_id)
    assert "contents" in read_resp["result"]
    assert "verified_memories" in read_resp["result"]["contents"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_execute_tools(auth_headers: dict[str, str]):
    ws_id = auth_headers["X-Workspace-ID"]
    server = MCPServer(default_workspace_id=ws_id)

    # 1. Add memory
    add_req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "memoryverse_add_memory",
            "arguments": {
                "content": "Antigravity and Claude collaborate via MCP protocol seamlessly.",
                "category": "project",
                "importance": 8,
                "tags": ["mcp", "ai"],
            },
        },
    }
    add_resp = await server.handle_request(add_req, workspace_id=ws_id)
    assert not add_resp["result"]["isError"]
    content_text = add_resp["result"]["content"][0]["text"]
    assert "Memory successfully stored" in content_text
    assert "Antigravity and Claude" in content_text

    # 2. Search
    search_req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "memoryverse_search",
            "arguments": {"query": "Antigravity Claude MCP"},
        },
    }
    search_resp = await server.handle_request(search_req, workspace_id=ws_id)
    assert not search_resp["result"]["isError"]
    search_text = search_resp["result"]["content"][0]["text"]
    assert "Found" in search_text or "Antigravity" in search_text

    # 3. Stats
    stats_req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "memoryverse_get_stats", "arguments": {}},
    }
    stats_resp = await server.handle_request(stats_req, workspace_id=ws_id)
    stats_text = stats_resp["result"]["content"][0]["text"]
    assert "AI-MemoryVerse Vault Statistics:" in stats_text
    assert "Verified Memories:" in stats_text


@pytest.mark.asyncio
async def test_mcp_api_endpoints(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    # 1. GET /api/v1/mcp/tools
    res_tools = await client.get("/api/v1/mcp/tools", headers=auth_headers)
    assert res_tools.status_code == 200
    data_tools = res_tools.json()
    assert data_tools["success"] is True
    assert len(data_tools["tools"]) >= 6

    # 2. GET /api/v1/mcp/config
    res_conf = await client.get("/api/v1/mcp/config", headers=auth_headers)
    assert res_conf.status_code == 200
    data_conf = res_conf.json()
    assert "claude_desktop" in data_conf
    assert "cursor" in data_conf
    assert "mcp_server.py" in str(data_conf["paths"]["script_path"])

    # 3. POST /api/v1/mcp (HTTP JSON-RPC)
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {
            "name": "memoryverse_get_stats",
            "arguments": {},
        },
    }
    res_rpc = await client.post("/api/v1/mcp", json=rpc_payload, headers=auth_headers)
    assert res_rpc.status_code == 200
    rpc_data = res_rpc.json()
    assert rpc_data["id"] == 100
    assert "result" in rpc_data
    assert "Vault Statistics" in rpc_data["result"]["content"][0]["text"]
