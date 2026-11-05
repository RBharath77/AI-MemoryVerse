import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.memory import Memory, MemoryCategory, MemoryStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.agent import (
    AgentActionResponse,
    AgentTaskCreate,
    AgentTaskListResponse,
    AgentTaskResponse,
    URLImportRequest,
    URLImportResponse,
)
from app.schemas.common import APIResponse
from app.services.agent_service import AgentService
from app.services.url_service import WebpageImporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/tasks", response_model=APIResponse[AgentTaskListResponse])
async def list_agent_tasks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskListResponse]:
    """List autonomous agent tasks executed in the current workspace."""
    tasks, total = await AgentService.list_tasks(
        db=db,
        workspace_id=current_workspace.id,
        limit=limit,
        offset=offset,
    )
    items = [
        AgentTaskResponse(
            id=t.id,
            workspace_id=t.workspace_id,
            user_id=t.user_id,
            title=t.title,
            goal=t.goal,
            status=t.status.value,
            steps_limit=t.steps_limit,
            steps_taken=t.steps_taken,
            result_summary=t.result_summary,
            error_message=t.error_message,
            actions=[
                AgentActionResponse(
                    id=a.id,
                    task_id=a.task_id,
                    tool_name=a.tool_name,
                    tool_input=a.tool_input,
                    tool_output=a.tool_output,
                    risk_level=a.risk_level,
                    approval_status=a.approval_status.value,
                    execution_latency_ms=a.execution_latency_ms,
                    created_at=a.created_at,
                )
                for a in t.actions
            ],
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]
    return APIResponse(success=True, data=AgentTaskListResponse(items=items, total=total))


@router.post(
    "/tasks",
    response_model=APIResponse[AgentTaskResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_task(
    data: AgentTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskResponse]:
    """Launch a controlled autonomous agent task with step limits and permission gating."""
    task = await AgentService.create_task(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=AgentTaskResponse(
            id=task.id,
            workspace_id=task.workspace_id,
            user_id=task.user_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            steps_limit=task.steps_limit,
            steps_taken=task.steps_taken,
            result_summary=task.result_summary,
            error_message=task.error_message,
            actions=[
                AgentActionResponse(
                    id=a.id,
                    task_id=a.task_id,
                    tool_name=a.tool_name,
                    tool_input=a.tool_input,
                    tool_output=a.tool_output,
                    risk_level=a.risk_level,
                    approval_status=a.approval_status.value,
                    execution_latency_ms=a.execution_latency_ms,
                    created_at=a.created_at,
                )
                for a in task.actions
            ],
            created_at=task.created_at,
            updated_at=task.updated_at,
        ),
    )


@router.get("/tasks/{task_id}", response_model=APIResponse[AgentTaskResponse])
async def get_agent_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskResponse]:
    """Get full details and execution audit logs for a specific agent task."""
    task = await AgentService.get_task(
        db=db,
        workspace_id=current_workspace.id,
        task_id=task_id,
    )
    return APIResponse(
        success=True,
        data=AgentTaskResponse(
            id=task.id,
            workspace_id=task.workspace_id,
            user_id=task.user_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            steps_limit=task.steps_limit,
            steps_taken=task.steps_taken,
            result_summary=task.result_summary,
            error_message=task.error_message,
            actions=[
                AgentActionResponse(
                    id=a.id,
                    task_id=a.task_id,
                    tool_name=a.tool_name,
                    tool_input=a.tool_input,
                    tool_output=a.tool_output,
                    risk_level=a.risk_level,
                    approval_status=a.approval_status.value,
                    execution_latency_ms=a.execution_latency_ms,
                    created_at=a.created_at,
                )
                for a in task.actions
            ],
            created_at=task.created_at,
            updated_at=task.updated_at,
        ),
    )


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[AgentTaskResponse])
async def cancel_agent_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskResponse]:
    """Halt an autonomous agent task."""
    task = await AgentService.cancel_task(
        db=db,
        workspace_id=current_workspace.id,
        task_id=task_id,
    )
    return APIResponse(
        success=True,
        data=AgentTaskResponse(
            id=task.id,
            workspace_id=task.workspace_id,
            user_id=task.user_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            steps_limit=task.steps_limit,
            steps_taken=task.steps_taken,
            result_summary=task.result_summary,
            error_message=task.error_message,
            actions=[],
            created_at=task.created_at,
            updated_at=task.updated_at,
        ),
    )


