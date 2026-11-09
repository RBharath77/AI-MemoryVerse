from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.common import APIResponse
from app.schemas.workspace import (
    CacheDependencyInvalidateRequest,
    CacheDependencyInvalidateResponse,
    CacheFreshnessResponse,
    ComplianceRemediateResponse,
    ComplianceScorecardResponse,
    DifferentialPrivacyMetricRequest,
    DifferentialPrivacyMetricResponse,
    MemoryDriftResponse,
    RAGBenchmarkResponse,
    RAGEvalHistoryResponse,
    RAGProbeRunRequest,
    TimelineDiffRequest,
    TimelineDiffResponse,
    TimeTravelSnapshotResponse,
    WorkspaceBenchmarkResponse,
    WorkspaceCMEKRotateResponse,
    WorkspaceCreate,
    WorkspaceCryptoShredResponse,
    WorkspaceDLPInspectRequest,
    WorkspaceDLPInspectResponse,
    WorkspaceDLPPolicyResponse,
    WorkspaceDLPPolicyUpdate,
    WorkspaceIPPolicyUpdate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceRetentionPolicyUpdate,
    WorkspaceSecretCreate,
    WorkspaceSecretResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=APIResponse[list[WorkspaceResponse]])
async def list_workspaces(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspaces = await WorkspaceService.get_user_workspaces(db, current_user.id)
    return APIResponse(
        success=True,
        data=[WorkspaceResponse.model_validate(w) for w in workspaces],
    )


@router.post("", response_model=APIResponse[WorkspaceResponse], status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.create_workspace(db, current_user, data)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/{workspace_id}", response_model=APIResponse[WorkspaceResponse])
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.patch("/{workspace_id}", response_model=APIResponse[WorkspaceResponse])
async def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.update_workspace(db, workspace_id, current_user.id, data)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/{workspace_id}/members", response_model=APIResponse[list[WorkspaceMemberResponse]])
async def list_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    members = await WorkspaceService.get_workspace_members(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=[WorkspaceMemberResponse.model_validate(m) for m in members],
    )


@router.post(
    "/{workspace_id}/members",
    response_model=APIResponse[WorkspaceMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: str,
    data: WorkspaceMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    member = await WorkspaceService.add_workspace_member(db, workspace_id, current_user.id, data)
    return APIResponse(
        success=True,
        data=WorkspaceMemberResponse.model_validate(member),
    )


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=APIResponse[WorkspaceMemberResponse],
)
async def update_workspace_member_role(
    workspace_id: str,
    user_id: str,
    data: WorkspaceMemberUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    member = await WorkspaceService.update_workspace_member_role(
        db, workspace_id, current_user.id, user_id, data.role
    )
    return APIResponse(
        success=True,
        data=WorkspaceMemberResponse.model_validate(member),
    )


@router.delete("/{workspace_id}/members/{user_id}", response_model=APIResponse[dict])
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await WorkspaceService.remove_workspace_member(db, workspace_id, current_user.id, user_id)
    return APIResponse(
        success=True,
        data={"message": "Member removed successfully."},
    )


@router.delete("/{workspace_id}", response_model=APIResponse[dict])
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a workspace permanently with full cascade cleanup (owner only)."""
    await WorkspaceService.delete_workspace(
        db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        is_superuser=current_user.is_superuser,
    )
    return APIResponse(
        success=True,
        data={"message": "Workspace and all associated resources permanently deleted."},
    )


@router.patch("/{workspace_id}/ip-policy", response_model=APIResponse[WorkspaceResponse])
async def update_workspace_ip_policy(
    workspace_id: str,
    data: WorkspaceIPPolicyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Configure or update authorized IPv4/IPv6 CIDR geofencing rules for this workspace."""
    workspace = await WorkspaceService.update_ip_policy(
        db, workspace_id, current_user.id, data.ip_allowlist
    )
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.patch("/{workspace_id}/retention-policy", response_model=APIResponse[WorkspaceResponse])
async def update_workspace_retention_policy(
    workspace_id: str,
    data: WorkspaceRetentionPolicyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Configure maximum lifetime retention days for unpinned workspace memories."""
    workspace = await WorkspaceService.update_retention_policy(
        db, workspace_id, current_user.id, data.retention_days
    )
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.post(
    "/{workspace_id}/secrets",
    response_model=APIResponse[WorkspaceSecretResponse],
    status_code=status.HTTP_201_CREATED,
)
async def store_workspace_secret(
    workspace_id: str,
    data: WorkspaceSecretCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Store an encrypted secret key or provider token under authenticated envelope encryption."""
    result = await WorkspaceService.store_secret(
        db, workspace_id, current_user.id, data.name, data.value
    )
    return APIResponse(
        success=True,
        data=WorkspaceSecretResponse(**result),
    )


@router.get(
    "/{workspace_id}/secrets",
    response_model=APIResponse[list[WorkspaceSecretResponse]],
)
async def list_workspace_secrets(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List stored workspace secrets with masked previews."""
    secrets = await WorkspaceService.list_secrets(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=[WorkspaceSecretResponse(**s) for s in secrets],
    )


@router.delete(
    "/{workspace_id}/secrets/{name}",
    response_model=APIResponse[dict],
)
async def delete_workspace_secret(
    workspace_id: str,
    name: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a secret key from workspace encrypted storage."""
    deleted = await WorkspaceService.delete_secret(db, workspace_id, current_user.id, name)
    return APIResponse(
        success=True,
        data={"deleted": deleted, "name": name},
    )


@router.post(
    "/{workspace_id}/retention/prune",
    response_model=APIResponse[dict],
)
async def prune_workspace_retention(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Prune and archive memories past their valid_until TTL or older than retention policy."""
    result = await WorkspaceService.prune_retention_memories(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=result,
    )


@router.get(
    "/{workspace_id}/cache/freshness",
    response_model=APIResponse[CacheFreshnessResponse],
)
async def get_workspace_cache_freshness(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    """Retrieve fine-grained semantic cache dependency freshness telemetry and hit/miss efficiency."""
    from app.ai.semantic_cache import SemanticCache

    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    stats = SemanticCache.get_freshness_telemetry(workspace_id)
    return APIResponse(
        success=True,
        data=CacheFreshnessResponse(**stats),
    )


@router.post(
    "/{workspace_id}/cache/invalidate-dependent",
    response_model=APIResponse[CacheDependencyInvalidateResponse],
)
async def invalidate_workspace_dependent_cache(
    workspace_id: str,
    data: CacheDependencyInvalidateRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    """Selectively invalidate only cached queries dependent on the updated memory or document IDs."""
    from datetime import UTC, datetime

    from app.ai.semantic_cache import SemanticCache

    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    purged_count = SemanticCache.invalidate_dependencies(workspace_id, data.dependency_ids)
    remaining = len(SemanticCache._workspace_keys.get(workspace_id, set()))

    return APIResponse(
        success=True,
        data=CacheDependencyInvalidateResponse(
            workspace_id=workspace_id,
            invalidated_keys_count=purged_count,
            remaining_entries_count=remaining,
            dependency_ids=data.dependency_ids,
            invalidated_at=datetime.now(UTC),
        ),
    )


@router.post(
    "/{workspace_id}/privacy/differentially-private-metrics",
    response_model=APIResponse[DifferentialPrivacyMetricResponse],
)
async def get_differentially_private_metrics(
    workspace_id: str,
    data: DifferentialPrivacyMetricRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute aggregate workspace metrics perturbed with calibrated Laplace noise
    satisfying formal (epsilon, delta)-differential privacy guarantees.
    """
    from app.core.differential_privacy import DifferentialPrivacyEngine

    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )

    result = await DifferentialPrivacyEngine.compute_private_metrics(
        db=db,
        workspace_id=workspace_id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/{workspace_id}/cmek/rotate",
    response_model=APIResponse[WorkspaceCMEKRotateResponse],
)
async def rotate_workspace_cmek_key(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Rotate customer-managed encryption key (CMEK) and re-encrypt all stored secrets under the new version."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.rotate_workspace_cmek(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceCMEKRotateResponse(**result),
    )


@router.post(
    "/{workspace_id}/cmek/crypto-shred",
    response_model=APIResponse[WorkspaceCryptoShredResponse],
)
async def crypto_shred_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Irreversibly crypto-shred all stored secrets and key material for this workspace (OWNER only)."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.crypto_shred_workspace(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceCryptoShredResponse(**result),
    )


@router.get(
    "/{workspace_id}/benchmark",
    response_model=APIResponse[WorkspaceBenchmarkResponse],
)
async def get_workspace_benchmark(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Measure real-time RAG retrieval latency, biological retention health, semantic cache hit-ratio, and readiness grade."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.get_benchmark_telemetry(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceBenchmarkResponse(**result),
    )


@router.post(
    "/{workspace_id}/eval/run-probe",
    response_model=APIResponse[RAGBenchmarkResponse],
)
async def run_workspace_rag_probe(
    workspace_id: str,
    data: RAGProbeRunRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Execute synthetic ground-truth retrieval probe benchmarking for context precision, recall, and groundedness."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.run_workspace_rag_probe(
        db=db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        sample_size=data.sample_size,
        top_k=data.top_k,
    )
    return APIResponse(
        success=True,
        data=RAGBenchmarkResponse(**result),
    )


@router.get(
    "/{workspace_id}/eval/history",
    response_model=APIResponse[RAGEvalHistoryResponse],
)
async def get_workspace_rag_eval_history(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical synthetic RAG retrieval probe runs."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.get_workspace_rag_eval_history(
        db=db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=RAGEvalHistoryResponse(**result),
    )


@router.get(
    "/{workspace_id}/dlp-policy",
    response_model=APIResponse[WorkspaceDLPPolicyResponse],
)
async def get_workspace_dlp_policy(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve workspace Data Loss Prevention (DLP) policy settings."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.get_workspace_dlp_policy(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceDLPPolicyResponse(**result),
    )


@router.patch(
    "/{workspace_id}/dlp-policy",
    response_model=APIResponse[WorkspaceDLPPolicyResponse],
)
async def update_workspace_dlp_policy(
    workspace_id: str,
    data: WorkspaceDLPPolicyUpdate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace Data Loss Prevention (DLP) policy rules and enforcement action (OWNER or ADMIN only)."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.update_workspace_dlp_policy(
        db=db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        enabled=data.enabled,
        action=data.action,
        active_rules=data.active_rules,
        custom_rules=data.custom_rules,
    )
    return APIResponse(
        success=True,
        data=WorkspaceDLPPolicyResponse(**result),
    )


@router.post(
    "/{workspace_id}/dlp/inspect",
    response_model=APIResponse[WorkspaceDLPInspectResponse],
)
async def inspect_workspace_dlp(
    workspace_id: str,
    data: WorkspaceDLPInspectRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Test and inspect text against active workspace DLP policy."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.inspect_workspace_dlp(
        db=db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        text=data.text,
    )
    return APIResponse(
        success=True,
        data=WorkspaceDLPInspectResponse(**result),
    )


@router.get(
    "/{workspace_id}/drift-analysis",
    response_model=APIResponse[MemoryDriftResponse],
)
async def get_workspace_memory_drift(
    workspace_id: str,
    window_days: int = 30,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate temporal semantic centroid drift, topic acceleration, and contradiction volatility."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.get_workspace_memory_drift(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        window_days=window_days,
    )
    return APIResponse(
        success=True,
        data=MemoryDriftResponse(**result),
    )


@router.get(
    "/{workspace_id}/compliance/scorecard",
    response_model=APIResponse[ComplianceScorecardResponse],
)
async def get_workspace_compliance_scorecard(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve 8-point regulatory and continuous security compliance scorecard."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.get_workspace_compliance_scorecard(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=ComplianceScorecardResponse(**result),
    )


@router.post(
    "/{workspace_id}/compliance/auto-remediate",
    response_model=APIResponse[ComplianceRemediateResponse],
)
async def auto_remediate_workspace_compliance(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Execute automated remediation for auto-fixable security compliance controls (DLP, TTL, HMAC)."""
    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await WorkspaceService.auto_remediate_workspace_compliance(
        db=db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=ComplianceRemediateResponse(**result),
    )


@router.get(
    "/{workspace_id}/timeline/time-travel",
    response_model=APIResponse[TimeTravelSnapshotResponse],
)
async def reconstruct_workspace_time_travel_snapshot(
    workspace_id: str,
    as_of: str = Query(description="Historical ISO 8601 timestamp (e.g. 2026-10-15T12:00:00Z)"),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Reconstruct the active memory state of a workspace as of an arbitrary historical timestamp."""
    from app.services.timeline_service import TimelineService

    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )

    try:
        clean_as_of = as_of.strip().replace(" ", "+")
        as_of_dt = datetime.fromisoformat(clean_as_of)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ISO 8601 timestamp format for 'as_of'.",
        )

    result = await TimelineService.reconstruct_time_travel_snapshot(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        as_of=as_of_dt,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post(
    "/{workspace_id}/timeline/diff",
    response_model=APIResponse[TimelineDiffResponse],
)
async def compute_workspace_timeline_diff(
    workspace_id: str,
    data: TimelineDiffRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Compute fine-grained structural delta between two arbitrary historical points in time."""
    from app.services.timeline_service import TimelineService

    if workspace_id != current_workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or unauthorized access.",
        )
    result = await TimelineService.compute_timeline_diff(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        timestamp_a=data.timestamp_a,
        timestamp_b=data.timestamp_b,
    )
    return APIResponse(
        success=True,
        data=result,
    )
