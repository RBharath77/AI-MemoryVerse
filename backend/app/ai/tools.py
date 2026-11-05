import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ActionRiskLevel(enum.StrEnum):
    LOW = "low"  # Read-only search, lookup, safe extraction (automatic)
    MEDIUM = "medium"  # Safe external web fetch, draft proposal (automatic)
    HIGH = "high"  # Consequential or destructive (requires user approval)


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: ActionRiskLevel
    parameters_schema: dict[str, Any]
    handler: Callable[..., Any] | None = None


class MemorySearchParams(BaseModel):
    query: str = Field(..., description="Query terms to search memories for")
    category: str | None = Field(default=None, description="Optional category filter")


class DocumentSearchParams(BaseModel):
    query: str = Field(..., description="Query terms to search uploaded documents for")


class GraphLookupParams(BaseModel):
    entity_name: str = Field(
        ...,
        description="Name of the entity to look up in the knowledge graph",
    )


class WebFetchParams(BaseModel):
    url: str = Field(..., description="Public HTTP/HTTPS URL of the webpage to fetch")


class ProposeMemoryParams(BaseModel):
    content: str = Field(..., description="Memory fact statement to record")
    category: str = Field(default="semantic", description="Memory category")
    importance: int = Field(default=5, ge=1, le=10, description="Importance score 1-10")


class DeleteMemoryParams(BaseModel):
    memory_id: str = Field(..., description="ID of the memory to delete permanently")
    reason: str = Field(..., description="Explanation why this memory should be removed")


class TriggerWebhookParams(BaseModel):
    target_url: str = Field(..., description="External webhook URL to dispatch notification to")
    payload: dict[str, Any] = Field(default_factory=dict, description="Payload data to send")


class ToolRegistry:
    """Central registry of tools executable by autonomous agent workflows."""

    _tools: dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, tool: ToolDefinition) -> None:
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> ToolDefinition | None:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[ToolDefinition]:
        return list(cls._tools.values())

    @classmethod
    def get_definitions_for_prompt(cls) -> str:
        """Format available tools into structured JSON documentation for LLM prompt context."""
        lines = []
        for t in cls._tools.values():
            risk_badge = "[REQUIRES APPROVAL]" if t.risk_level == ActionRiskLevel.HIGH else "[AUTO]"
            lines.append(
                f"- Tool: `{t.name}` {risk_badge}\n"
                f"  Description: {t.description}\n"
                f"  Parameters: {t.parameters_schema}"
            )
        return "\n\n".join(lines)


# Pre-register built-in agent tools
ToolRegistry.register(
    ToolDefinition(
        name="search_memories",
        description="Search user-approved long-term memories using hybrid retrieval.",
        risk_level=ActionRiskLevel.LOW,
        parameters_schema=MemorySearchParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="search_documents",
        description="Search parsed knowledge documents and chunk passages in the workspace.",
        risk_level=ActionRiskLevel.LOW,
        parameters_schema=DocumentSearchParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="lookup_knowledge_graph",
        description="Query the workspace knowledge graph for an entity and its connections.",
        risk_level=ActionRiskLevel.LOW,
        parameters_schema=GraphLookupParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="fetch_web_url",
        description="Fetch a public webpage URL with SSRF protection and extract text.",
        risk_level=ActionRiskLevel.MEDIUM,
        parameters_schema=WebFetchParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="propose_memory",
        description="Propose recording a new memory fact into the workspace.",
        risk_level=ActionRiskLevel.LOW,
        parameters_schema=ProposeMemoryParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="delete_memory",
        description="Permanently delete a memory record from the vault. HIGH RISK action.",
        risk_level=ActionRiskLevel.HIGH,
        parameters_schema=DeleteMemoryParams.model_json_schema(),
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="trigger_webhook",
        description="Dispatch an external webhook notification. HIGH RISK action.",
        risk_level=ActionRiskLevel.HIGH,
        parameters_schema=TriggerWebhookParams.model_json_schema(),
    )
)