@router.post("/actions/{action_id}/approve", response_model=APIResponse[AgentTaskResponse])
async def approve_action_checkpoint(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskResponse]:
    """Explicit human-in-the-loop approval to execute a high-risk consequential agent tool."""
    task = await AgentService.approve_action(
        db=db,
        workspace_id=current_workspace.id,
        action_id=action_id,
        user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=AgentTaskResponse(
            id=task.id,
            workspace_id=task.workspace_id,
            user_id=task.user_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            steps_limit=task.steps_limit,
            steps_taken=task.steps_taken,
            result_summary=task.result_summary,
            error_message=task.error_message,
            actions=[
                AgentActionResponse(
                    id=a.id,
                    task_id=a.task_id,
                    tool_name=a.tool_name,
                    tool_input=a.tool_input,
                    tool_output=a.tool_output,
                    risk_level=a.risk_level,
                    approval_status=a.approval_status.value,
                    execution_latency_ms=a.execution_latency_ms,
                    created_at=a.created_at,
                )
                for a in task.actions
            ],
            created_at=task.created_at,
            updated_at=task.updated_at,
        ),
    )


@router.post("/actions/{action_id}/reject", response_model=APIResponse[AgentTaskResponse])
async def reject_action_checkpoint(
    action_id: str,
    reason: str = Query("Rejected by user.", description="Reason for rejection"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[AgentTaskResponse]:
    """Explicit human-in-the-loop rejection of a high-risk agent tool."""
    task = await AgentService.reject_action(
        db=db,
        workspace_id=current_workspace.id,
        action_id=action_id,
        user_id=current_user.id,
        reason=reason,
    )
    return APIResponse(
        success=True,
        data=AgentTaskResponse(
            id=task.id,
            workspace_id=task.workspace_id,
            user_id=task.user_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            steps_limit=task.steps_limit,
            steps_taken=task.steps_taken,
            result_summary=task.result_summary,
            error_message=task.error_message,
            actions=[
                AgentActionResponse(
                    id=a.id,
                    task_id=a.task_id,
                    tool_name=a.tool_name,
                    tool_input=a.tool_input,
                    tool_output=a.tool_output,
                    risk_level=a.risk_level,
                    approval_status=a.approval_status.value,
                    execution_latency_ms=a.execution_latency_ms,
                    created_at=a.created_at,
                )
                for a in task.actions
            ],
            created_at=task.created_at,
            updated_at=task.updated_at,
        ),
    )


@router.post("/import-url", response_model=APIResponse[URLImportResponse])
async def import_web_url(
    data: URLImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[URLImportResponse]:
    """Safely fetch and import external webpage text with SSRF protection."""
    result = await WebpageImporter.import_url(data.url)

    doc_id = None
    if data.ingest_as_document and result.get("content"):
        # Automatically record as a semantic memory if requested
        mem = Memory(
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            content=f"Imported from {result['url']}: {result['content'][:500]}",
            category=MemoryCategory.SEMANTIC,
            importance=7,
            status=MemoryStatus.APPROVED,
        )
        db.add(mem)
        await db.commit()
        doc_id = mem.id

    return APIResponse(
        success=True,
        data=URLImportResponse(
            url=result["url"],
            title=result["title"],
            content=result["content"],
            word_count=result["word_count"],
            document_id=doc_id,
        ),
    )
