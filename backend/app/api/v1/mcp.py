"""FastAPI router for Model Context Protocol (MCP) endpoints.

Supports:
- HTTP JSON-RPC 2.0 (POST /api/v1/mcp)
- MCP Server-Sent Events (GET /api/v1/mcp/sse)
- One-click client configurations (GET /api/v1/mcp/config)
- Tool definitions catalog (GET /api/v1/mcp/tools)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.mcp.server import MCPServer
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

router = APIRouter()
_mcp_instance = MCPServer()


@router.post("")
async def handle_mcp_post(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Execute JSON-RPC 2.0 MCP request over HTTP.

    Accepts single JSON-RPC 2.0 request or batch list of requests.
    Enforces multi-tenant workspace isolation with strict ownership validation.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: Invalid JSON"},
            },
        )

    # Resolve target workspace and enforce tenancy boundaries
    user_id = str(current_user.id)
    workspace_id = None
    header_ws = request.headers.get("X-Workspace-ID")

    if header_ws:
        try:
            target_ws_id = str(uuid.UUID(header_ws))
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32602, "message": "Invalid X-Workspace-ID header format."},
                },
            )

        # Verify caller has valid membership or is superuser
        if not current_user.is_superuser:
            check_q = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == target_ws_id,
                WorkspaceMember.user_id == current_user.id,
            )
            membership = (await db.execute(check_q)).scalar_one_or_none()
            if not membership:
                return JSONResponse(
                    status_code=403,
                    content={
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32000,
                            "message": "Forbidden: You are not an authorized member of this workspace.",
                        },
                    },
                )
        workspace_id = target_ws_id
    else:
        # Fall back to user's first available workspace membership or owned workspace
        ws_q = (
            select(WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == current_user.id)
            .limit(1)
        )
        first_ws = (await db.execute(ws_q)).scalar_one_or_none()
        if not first_ws:
            owned_q = select(Workspace.id).where(Workspace.owner_id == current_user.id).limit(1)
            first_ws = (await db.execute(owned_q)).scalar_one_or_none()
        if not first_ws:
            return JSONResponse(
                status_code=404,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32001,
                        "message": "User does not have an active workspace.",
                    },
                },
            )
        workspace_id = str(first_ws)

    # Handle batch or single
    if isinstance(body, list):
        results = []
        for req in body:
            resp = await _mcp_instance.handle_request(
                req, workspace_id=workspace_id, user_id=user_id
            )
            if resp:
                results.append(resp)
        return JSONResponse(content=results)
    elif isinstance(body, dict):
        resp = await _mcp_instance.handle_request(body, workspace_id=workspace_id, user_id=user_id)
        return JSONResponse(content=resp)
    else:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request"},
            },
        )


@router.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """Server-Sent Events endpoint conforming to MCP SSE transport specification."""

    async def event_generator():
        # MCP SSE standard: announce the message submission endpoint
        endpoint_uri = "/api/v1/mcp"
        yield f"event: endpoint\ndata: {endpoint_uri}\n\n"

        # Keep-alive heartbeat loop
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(15)
                yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tools")
async def get_mcp_tools(
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Return catalog of available MCP tools and schemas."""
    return {
        "success": True,
        "protocol": "mcp",
        "version": "2024-11-05",
        "server": "ai-memoryverse",
        "tools": _mcp_instance.tool_definitions,
        "resources": _mcp_instance.resource_definitions,
    }


@router.get("/config")
async def get_mcp_client_configurations(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Generate ready-to-copy configurations for Claude Desktop, Cursor, and Antigravity."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    python_bin = sys.executable
    script_path = os.path.join(repo_root, "mcp_server.py")
    http_base = str(request.base_url).rstrip("/") + "/api/v1/mcp"

    claude_desktop_snippet = {
        "mcpServers": {
            "ai-memoryverse": {
                "command": python_bin,
                "args": [script_path],
                "env": {
                    "PYTHONPATH": os.path.join(repo_root, "backend"),
                },
            }
        }
    }

    cursor_snippet = {
        "mcpServers": {
            "ai-memoryverse": {
                "command": python_bin,
                "args": [script_path],
            }
        }
    }

    http_snippet = {
        "name": "ai-memoryverse",
        "url": http_base,
        "type": "http-jsonrpc",
    }

    return {
        "success": True,
        "claude_desktop": claude_desktop_snippet,
        "cursor": cursor_snippet,
        "http_client": http_snippet,
        "paths": {
            "python_executable": python_bin,
            "script_path": script_path,
            "workspace_root": repo_root,
        },
    }
