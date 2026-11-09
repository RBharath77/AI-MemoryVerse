import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_superuser,
    get_current_active_user,
    get_current_workspace,
    get_db,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.billing import (
    AuditChainVerificationResponse,
    AuditEventResponse,
    MerkleAuditRootRequest,
    MerkleAuditRootResponse,
    MerkleProofRequest,
    MerkleProofResponse,
    MerkleProofVerificationRequest,
    MerkleProofVerificationResponse,
    SystemOverviewResponse,
)
from app.schemas.common import APIResponse
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/overview", response_model=APIResponse[SystemOverviewResponse])
async def get_system_overview(
    current_user: User = Depends(get_current_active_superuser),
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


@router.get("/audit-logs/verify-chain", response_model=APIResponse[AuditChainVerificationResponse])
async def verify_audit_logs_chain(
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AuditChainVerificationResponse]:
    """Cryptographically verify the audit log hash chain to detect any tampering or deletion.

    Enforces RBAC: workspace OWNER, ADMIN, or platform superuser.
    """
    is_admin = current_user.is_superuser
    if not is_admin:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators and owners can verify cryptographic audit chains.",
        )

    ws_filter = None if current_user.is_superuser else workspace.id
    result = await AdminService.verify_audit_hash_chain(db=db, workspace_id=ws_filter)
    return APIResponse(success=True, data=AuditChainVerificationResponse(**result))


@router.get("/audit-logs/export")
async def export_audit_logs(
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    action: str | None = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(500, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Export compliance audit logs in JSON or CSV format.

    Enforces RBAC: workspace OWNER, ADMIN, or platform superuser.
    """
    is_admin = current_user.is_superuser
    if not is_admin:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators and owners can export audit trails.",
        )

    ws_filter = None if current_user.is_superuser else workspace.id
    logs = await AdminService.export_audit_logs(
        db=db,
        workspace_id=ws_filter,
        from_date=from_date,
        to_date=to_date,
        action=action,
        limit=limit,
    )

    if format == "csv":
        import csv
        import io

        from fastapi.responses import Response

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "workspace_id", "user_id", "action", "ip_address", "created_at"])
        for evt in logs:
            writer.writerow(
                [
                    evt.id,
                    evt.workspace_id or "",
                    evt.user_id or "",
                    evt.action,
                    evt.ip_address or "",
                    evt.created_at.isoformat() if evt.created_at else "",
                ]
            )
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-logs-export.csv"},
        )

    # JSON export
    events_data = [evt.model_dump(mode="json") for evt in logs]
    export_payload = {
        "workspace_id": workspace.id,
        "count": len(events_data),
        "exported_at": datetime.now(UTC).isoformat(),
        "exported_by": current_user.id,
        "events": events_data,
    }
    serialized = json.dumps(export_payload, sort_keys=True)
    integrity_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    export_payload["integrity_sha256"] = integrity_sha256

    return APIResponse(success=True, data=export_payload)


@router.post("/audit-logs/merkle-root", response_model=APIResponse[MerkleAuditRootResponse])
async def compute_audit_merkle_root(
    data: MerkleAuditRootRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MerkleAuditRootResponse]:
    """
    Compute cryptographic Merkle Tree root across recorded audit events.
    Enforces RBAC: workspace OWNER, ADMIN, or platform superuser.
    """

    is_admin = current_user.is_superuser
    if not is_admin:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators and owners can generate cryptographic Merkle roots.",
        )

    ws_id = None if (current_user.is_superuser and data.workspace_id == "all") else workspace.id
    result = await AdminService.compute_merkle_root(
        db=db,
        workspace_id=ws_id,
        start_date=data.start_date,
        end_date=data.end_date,
        action_filter=data.action_filter,
    )
    return APIResponse(success=True, data=result)


@router.post("/audit-logs/merkle-proof", response_model=APIResponse[MerkleProofResponse])
async def generate_audit_merkle_proof(
    data: MerkleProofRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MerkleProofResponse]:
    """
    Generate cryptographic Merkle inclusion audit path for a single audit event.
    Enforces RBAC: workspace OWNER, ADMIN, or platform superuser.
    """
    is_admin = current_user.is_superuser
    if not is_admin:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators and owners can generate Merkle inclusion proofs.",
        )

    ws_id = None if (current_user.is_superuser and data.workspace_id == "all") else workspace.id
    proof_res = await AdminService.generate_merkle_proof(
        db=db,
        event_id=data.event_id,
        workspace_id=ws_id,
    )
    if not proof_res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event '{data.event_id}' not found in specified workspace audit log.",
        )

    return APIResponse(success=True, data=proof_res)


@router.post(
    "/audit-logs/verify-merkle-proof",
    response_model=APIResponse[MerkleProofVerificationResponse],
)
async def verify_audit_merkle_proof(
    data: MerkleProofVerificationRequest,
    current_user: User = Depends(get_current_active_user),
) -> APIResponse[MerkleProofVerificationResponse]:
    """
    Zero-knowledge cryptographic verification of a Merkle inclusion proof.
    Verifies that leaf_hash is certified in expected merkle_root without disclosing other records.
    """
    verification = AdminService.verify_merkle_proof(
        leaf_hash=data.leaf_hash,
        merkle_root=data.merkle_root,
        audit_path=data.audit_path,
    )
    return APIResponse(success=True, data=verification)
