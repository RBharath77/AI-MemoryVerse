from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.memory import MemoryReviewAction, MemoryReviewResponse
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory-reviews", tags=["Memory Reviews"])


@router.get("", response_model=APIResponse[PaginatedResponse[MemoryReviewResponse]])
async def list_memory_reviews(
    status_filter: str | None = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    items, total = await MemoryService.list_reviews(
        db=db,
        workspace_id=current_workspace.id,
        status_filter=status_filter,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=[MemoryReviewResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post("/{review_id}/action", response_model=APIResponse[MemoryReviewResponse])
async def act_on_memory_review(
    review_id: str,
    action: MemoryReviewAction,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    review = await MemoryService.act_on_review(
        db=db,
        workspace_id=current_workspace.id,
        review_id=review_id,
        user_id=current_user.id,
        action=action,
    )
    return APIResponse(
        success=True,
        data=MemoryReviewResponse.model_validate(review),
    )
