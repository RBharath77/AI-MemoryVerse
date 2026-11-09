import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.research import ReportType
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.common import APIResponse
from app.schemas.research import (
    InsightListResponse,
    InsightResponse,
    NarrativeSynthesisRequest,
    NarrativeSynthesisResponse,
    ReportGenerateRequest,
    ReportListResponse,
    ReportResponse,
)
from app.services.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/reports", response_model=APIResponse[ReportListResponse])
async def list_reports(
    report_type: ReportType | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[ReportListResponse]:
    """List research reports generated in the current workspace."""
    reports, total = await ResearchService.get_reports(
        db=db,
        workspace_id=current_workspace.id,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )
    items = [
        ReportResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            user_id=r.user_id,
            title=r.title,
            topic=r.topic,
            report_type=r.report_type.value,
            status=r.status.value,
            content_markdown=r.content_markdown,
            key_findings=r.key_findings,
            action_items=r.action_items,
            sources_used=r.sources_used,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return APIResponse(success=True, data=ReportListResponse(items=items, total=total))


@router.post("/generate", response_model=APIResponse[ReportResponse])
async def generate_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[ReportResponse]:
    """Generate a multi-document research synthesis, daily digest, or topic brief."""
    report = await ResearchService.generate_report(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=ReportResponse(
            id=report.id,
            workspace_id=report.workspace_id,
            user_id=report.user_id,
            title=report.title,
            topic=report.topic,
            report_type=report.report_type.value,
            status=report.status.value,
            content_markdown=report.content_markdown,
            key_findings=report.key_findings,
            action_items=report.action_items,
            sources_used=report.sources_used,
            created_at=report.created_at,
        ),
    )


@router.post("/narrative-synthesis", response_model=APIResponse[NarrativeSynthesisResponse])
async def synthesize_contextual_narrative(
    data: NarrativeSynthesisRequest,
    db: AsyncSession = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[NarrativeSynthesisResponse]:
    """
    Contextual Narrative Memory Synthesis & Executive Storytelling.
    Structures multi-source workspace memories and knowledge graph milestones into a
    coherent, multi-act chronological narrative briefing with grounded citations.
    """
    from app.ai.narrative_synthesis import NarrativeSynthesisEngine

    result = await NarrativeSynthesisEngine.synthesize(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.get("/reports/{report_id}", response_model=APIResponse[ReportResponse])
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[ReportResponse]:
    """Get a specific research report by ID."""
    report = await ResearchService.get_report(
        db=db,
        workspace_id=current_workspace.id,
        report_id=report_id,
    )
    return APIResponse(
        success=True,
        data=ReportResponse(
            id=report.id,
            workspace_id=report.workspace_id,
            user_id=report.user_id,
            title=report.title,
            topic=report.topic,
            report_type=report.report_type.value,
            status=report.status.value,
            content_markdown=report.content_markdown,
            key_findings=report.key_findings,
            action_items=report.action_items,
            sources_used=report.sources_used,
            created_at=report.created_at,
        ),
    )


@router.delete("/reports/{report_id}", response_model=APIResponse[dict[str, Any]])
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[dict[str, Any]]:
    """Delete a research report (creator, admin, or owner only)."""
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    await ResearchService.delete_report(
        db=db,
        workspace_id=current_workspace.id,
        report_id=report_id,
        current_user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner,
    )
    return APIResponse(success=True, data={"deleted": True})


@router.get("/insights", response_model=APIResponse[InsightListResponse])
async def list_insights(
    include_dismissed: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[InsightListResponse]:
    """List proactive smart knowledge insights."""
    insights, total = await ResearchService.get_insights(
        db=db,
        workspace_id=current_workspace.id,
        include_dismissed=include_dismissed,
    )
    items = [
        InsightResponse(
            id=i.id,
            workspace_id=i.workspace_id,
            insight_type=i.insight_type.value,
            title=i.title,
            description=i.description,
            suggested_action=i.suggested_action,
            related_entity_id=i.related_entity_id,
            related_memory_ids=i.related_memory_ids,
            is_dismissed=i.is_dismissed,
            created_at=i.created_at,
        )
        for i in insights
    ]
    return APIResponse(success=True, data=InsightListResponse(items=items, total=total))


@router.post("/insights/refresh", response_model=APIResponse[InsightListResponse])
async def refresh_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[InsightListResponse]:
    """Scan the memory vault and knowledge graph to regenerate smart insights."""
    insights = await ResearchService.refresh_insights(
        db=db,
        workspace_id=current_workspace.id,
    )
    items = [
        InsightResponse(
            id=i.id,
            workspace_id=i.workspace_id,
            insight_type=i.insight_type.value,
            title=i.title,
            description=i.description,
            suggested_action=i.suggested_action,
            related_entity_id=i.related_entity_id,
            related_memory_ids=i.related_memory_ids,
            is_dismissed=i.is_dismissed,
            created_at=i.created_at,
        )
        for i in insights
    ]
    return APIResponse(success=True, data=InsightListResponse(items=items, total=len(items)))


@router.post("/insights/{insight_id}/dismiss", response_model=APIResponse[InsightResponse])
async def dismiss_insight(
    insight_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[InsightResponse]:
    """Dismiss a knowledge insight."""
    insight = await ResearchService.dismiss_insight(
        db=db,
        workspace_id=current_workspace.id,
        insight_id=insight_id,
    )
    return APIResponse(
        success=True,
        data=InsightResponse(
            id=insight.id,
            workspace_id=insight.workspace_id,
            insight_type=insight.insight_type.value,
            title=insight.title,
            description=insight.description,
            suggested_action=insight.suggested_action,
            related_entity_id=insight.related_entity_id,
            related_memory_ids=insight.related_memory_ids,
            is_dismissed=insight.is_dismissed,
            created_at=insight.created_at,
        ),
    )


@router.post(
    "/narrative-synthesis",
    response_model=APIResponse[NarrativeSynthesisResponse],
)
async def synthesize_narrative(
    data: NarrativeSynthesisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[NarrativeSynthesisResponse]:
    """
    Contextual Narrative Memory Synthesis & Executive Storytelling Engine.
    Structures multi-source workspace memories into a coherent, multi-act chronological narrative briefing.
    """
    from app.ai.narrative_synthesis import NarrativeSynthesisEngine

    result = await NarrativeSynthesisEngine.synthesize(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)
