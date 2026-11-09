"""Model Context Protocol (MCP) Server for AI-MemoryVerse.

Provides JSON-RPC 2.0 stdio and HTTP/SSE tool execution enabling AI assistants
(Claude Desktop, Cursor, Antigravity) to query memories, save thoughts, explore the
knowledge graph, search documents, and inspect vault telemetry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.database as db_mod
from app.ai.retrieval import HybridSearchEngine
from app.models.document import Document
from app.models.graph import GraphEntity, GraphRelationship
from app.models.memory import Memory, MemoryCategory, MemoryReview, MemoryStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.memory import MemoryCreate
from app.services.graph_service import GraphService
from app.services.memory_service import MemoryService

logger = logging.getLogger("memoryverse.mcp")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-memoryverse"
SERVER_VERSION = "1.0.0"

# Category normalization mapping
CATEGORY_MAP: dict[str, MemoryCategory] = {
    "semantic": MemoryCategory.SEMANTIC,
    "general": MemoryCategory.SEMANTIC,
    "tech": MemoryCategory.SEMANTIC,
    "technical": MemoryCategory.SEMANTIC,
    "knowledge": MemoryCategory.SEMANTIC,
    "episodic": MemoryCategory.EPISODIC,
    "experience": MemoryCategory.EPISODIC,
    "event": MemoryCategory.EPISODIC,
    "history": MemoryCategory.EPISODIC,
    "project": MemoryCategory.PROJECT,
    "work": MemoryCategory.PROJECT,
    "task": MemoryCategory.PROJECT,
    "preference": MemoryCategory.PREFERENCE,
    "personal": MemoryCategory.PREFERENCE,
    "habit": MemoryCategory.PREFERENCE,
}


class MCPServer:
    """JSON-RPC 2.0 Model Context Protocol Server."""

    def __init__(
        self,
        default_workspace_id: str | None = None,
        default_user_id: str | None = None,
    ) -> None:
        self.default_workspace_id = default_workspace_id
        self.default_user_id = default_user_id

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """List of tools exposed to MCP AI clients."""
        return [
            {
                "name": "memoryverse_search",
                "description": (
                    "Search across personal memory vault and ingested documents using hybrid "
                    "(keyword + semantic vector) retrieval with Reciprocal Rank Fusion."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query or keywords to find.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 5).",
                            "default": 5,
                        },
                        "category": {
                            "type": "string",
                            "description": "Category filter: semantic, episodic, etc.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memoryverse_add_memory",
                "description": (
                    "Save a new long-term fact, insight, preference, decision, or note "
                    "directly into your AI-MemoryVerse external brain."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The information or thought to store permanently.",
                        },
                        "category": {
                            "type": "string",
                            "description": "Category: semantic, episodic, project, preference.",
                            "default": "semantic",
                        },
                        "importance": {
                            "type": "integer",
                            "description": "Importance rating from 1 (low) to 10 (critical).",
                            "default": 5,
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of tag keywords.",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "memoryverse_get_graph",
                "description": (
                    "Explore the knowledge graph. Fetches entity nodes, semantic clusters, "
                    "and directional relationships in your external brain."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Optional entity name to inspect its neighborhood.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum entities/relationships to return (default 25).",
                            "default": 25,
                        },
                    },
                },
            },
            {
                "name": "memoryverse_list_documents",
                "description": (
                    "List documents indexed, parsed, and chunked in the active workspace."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of documents to list (default 10).",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "memoryverse_get_stats",
                "description": (
                    "Get real-time telemetry: count of memories by status, ingested documents, "
                    "knowledge graph entities, and review inbox size."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "memoryverse_review_inbox",
                "description": (
                    "Retrieve pending candidate facts from the review inbox awaiting confirmation."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max pending facts to return (default 10).",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "memoryverse_get_insights",
                "description": (
                    "Retrieve proactive knowledge intelligence insights: stale memories, "
                    "contradiction alerts, trending architectural hubs, and knowledge gaps."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Whether to rescan vault and graph to detect new insights (default false).",
                            "default": False,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum insights to return (default 10, max 50).",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "memoryverse_generate_report",
                "description": (
                    "Synthesize a multi-source research report, daily knowledge digest, "
                    "or project brief using the AI-MemoryVerse research engine."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Subject or question to synthesize research for.",
                        },
                        "report_type": {
                            "type": "string",
                            "description": "Type: topic_research, daily_digest, weekly_summary, project_brief.",
                            "default": "topic_research",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Lookback window in days (default 30).",
                            "default": 30,
                        },
                    },
                    "required": ["topic"],
                },
            },
        ]

    @property
    def resource_definitions(self) -> list[dict[str, Any]]:
        """List of static resources exposed to MCP AI clients."""
        return [
            {
                "uri": "memoryverse://vault/recent",
                "name": "Recent Memories",
                "description": "The 10 most recent verified memories in your AI-MemoryVerse vault.",
                "mimeType": "application/json",
            },
            {
                "uri": "memoryverse://stats",
                "name": "Vault Telemetry",
                "description": "Real-time statistics of memories, documents, and graph links.",
                "mimeType": "application/json",
            },
            {
                "uri": "memoryverse://insights",
                "name": "Proactive Knowledge Insights",
                "description": "Live proactive intelligence insights and knowledge gap warnings.",
                "mimeType": "application/json",
            },
        ]

    async def resolve_tenancy(
        self,
        db: AsyncSession,
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> tuple[str, str]:
        """Resolve workspace and user ID, defaulting to DB owner if unprovided."""
        target_ws_id = workspace_id or self.default_workspace_id
        target_u_id = user_id or self.default_user_id

        if target_ws_id and target_u_id:
            return target_ws_id, target_u_id

        # If only workspace_id is provided, resolve its owner
        if target_ws_id:
            ws_res = await db.execute(select(Workspace).where(Workspace.id == target_ws_id))
            ws = ws_res.scalar_one_or_none()
            if ws:
                return ws.id, target_u_id or ws.owner_id

        # If only user_id is provided, resolve user's owned or joined workspace
        if target_u_id:
            owned_ws_res = await db.execute(
                select(Workspace)
                .where(Workspace.owner_id == target_u_id)
                .order_by(Workspace.created_at.asc())
                .limit(1)
            )
            owned_ws = owned_ws_res.scalar_one_or_none()
            if owned_ws:
                return owned_ws.id, target_u_id

        # Query first active workspace
        query = select(Workspace).order_by(Workspace.created_at.asc()).limit(1)
        res = await db.execute(query)
        ws = res.scalars().first()

        if not ws:
            # Create a bootstrap workspace & user for seamless out-of-the-box local stdio usage
            u_query = select(User).limit(1)
            u_res = await db.execute(u_query)
            user_rec = u_res.scalars().first()
            if not user_rec:
                user_rec = User(
                    email="mcp-user@memoryverse.local",
                    hashed_password="mcp_local_placeholder_disabled",
                    full_name="MCP AI Agent",
                    is_active=True,
                )
                db.add(user_rec)
                await db.flush()

            ws = Workspace(
                name="Primary Knowledge Vault",
                slug="primary-vault",
                owner_id=user_rec.id,
            )
            db.add(ws)
            await db.commit()
            return ws.id, user_rec.id

        return ws.id, ws.owner_id

    async def handle_request(
        self,
        request: dict[str, Any],
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a single JSON-RPC 2.0 request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {}) or {}

        # Handle notifications (no response required, or null response)
        if req_id is None:
            if method == "notifications/initialized":
                logger.info("MCP client initialized notification received.")
            return {}

        # Standard JSON-RPC 2.0 dispatch
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                        },
                        "serverInfo": {
                            "name": SERVER_NAME,
                            "version": SERVER_VERSION,
                        },
                    },
                }

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": self.tool_definitions},
                }

            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result_content = await self.execute_tool(
                    name=name,
                    args=arguments,
                    workspace_id=workspace_id,
                    user_id=user_id,
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result_content}],
                        "isError": False,
                    },
                }

            elif method == "resources/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"resources": self.resource_definitions},
                }

            elif method == "resources/read":
                uri = params.get("uri")
                content_str = await self.read_resource(
                    uri=uri, workspace_id=workspace_id, user_id=user_id
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": content_str,
                            }
                        ]
                    },
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: '{method}'",
                    },
                }

        except Exception as e:
            logger.exception("Error executing MCP method %s: %s", method, e)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal MCP server error: {str(e)}",
                },
            }

    async def execute_tool(
        self,
        name: str | None,
        args: dict[str, Any],
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Execute a specific MCP tool and return formatted text."""
        async with db_mod.async_session_factory() as db:
            ws_id, u_id = await self.resolve_tenancy(db, workspace_id, user_id)

            if name == "memoryverse_search":
                query = args.get("query", "").strip()
                if not query:
                    return "Error: query parameter is required."
                try:
                    limit = min(max(int(args.get("limit", 5)), 1), 50)
                except (TypeError, ValueError):
                    limit = 5
                category = args.get("category")

                results = await HybridSearchEngine.search(
                    db=db,
                    workspace_id=ws_id,
                    query=query,
                    top_k=limit,
                    filter_category=category,
                )

                if not results:
                    return f"No memories or documents matching '{query}' were found in your vault."

                lines = [f"Found {len(results)} relevant results for '{query}':\n"]
                for i, r in enumerate(results, 1):
                    tag = f"[{r.source_type.upper()}]"
                    cat = f" | {r.category}" if r.category else ""
                    score = f" (score: {r.score:.3f})"
                    lines.append(f"{i}. {tag}{cat}{score} {r.title or 'Untitled'}")
                    lines.append(f"   Excerpt: {r.content.strip()}\n")
                return "\n".join(lines).strip()

            elif name == "memoryverse_add_memory":
                content = args.get("content", "").strip()
                if not content:
                    return "Error: content parameter is required."

                # Deep Defense: redact credentials before storing via MCP
                from app.core.sanitizer import CredentialSanitizer

                content = CredentialSanitizer.redact(content).sanitized_text

                raw_cat = str(args.get("category", "semantic")).lower()
                category = CATEGORY_MAP.get(raw_cat, MemoryCategory.SEMANTIC)
                try:
                    importance = min(max(int(args.get("importance", 5)), 1), 10)
                except (TypeError, ValueError):
                    importance = 5
                tags = args.get("tags", [])

                mem_in = MemoryCreate(
                    content=content,
                    category=category,
                    importance=importance,
                    tags=tags,
                    source_type="mcp_assistant",
                )

                mem = await MemoryService.create_memory(
                    db=db,
                    workspace_id=ws_id,
                    user_id=u_id,
                    data=mem_in,
                )

                return (
                    f"Memory successfully stored in AI-MemoryVerse!\n"
                    f"- Memory ID: {mem.id}\n"
                    f"- Category: {mem.category.value}\n"
                    f"- Status: {mem.status.value}\n"
                    f"- Importance: {mem.importance}/10\n"
                    f"- Content: {mem.content}"
                )

            elif name == "memoryverse_get_graph":
                entity_query = args.get("entity")
                try:
                    limit = min(max(int(args.get("limit", 25)), 1), 100)
                except (TypeError, ValueError):
                    limit = 25

                if entity_query:
                    neighborhood = await GraphService.get_neighborhood(
                        db=db,
                        workspace_id=ws_id,
                        entity_name=entity_query.strip(),
                    )
                    nodes = neighborhood.get("nodes", [])
                    edges = neighborhood.get("edges", [])
                    if not nodes:
                        return f"Entity '{entity_query}' was not found in the knowledge graph."

                    lines = [f"Knowledge Graph neighborhood for '{entity_query}':\n"]
                    lines.append(f"Nodes ({len(nodes)}):")
                    for n in nodes:
                        lines.append(f"- {n.get('name')} [{n.get('entity_type', 'concept')}]")
                    lines.append(f"\nConnections ({len(edges)}):")
                    for e in edges:
                        lines.append(
                            f"- {e.get('source')} --({e.get('relation')})--> {e.get('target')}"
                        )
                    return "\n".join(lines)
                else:
                    graph_data = await GraphService.get_workspace_graph(
                        db=db,
                        workspace_id=ws_id,
                        limit=limit,
                    )
                    nodes = graph_data.get("nodes", [])
                    edges = graph_data.get("edges", [])
                    lines = [
                        f"AI-MemoryVerse Graph ({len(nodes)} entities, {len(edges)} relations):\n"
                    ]
                    for e in edges[:limit]:
                        lines.append(
                            f"- {e.get('source')} -[{e.get('relation')}]-> {e.get('target')}"
                        )
                    if not edges and nodes:
                        lines.append("Entities without explicit edges:")
                        for n in nodes[:limit]:
                            lines.append(f"- {n.get('name')} ({n.get('entity_type')})")
                    if not nodes and not edges:
                        lines.append("Knowledge graph is empty. Ingest memories to build graphs.")
                    return "\n".join(lines)

            elif name == "memoryverse_list_documents":
                try:
                    limit = min(max(int(args.get("limit", 10)), 1), 50)
                except (TypeError, ValueError):
                    limit = 10
                q = (
                    select(Document)
                    .where(Document.workspace_id == ws_id)
                    .order_by(Document.created_at.desc())
                    .limit(limit)
                )
                res = await db.execute(q)
                docs = res.scalars().all()

                if not docs:
                    return "No documents ingested in this workspace yet."

                lines = [f"Ingested Documents ({len(docs)}):\n"]
                for d in docs:
                    size_kb = (d.file_size or 0) / 1024
                    lines.append(
                        f"- {d.filename} | {d.mime_type or 'text'} | "
                        f"{size_kb:.1f} KB | {d.status} | ID: {d.id}"
                    )
                return "\n".join(lines)

            elif name == "memoryverse_get_stats":
                # Memories count
                mem_q = select(func.count(Memory.id)).where(
                    Memory.workspace_id == ws_id,
                    Memory.status == MemoryStatus.APPROVED,
                )
                mem_count = (await db.execute(mem_q)).scalar() or 0

                # Review inbox count
                rev_q = select(func.count(MemoryReview.id)).where(
                    MemoryReview.workspace_id == ws_id,
                    MemoryReview.review_status == "pending",
                )
                rev_count = (await db.execute(rev_q)).scalar() or 0

                # Document count
                doc_q = select(func.count(Document.id)).where(Document.workspace_id == ws_id)
                doc_count = (await db.execute(doc_q)).scalar() or 0

                # Entities & relations count
                ent_q = select(func.count(GraphEntity.id)).where(GraphEntity.workspace_id == ws_id)
                ent_count = (await db.execute(ent_q)).scalar() or 0

                rel_q = select(func.count(GraphRelationship.id)).where(
                    GraphRelationship.workspace_id == ws_id
                )
                rel_count = (await db.execute(rel_q)).scalar() or 0

                return (
                    f"AI-MemoryVerse Vault Statistics:\n"
                    f"- Verified Memories: {mem_count}\n"
                    f"- Review Inbox Queue: {rev_count} pending facts\n"
                    f"- Documents Ingested: {doc_count}\n"
                    f"- Knowledge Graph Entities: {ent_count}\n"
                    f"- Knowledge Graph Relations: {rel_count}\n"
                    f"- Workspace ID: {ws_id}\n"
                    f"- MCP Server: {SERVER_NAME} v{SERVER_VERSION}"
                )

            elif name == "memoryverse_review_inbox":
                try:
                    limit = min(max(int(args.get("limit", 10)), 1), 50)
                except (TypeError, ValueError):
                    limit = 10
                q = (
                    select(MemoryReview)
                    .where(
                        MemoryReview.workspace_id == ws_id,
                        MemoryReview.review_status == "pending",
                    )
                    .order_by(MemoryReview.created_at.desc())
                    .limit(limit)
                )
                res = await db.execute(q)
                reviews = res.scalars().all()

                if not reviews:
                    return "Review inbox is completely clear. No pending facts awaiting review."

                lines = [f"Pending Facts in Review Inbox ({len(reviews)}):\n"]
                for r in reviews:
                    lines.append(
                        f"- ID: {r.id}\n"
                        f"  Fact: {r.original_text}\n"
                        f"  Notes: {r.review_notes or 'Pending review'}\n"
                    )
                return "\n".join(lines).strip()

            elif name == "memoryverse_get_insights":
                from app.services.research_service import ResearchService

                refresh = bool(args.get("refresh", False))
                try:
                    limit = min(max(int(args.get("limit", 10)), 1), 50)
                except (TypeError, ValueError):
                    limit = 10

                if refresh:
                    insights = await ResearchService.refresh_insights(db=db, workspace_id=ws_id)
                else:
                    insights, _ = await ResearchService.get_insights(db=db, workspace_id=ws_id)

                if not insights:
                    return "No active knowledge insights found. Your vault is fully up to date."

                lines = [f"AI-MemoryVerse Knowledge Insights ({len(insights[:limit])}):\n"]
                for ins in insights[:limit]:
                    lines.append(f"- [{ins.insight_type.value.upper()}] {ins.title}")
                    lines.append(f"  Description: {ins.description}")
                    lines.append(f"  Suggested Action: {ins.suggested_action}\n")
                return "\n".join(lines).strip()

            elif name == "memoryverse_generate_report":
                from app.models.research import ReportType
                from app.schemas.research import ReportGenerateRequest
                from app.services.research_service import ResearchService

                topic = args.get("topic", "").strip()
                if not topic:
                    return "Error: topic parameter is required."

                raw_type = str(args.get("report_type", "topic_research")).lower().strip()
                try:
                    report_type = ReportType(raw_type)
                except ValueError:
                    report_type = ReportType.TOPIC_RESEARCH

                try:
                    days_back = min(max(int(args.get("days_back", 30)), 1), 365)
                except (TypeError, ValueError):
                    days_back = 30

                report_in = ReportGenerateRequest(
                    topic=topic,
                    report_type=report_type,
                    days_back=days_back,
                )
                report = await ResearchService.generate_report(
                    db=db,
                    workspace_id=ws_id,
                    user_id=u_id,
                    data=report_in,
                )
                return (
                    f"Report Generated Successfully!\n"
                    f"- Report ID: {report.id}\n"
                    f"- Title: {report.title}\n"
                    f"- Type: {report.report_type.value}\n\n"
                    f"{report.content_markdown}"
                )

            else:
                return f"Error: Unknown tool '{name}'."

    async def read_resource(
        self,
        uri: str | None,
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Read an MCP resource representation."""
        async with db_mod.async_session_factory() as db:
            ws_id, _ = await self.resolve_tenancy(db, workspace_id, user_id)

            if uri == "memoryverse://vault/recent":
                q = (
                    select(Memory)
                    .where(
                        Memory.workspace_id == ws_id,
                        Memory.status == MemoryStatus.APPROVED,
                    )
                    .order_by(Memory.updated_at.desc())
                    .limit(10)
                )
                res = await db.execute(q)
                mems = res.scalars().all()
                data = [
                    {
                        "id": m.id,
                        "content": m.content,
                        "category": m.category.value,
                        "importance": m.importance,
                        "tags": m.tags or [],
                        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                    }
                    for m in mems
                ]
                return json.dumps({"recent_memories": data}, indent=2)

            elif uri == "memoryverse://stats":
                mem_q = select(func.count(Memory.id)).where(
                    Memory.workspace_id == ws_id,
                    Memory.status == MemoryStatus.APPROVED,
                )
                doc_q = select(func.count(Document.id)).where(Document.workspace_id == ws_id)
                mem_count = (await db.execute(mem_q)).scalar() or 0
                doc_count = (await db.execute(doc_q)).scalar() or 0

                return json.dumps(
                    {
                        "workspace_id": ws_id,
                        "verified_memories": mem_count,
                        "documents": doc_count,
                        "protocol_version": PROTOCOL_VERSION,
                    },
                    indent=2,
                )

            elif uri == "memoryverse://insights":
                from app.services.research_service import ResearchService

                insights, _ = await ResearchService.get_insights(db=db, workspace_id=ws_id)
                data = [
                    {
                        "id": i.id,
                        "type": i.insight_type.value,
                        "title": i.title,
                        "description": i.description,
                        "suggested_action": i.suggested_action,
                        "created_at": i.created_at.isoformat() if i.created_at else None,
                    }
                    for i in insights
                ]
                return json.dumps({"knowledge_insights": data}, indent=2)

            return json.dumps({"error": f"Resource not found: {uri}"})

    async def run_stdio(self) -> None:
        """Run standard I/O JSON-RPC loop for Claude Desktop / Cursor / CLI."""
        sys.stderr.write(f"[{SERVER_NAME}] MCP stdio server started. Listening on stdin...\n")
        sys.stderr.flush()

        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line = await reader.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
            except json.JSONDecodeError as err:
                sys.stderr.write(f"[{SERVER_NAME}] JSON decode error: {err}\n")
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            response = await self.handle_request(request)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        sys.stderr.write(f"[{SERVER_NAME}] MCP stdio server terminated.\n")
        sys.stderr.flush()
