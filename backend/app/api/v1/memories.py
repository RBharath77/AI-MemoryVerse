from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.memory import MemoryCategory, MemoryStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.memory import (
    MemoryAnalyticsResponse,
    MemoryConsolidateRequest,
    MemoryCreate,
    MemoryExtractionRequest,
    MemoryExtractionResponse,
    MemoryFeedbackCreate,
    MemoryFeedbackResponse,
    MemoryImportRequest,
    MemoryImportResponse,
    MemoryLinkCreate,
    MemoryLinkResponse,
    MemoryResponse,
    MemoryTimelineResponse,
    MemoryUpdate,
    MemoryVersionResponse,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["Memories"])


@router.get("", response_model=APIResponse[PaginatedResponse[MemoryResponse]])
async def list_memories(
    category: MemoryCategory | None = None,
    status_filter: MemoryStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    is_pinned: bool | None = None,
    active_only: bool = Query(
        default=False, description="Filter for currently active/unexpired memories"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    items, total = await MemoryService.list_memories(
        db=db,
        workspace_id=current_workspace.id,
        category=category,
        status=status_filter,
        search=search,
        is_pinned=is_pinned,
        active_only=active_only,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=[MemoryResponse.model_validate(m) for m in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post("", response_model=APIResponse[MemoryResponse], status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    memory = await MemoryService.create_memory(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(memory),
    )


@router.get("/timeline", response_model=APIResponse[MemoryTimelineResponse])
async def get_timeline(
    limit: int = Query(default=100, ge=1, le=500),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    events = await MemoryService.get_timeline(db, current_workspace.id, limit=limit)
    return APIResponse(
        success=True,
        data=MemoryTimelineResponse(
            events=events,
            total=len(events),
        ),
    )


@router.get("/analytics", response_model=APIResponse[MemoryAnalyticsResponse])
async def get_analytics(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    stats = await MemoryService.get_analytics(db, current_workspace.id)
    return APIResponse(
        success=True,
        data=MemoryAnalyticsResponse(**stats),
    )


@router.get("/export")
async def export_memories(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    content, media_type = await MemoryService.export_memories(
        db=db,
        workspace_id=current_workspace.id,
        export_format=format,
    )
    filename = f"memories-{current_workspace.slug}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=APIResponse[MemoryImportResponse])
async def import_memories(
    data: MemoryImportRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    imported, skipped = await MemoryService.import_memories(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        items=data.memories,
    )
    return APIResponse(
        success=True,
        data=MemoryImportResponse(
            imported_count=imported,
            duplicates_skipped=skipped,
            total_processed=len(data.memories),
        ),
    )


@router.post("/extract", response_model=APIResponse[MemoryExtractionResponse])
async def extract_memories(
    data: MemoryExtractionRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await MemoryService.extract_and_store_memories(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post("/consolidate", response_model=APIResponse[MemoryResponse])
async def consolidate_memories(
    data: MemoryConsolidateRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    consolidated = await MemoryService.consolidate_memories(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(consolidated),
    )


@router.get("/{memory_id}", response_model=APIResponse[MemoryResponse])
async def get_memory(
    memory_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    memory = await MemoryService.get_memory(db, current_workspace.id, memory_id)
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(memory),
    )


@router.patch("/{memory_id}", response_model=APIResponse[MemoryResponse])
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    memory = await MemoryService.update_memory(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(memory),
    )


@router.delete("/{memory_id}", response_model=APIResponse[dict])
async def delete_memory(
    memory_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    await MemoryService.delete_memory(db, current_workspace.id, memory_id)
    return APIResponse(
        success=True,
        data={"message": "Memory deleted successfully."},
    )


@router.get("/{memory_id}/versions", response_model=APIResponse[list[MemoryVersionResponse]])
async def list_memory_versions(
    memory_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    versions = await MemoryService.get_versions(db, current_workspace.id, memory_id)
    return APIResponse(
        success=True,
        data=[MemoryVersionResponse.model_validate(v) for v in versions],
    )


@router.post("/{memory_id}/restore", response_model=APIResponse[MemoryResponse])
async def restore_memory_version(
    memory_id: str,
    version_number: int = Query(ge=1),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    restored = await MemoryService.restore_version(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
        version_number=version_number,
    )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(restored),
    )


@router.post("/{memory_id}/feedback", response_model=APIResponse[MemoryFeedbackResponse])
async def add_memory_feedback(
    memory_id: str,
    data: MemoryFeedbackCreate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    fb = await MemoryService.add_feedback(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        memory_id=memory_id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=MemoryFeedbackResponse.model_validate(fb),
    )


@router.post("/{memory_id}/links", response_model=APIResponse[MemoryLinkResponse])
async def create_memory_link(
    memory_id: str,
    data: MemoryLinkCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    link = await MemoryService.create_link(
        db=db,
        workspace_id=current_workspace.id,
        source_memory_id=memory_id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=MemoryLinkResponse.model_validate(link),
    )


@router.get("/{memory_id}/links", response_model=APIResponse[list[MemoryLinkResponse]])
async def list_memory_links(
    memory_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    links = await MemoryService.list_links(db, current_workspace.id, memory_id)
    return APIResponse(
        success=True,
        data=[MemoryLinkResponse.model_validate(lk) for lk in links],
    )
