from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.memory import MemoryCategory, MemoryStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.memory import MemoryCreate, MemoryResponse, MemoryUpdate
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["Memories"])


@router.get("", response_model=APIResponse[PaginatedResponse[MemoryResponse]])
async def list_memories(
    category: MemoryCategory | None = None,
    status_filter: MemoryStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
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
