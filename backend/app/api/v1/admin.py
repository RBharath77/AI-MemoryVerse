from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_current_workspace,
    get_db,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.billing import AuditEventResponse, SystemOverviewResponse
from app.schemas.common import APIResponse
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/overview", response_model=APIResponse[SystemOverviewResponse])
async def get_system_overview(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SystemOverviewResponse]:
    """Retrieve system-wide telemetry, health checks, and subscription distributions."""
    overview = await AdminService.get_system_overview(db)
    return APIResponse(data=overview)


@router.get("/audit-logs", response_model=APIResponse[list[AuditEventResponse]])
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[AuditEventResponse]]:
    """Retrieve operational and security audit log trail."""
    # If superuser, can view all; otherwise view workspace-scoped logs
    ws_filter = None if current_user.is_superuser else workspace.id
    logs = await AdminService.get_audit_logs(db, limit=limit, workspace_id=ws_filter, action=action)
    return APIResponse(data=logs)
