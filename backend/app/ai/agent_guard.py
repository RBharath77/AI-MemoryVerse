import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import HybridSearchEngine
from app.core.sanitizer import CredentialSanitizer
from app.models.agent import AgentTask
from app.models.graph import GraphEntity
from app.models.memory import Memory, MemoryCategory, MemoryStatus
from app.services.url_service import WebpageImporter

logger = logging.getLogger(__name__)


class AgentGuardError(Exception):
    """Base exception for agent guardrail failures."""

    pass


class ToolValidationError(AgentGuardError):
    """Raised when tool parameters fail validation or exceed security boundaries."""

    pass


class ToolLoopDetectedError(AgentGuardError):
    """Raised when runaway repetitive tool invocation loop is detected."""

    pass


class ToolTimeoutError(AgentGuardError):
    """Raised when tool execution exceeds time limits."""

    pass


@dataclass
class GuardResult:
    params: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True
    error: str | None = None


class AgentToolExecutionGuard:
    """Security guardrails, parameter boundary enforcement, timeout bounding,

    and runaway loop prevention for autonomous agent tool invocations.
    """

    # Maximum query length for memory/document retrieval
    MAX_QUERY_LENGTH = 500
    # Maximum result count
    MAX_TOP_K = 25
    MIN_TOP_K = 1
    DEFAULT_TOP_K = 5
    # Maximum memory content length
    MAX_MEMORY_CONTENT = 4000
    # Maximum entity name length
    MAX_ENTITY_NAME_LENGTH = 150
    # Maximum consecutive identical tool executions before loop trigger
    MAX_CONSECUTIVE_IDENTICAL_CALLS = 2
    # Global tool call budget per task
    MAX_GLOBAL_TOOL_CALLS = 25

    @classmethod
    def clamp_and_validate_params(cls, tool_name: str, params: dict[str, Any]) -> GuardResult:
        """Enforce strict parameter types, clamping, and sanitization boundaries

        for the specified tool.
        """
        sanitized = dict(params or {})
        warnings: list[str] = []

        if tool_name in ("search_memories", "search_documents"):
            raw_query = str(sanitized.get("query", "")).strip()
            if not raw_query:
                raw_query = "knowledge base overview"
                warnings.append("Empty query substituted with default.")

            if len(raw_query) > cls.MAX_QUERY_LENGTH:
                raw_query = raw_query[: cls.MAX_QUERY_LENGTH]
                warnings.append(
                    f"Query exceeded {cls.MAX_QUERY_LENGTH} chars and was clamped.",
                )

            sanitized["query"] = raw_query

            # Clamp top_k
            raw_top_k = sanitized.get("top_k", cls.DEFAULT_TOP_K)
            try:
                top_k = int(raw_top_k)
            except (ValueError, TypeError):
                top_k = cls.DEFAULT_TOP_K
                warnings.append("Invalid top_k format, reverted to default.")

            if top_k > cls.MAX_TOP_K:
                top_k = cls.MAX_TOP_K
                warnings.append(f"top_k clamped to max {cls.MAX_TOP_K}.")
            elif top_k < cls.MIN_TOP_K:
                top_k = cls.MIN_TOP_K
                warnings.append(f"top_k clamped to min {cls.MIN_TOP_K}.")
            sanitized["top_k"] = top_k

            if "category" in sanitized and sanitized["category"]:
                cat = str(sanitized["category"]).strip()[:64]
                sanitized["category"] = cat

        elif tool_name == "lookup_knowledge_graph":
            entity_name = str(sanitized.get("entity_name", "")).strip()
            if not entity_name:
                return GuardResult(
                    params=sanitized,
                    is_valid=False,
                    error="Parameter 'entity_name' cannot be empty.",
                )
            if len(entity_name) > cls.MAX_ENTITY_NAME_LENGTH:
                entity_name = entity_name[: cls.MAX_ENTITY_NAME_LENGTH]
                warnings.append(f"entity_name clamped to {cls.MAX_ENTITY_NAME_LENGTH} chars.")
            sanitized["entity_name"] = entity_name

        elif tool_name == "fetch_web_url":
            raw_url = str(sanitized.get("url", "")).strip()
            if not raw_url.startswith(("http://", "https://")):
                return GuardResult(
                    params=sanitized,
                    is_valid=False,
                    error="URL must start with http:// or https://.",
                )
            sanitized["url"] = raw_url

        elif tool_name == "propose_memory":
            raw_content = str(sanitized.get("content", "")).strip()
            if not raw_content:
                return GuardResult(
                    params=sanitized,
                    is_valid=False,
                    error="Memory content cannot be empty.",
                )

            # Redact credentials and sensitive tokens from memory proposal
            sanitization = CredentialSanitizer.redact(raw_content)
            clean_content = sanitization.sanitized_text
            if sanitization.detected_types:
                warnings.append(
                    f"Sensitive credentials ({', '.join(sanitization.detected_types)}) in memory content were automatically redacted."
                )

            if len(clean_content) > cls.MAX_MEMORY_CONTENT:
                clean_content = clean_content[: cls.MAX_MEMORY_CONTENT]
                warnings.append(f"Memory content clamped to {cls.MAX_MEMORY_CONTENT} chars.")

            sanitized["content"] = clean_content

            # Clamp importance
            raw_imp = sanitized.get("importance", 5)
            try:
                imp = int(raw_imp)
                imp = max(1, min(10, imp))
            except (ValueError, TypeError):
                imp = 5
            sanitized["importance"] = imp

            # Validate category
            cat_val = str(sanitized.get("category", "semantic")).lower()
            valid_cats = {c.value for c in MemoryCategory}
            if cat_val not in valid_cats:
                cat_val = "semantic"
                warnings.append("Invalid category provided, defaulted to 'semantic'.")
            sanitized["category"] = cat_val

        elif tool_name == "delete_memory":
            mem_id = str(sanitized.get("memory_id", "")).strip()
            # Validate UUID format
            uuid_regex = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            if not re.match(uuid_regex, mem_id, re.IGNORECASE):
                return GuardResult(
                    params=sanitized,
                    is_valid=False,
                    error=f"Invalid memory_id format: '{mem_id}'. Expected UUID.",
                )
            sanitized["memory_id"] = mem_id

            reason = str(sanitized.get("reason", "")).strip()
            if len(reason) > 500:
                reason = reason[:500]
                warnings.append("Reason clamped to 500 chars.")
            sanitized["reason"] = reason

        elif tool_name == "trigger_webhook":
            target_url = str(sanitized.get("target_url", "")).strip()
            if not target_url.startswith(("http://", "https://")):
                return GuardResult(
                    params=sanitized,
                    is_valid=False,
                    error="target_url must be an HTTP or HTTPS URL.",
                )
            sanitized["target_url"] = target_url

        return GuardResult(params=sanitized, warnings=warnings, is_valid=True)

    @classmethod
    def check_loop_and_rate_limits(
        cls,
        task: AgentTask,
        proposed_tool: str,
        proposed_params: dict[str, Any],
    ) -> str | None:
        """Inspect task history to detect runaway repetitive tool execution loops

        or tool invocation budget exhaustion.
        Returns an error message if a violation is detected, or None if safe.
        """
        # 1. Budget check
        if task.steps_taken >= task.steps_limit:
            return f"Step limit of {task.steps_limit} reached for task."

        if task.steps_taken >= cls.MAX_GLOBAL_TOOL_CALLS:
            return f"Global task tool call budget of {cls.MAX_GLOBAL_TOOL_CALLS} exhausted."

        # 2. Runaway loop detection
        # Check the recent actions in task.actions
        if len(task.actions) >= cls.MAX_CONSECUTIVE_IDENTICAL_CALLS:
            recent = task.actions[-cls.MAX_CONSECUTIVE_IDENTICAL_CALLS :]
            all_same_tool = all(a.tool_name == proposed_tool for a in recent)
            if all_same_tool:
                # Compare tool inputs
                same_params = all(a.tool_input == proposed_params for a in recent)
                if same_params:
                    return (
                        f"Runaway loop detected: tool '{proposed_tool}' proposed with "
                        f"identical parameters {cls.MAX_CONSECUTIVE_IDENTICAL_CALLS} times consecutively."
                    )

        return None

    @classmethod
    async def execute_tool_with_timeout(
        cls,
        tool_name: str,
        params: dict[str, Any],
        workspace_id: str,
        task: AgentTask,
        db: AsyncSession,
        timeout_seconds: float = 15.0,
    ) -> tuple[dict[str, Any], float]:
        """Execute a low or medium risk tool under a bounded asynchronous timeout.

        Returns (tool_output, latency_ms).
        """
        start_t = time.perf_counter()

        async def _run() -> dict[str, Any]:
            if tool_name == "search_memories":
                q_text = params.get("query", task.goal[:50])
                top_k = params.get("top_k", cls.DEFAULT_TOP_K)
                results = await HybridSearchEngine.search(
                    db=db,
                    workspace_id=workspace_id,
                    query=q_text,
                    top_k=top_k,
                    include_memories=True,
                    include_documents=False,
                )
                return {
                    "found_count": len(results),
                    "items": [{"title": r.title, "content": r.content} for r in results],
                }

            elif tool_name == "search_documents":
                q_text = params.get("query", task.goal[:50])
                top_k = params.get("top_k", cls.DEFAULT_TOP_K)
                results = await HybridSearchEngine.search(
                    db=db,
                    workspace_id=workspace_id,
                    query=q_text,
                    top_k=top_k,
                    include_memories=False,
                    include_documents=True,
                )
                return {
                    "found_count": len(results),
                    "items": [{"title": r.title, "content": r.content} for r in results],
                }

            elif tool_name == "lookup_knowledge_graph":
                e_name = params.get("entity_name", "")
                q = select(GraphEntity).where(
                    GraphEntity.workspace_id == workspace_id,
                    GraphEntity.name.ilike(f"%{e_name}%"),
                )
                entity = (await db.execute(q)).scalar_one_or_none()
                if entity:
                    return {
                        "name": entity.name,
                        "entity_type": entity.entity_type.value,
                        "description": entity.description,
                        "mention_count": entity.mention_count,
                        "connected_edges": (
                            len(entity.outgoing_relationships) + len(entity.incoming_relationships)
                        ),
                    }
                return {"found": False, "message": f"Entity '{e_name}' not in graph."}

            elif tool_name == "fetch_web_url":
                target_url = params.get("url", "")
                web_res = await WebpageImporter.import_url(target_url)
                return {
                    "title": web_res["title"],
                    "word_count": web_res["word_count"],
                    "content_snippet": web_res["content"][:1000],
                }

            elif tool_name == "propose_memory":
                clean_content = params.get("content", "").strip()
                if clean_content:
                    mem = Memory(
                        workspace_id=workspace_id,
                        user_id=task.user_id,
                        content=clean_content,
                        category=MemoryCategory(params.get("category", "semantic")),
                        importance=params.get("importance", 5),
                        status=MemoryStatus.APPROVED,
                    )
                    db.add(mem)
                    await db.flush()
                    return {"memory_id": mem.id, "status": "approved"}
                return {"error": "Content cannot be empty."}

            else:
                return {"message": f"Tool '{tool_name}' executed successfully."}

        try:
            tool_output = await asyncio.wait_for(_run(), timeout=timeout_seconds)
        except TimeoutError:
            logger.warning(
                "Agent tool '%s' timed out after %.1f seconds on task '%s'",
                tool_name,
                timeout_seconds,
                task.id,
            )
            tool_output = {
                "error": f"Tool '{tool_name}' execution timed out after {timeout_seconds}s.",
                "timed_out": True,
            }
        except Exception as exc:
            logger.error("Agent tool '%s' failed: %s", tool_name, exc)
            tool_output = {"error": str(exc)}

        latency_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
        return tool_output, latency_ms
