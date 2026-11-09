from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_current_workspace,
    require_scope,
)
from app.core.database import get_db
from app.core.idempotency import IdempotencyService, get_idempotency_key
from app.models.memory import MemoryCategory, MemoryStatus
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.memory import (
    ExistingReflectionsResponse,
    HierarchyDrilldownRequest,
    HierarchyDrilldownResponse,
    MemoryAclResponse,
    MemoryAclUpdate,
    MemoryAnalyticsResponse,
    MemoryAssociationsResponse,
    MemoryAutoConsolidateRequest,
    MemoryAutoConsolidateResponse,
    MemoryConflictResolutionRequest,
    MemoryConflictResolutionResponse,
    MemoryConsolidateRequest,
    MemoryCreate,
    MemoryDecayAnalyticsResponse,
    MemoryDeduplicationRequest,
    MemoryDeduplicationResponse,
    MemoryExtractionRequest,
    MemoryExtractionResponse,
    MemoryFeedbackCreate,
    MemoryFeedbackResponse,
    MemoryHierarchyBuildRequest,
    MemoryHierarchyResponse,
    MemoryImportRequest,
    MemoryImportResponse,
    MemoryLinkCreate,
    MemoryLinkResponse,
    MemoryReflectionRequest,
    MemoryReflectionResponse,
    MemoryReinforceResponse,
    MemoryResponse,
    MemoryTimelineResponse,
    MemoryUpdate,
    MemoryVersionResponse,
    SemanticFactDiffResponse,
    SleepCycleExecutionRequest,
    SleepCycleExecutionResponse,
    SleepCycleSimulationRequest,
    SleepCycleSimulationResponse,
    SpacedRepetitionReviewResponse,
    SpacedRepetitionReviewSubmit,
    SpacedRepetitionScheduleResponse,
    TimeLockedMemoryCreate,
    TimeLockedMemoryResponse,
    TimeLockedMemoryRevealResponse,
    WorkspaceIntegrityVerifyResponse,
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
    _scope: None = Depends(require_scope("memories:read")),
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
    response: Response,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:write")),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    if idempotency_key:
        acquired, record = await IdempotencyService.acquire(
            idempotency_key=idempotency_key,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
        )
        if not acquired:
            if record and record.status == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A request with this Idempotency-Key is currently being processed. Please retry shortly.",
                )
            if record and record.status == "completed":
                response.headers["X-Cache-Lookup"] = "HIT-IDEMPOTENT"
                response.status_code = record.status_code
                return record.data

    try:
        memory = await MemoryService.create_memory(
            db=db,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            data=data,
        )
        res_data = APIResponse(
            success=True,
            data=MemoryResponse.model_validate(memory),
        )
        if idempotency_key:
            response.headers["X-Cache-Lookup"] = "MISS-IDEMPOTENT"
            await IdempotencyService.complete(
                idempotency_key=idempotency_key,
                workspace_id=current_workspace.id,
                user_id=current_user.id,
                status_code=status.HTTP_201_CREATED,
                data=res_data.model_dump(mode="json"),
            )
        return res_data
    except Exception:
        if idempotency_key:
            await IdempotencyService.release(idempotency_key, current_workspace.id, current_user.id)
        raise


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
    response: Response,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    if idempotency_key:
        acquired, record = await IdempotencyService.acquire(
            idempotency_key=idempotency_key,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
        )
        if not acquired:
            if record and record.status == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A request with this Idempotency-Key is currently being processed. Please retry shortly.",
                )
            if record and record.status == "completed":
                response.headers["X-Cache-Lookup"] = "HIT-IDEMPOTENT"
                response.status_code = record.status_code
                return record.data

    try:
        result = await MemoryService.extract_and_store_memories(
            db=db,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            data=data,
        )
        res_data = APIResponse(
            success=True,
            data=result,
        )
        if idempotency_key:
            response.headers["X-Cache-Lookup"] = "MISS-IDEMPOTENT"
            await IdempotencyService.complete(
                idempotency_key=idempotency_key,
                workspace_id=current_workspace.id,
                user_id=current_user.id,
                status_code=status.HTTP_200_OK,
                data=res_data.model_dump(mode="json"),
            )
        return res_data
    except Exception:
        if idempotency_key:
            await IdempotencyService.release(idempotency_key, current_workspace.id, current_user.id)
        raise


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


@router.get("/decay-analytics", response_model=APIResponse[MemoryDecayAnalyticsResponse])
async def get_memory_decay_analytics(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """
    Analyze workspace memory decay distribution according to the Ebbinghaus Forgetting Curve.
    Categorizes memories into Strong, Fading, and Dormant (requiring review/reinforcement).
    """
    result = await MemoryService.get_decay_analytics(
        db=db,
        workspace_id=current_workspace.id,
    )
    return APIResponse(
        success=True,
        data=MemoryDecayAnalyticsResponse(**result),
    )


@router.post("/integrity/verify", response_model=APIResponse[WorkspaceIntegrityVerifyResponse])
async def verify_workspace_memories_integrity(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """
    Cryptographic tamper-evident audit.
    Verifies row-level HMAC-SHA256 signatures for all workspace memories,
    detecting direct SQL modifications or unauthorized row tampering.
    """
    result = await MemoryService.verify_workspace_integrity(
        db=db,
        workspace_id=current_workspace.id,
    )
    return APIResponse(
        success=True,
        data=WorkspaceIntegrityVerifyResponse(**result),
    )


@router.post("/reflect", response_model=APIResponse[MemoryReflectionResponse])
async def trigger_workspace_memory_reflection(
    data: MemoryReflectionRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """
    Autonomous Cognitive Memory Reflection.
    Synthesizes higher-order principles, architectural decisions, habits, and preferences
    from episodic workspace memories. Optionally auto-commits them as semantic memories.
    """
    from app.ai.reflection_engine import MemoryReflectionEngine

    result = await MemoryReflectionEngine.reflect(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        request=data,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.get("/reflections", response_model=APIResponse[ExistingReflectionsResponse])
async def get_existing_workspace_reflections(
    limit: int = Query(default=20, ge=1, le=100),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Retrieve previously committed cognitive reflections for the workspace."""
    from app.ai.reflection_engine import MemoryReflectionEngine

    result = await MemoryReflectionEngine.get_existing_reflections(
        db=db,
        workspace_id=current_workspace.id,
        limit=limit,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post(
    "/sleep-cycle/simulate",
    response_model=APIResponse[SleepCycleSimulationResponse],
)
async def simulate_sleep_cycle_pruning(
    data: SleepCycleSimulationRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """
    Simulate cognitive sleep-cycle synaptic pruning over workspace memories.
    Identifies low-utility, dormant, and transient memories while rigorously
    protecting pinned and knowledge-graph-anchored assets.
    """
    from app.ai.sleep_pruner import MemorySleepPruner

    result = await MemorySleepPruner.simulate_sleep_cycle(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/sleep-cycle/execute",
    response_model=APIResponse[SleepCycleExecutionResponse],
)
async def execute_sleep_cycle_pruning(
    data: SleepCycleExecutionRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Commit sleep-cycle pruning or context compaction across candidate memories.
    Actions supported: ARCHIVE, SUPERSEDE, or COMPACT into a single consolidated digest.
    """
    from app.ai.sleep_pruner import MemorySleepPruner

    result = await MemorySleepPruner.execute_sleep_cycle(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/hierarchy/build",
    response_model=APIResponse[MemoryHierarchyResponse],
)
async def build_memory_hierarchy(
    data: MemoryHierarchyBuildRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Construct multi-tier cognitive abstraction pyramid over active workspace memories.
    Organizes memories into Leaf observations, Tactical clusters, Core principles, and Root axioms.
    """
    from app.ai.cognitive_hierarchy import CognitiveHierarchyEngine

    result = await CognitiveHierarchyEngine.build_hierarchy(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.get(
    "/hierarchy/tree",
    response_model=APIResponse[MemoryHierarchyResponse],
)
async def get_memory_hierarchy_tree(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Retrieve active cognitive abstraction tree for the workspace."""
    from app.ai.cognitive_hierarchy import CognitiveHierarchyEngine

    result = await CognitiveHierarchyEngine.get_hierarchy(
        db=db,
        workspace_id=current_workspace.id,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/hierarchy/drilldown",
    response_model=APIResponse[HierarchyDrilldownResponse],
)
async def drilldown_memory_hierarchy(
    data: HierarchyDrilldownRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Inspect and drill down into a specific hierarchy node, walking ancestors, descendants, and source memories."""
    from app.ai.cognitive_hierarchy import CognitiveHierarchyEngine

    result = await CognitiveHierarchyEngine.drilldown(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.get(
    "/spaced-repetition/schedule",
    response_model=APIResponse[SpacedRepetitionScheduleResponse],
)
async def get_spaced_repetition_schedule(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """
    Autonomous Temporal Memory Time-Decay Rejuvenation & Spaced Repetition Scheduler.
    Retrieves upcoming and overdue memories scheduled for SM-2 review with retention probabilities.
    """
    from app.ai.spaced_repetition import SpacedRepetitionScheduler

    result = await SpacedRepetitionScheduler.get_schedule(
        db=db,
        workspace_id=current_workspace.id,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/spaced-repetition/review",
    response_model=APIResponse[SpacedRepetitionReviewResponse],
)
async def submit_spaced_repetition_review(
    data: SpacedRepetitionReviewSubmit,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Submit recall quality rating (0-5) for a memory, updating SM-2 ease factor,
    repetition count, interval, and next review date.
    """
    from app.ai.spaced_repetition import SpacedRepetitionScheduler

    result = await SpacedRepetitionScheduler.submit_review(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        submit_data=data,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/time-locked",
    response_model=APIResponse[TimeLockedMemoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_time_locked_memory(
    data: TimeLockedMemoryCreate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Zero-Knowledge Multi-Tenant Ephemeral Memory Vault & Time-Locked Cryptographic Enclave.
    Encrypts sensitive content under an ephemeral per-record key with TTL and max views.
    """
    from app.core.time_locked_vault import TimeLockedVaultService

    result = await TimeLockedVaultService.create_time_locked_memory(
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.get(
    "/time-locked/{vault_id}",
    response_model=APIResponse[TimeLockedMemoryRevealResponse],
)
async def reveal_time_locked_memory(
    vault_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Reveal and decrypt time-locked ephemeral memory; burns key on read once views expire."""
    from app.core.time_locked_vault import TimeLockedVaultService

    result = await TimeLockedVaultService.reveal_time_locked_memory(
        workspace_id=current_workspace.id,
        vault_id=vault_id,
    )
    return APIResponse(success=True, data=result)


@router.delete(
    "/time-locked/{vault_id}",
    response_model=APIResponse[dict],
)
async def shred_time_locked_memory(
    vault_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """Immediately and irreversibly cryptographically shred an ephemeral time-locked vault memory."""
    from app.core.time_locked_vault import TimeLockedVaultService

    shredded = TimeLockedVaultService.crypto_shred(
        workspace_id=current_workspace.id,
        vault_id=vault_id,
    )
    return APIResponse(success=True, data={"shredded": shredded, "vault_id": vault_id})


@router.get("/{memory_id}", response_model=APIResponse[MemoryResponse])
async def get_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:read")),
):
    from app.core.memory_acl import MemoryAccessControlService

    memory = await MemoryService.get_memory(db, current_workspace.id, memory_id)
    role = await MemoryAccessControlService.get_user_workspace_role(
        db, current_workspace.id, current_user.id
    )
    can_read = MemoryAccessControlService.can_user_access_memory(
        memory=memory,
        user_id=current_user.id,
        user_role=role,
        is_superuser=current_user.is_superuser,
        action="read",
    )
    if not can_read:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this restricted memory is forbidden by dynamic access control list policy",
        )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(memory),
    )


@router.get(
    "/{memory_id}/access-control",
    response_model=APIResponse[MemoryAclResponse],
)
async def get_memory_access_control(
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:read")),
):
    """Retrieve fine-grained ABAC visibility and dynamic ACL policy for a memory."""
    from app.core.memory_acl import MemoryAccessControlService

    memory = await MemoryService.get_memory(db, current_workspace.id, memory_id)
    role = await MemoryAccessControlService.get_user_workspace_role(
        db, current_workspace.id, current_user.id
    )
    policy = MemoryAccessControlService.get_memory_acl_policy(
        memory=memory,
        user_id=current_user.id,
        user_role=role,
        is_superuser=current_user.is_superuser,
    )
    return APIResponse(success=True, data=policy)


@router.patch(
    "/{memory_id}/access-control",
    response_model=APIResponse[MemoryAclResponse],
)
async def update_memory_access_control(
    memory_id: str,
    data: MemoryAclUpdate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:write")),
):
    """Update fine-grained ABAC visibility and dynamic ACL policy for a memory (author, owner, admin only)."""
    from app.core.memory_acl import MemoryAccessControlService

    memory = await MemoryService.get_memory(db, current_workspace.id, memory_id)
    role = await MemoryAccessControlService.get_user_workspace_role(
        db, current_workspace.id, current_user.id
    )
    updated_policy = await MemoryAccessControlService.update_memory_acl_policy(
        db=db,
        memory=memory,
        user_id=current_user.id,
        user_role=role,
        update_data=data,
        is_superuser=current_user.is_superuser,
    )
    return APIResponse(success=True, data=updated_policy)


@router.patch("/{memory_id}", response_model=APIResponse[MemoryResponse])
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:write")),
):
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    memory = await MemoryService.update_memory(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
        data=data,
        is_admin_or_owner=is_admin_or_owner,
    )
    return APIResponse(
        success=True,
        data=MemoryResponse.model_validate(memory),
    )


@router.delete("/{memory_id}", response_model=APIResponse[dict])
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("memories:write")),
):
    """Delete a memory (creator, workspace admin, or owner only)."""
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    await MemoryService.delete_memory(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        current_user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner,
    )
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
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    restored = await MemoryService.restore_version(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
        version_number=version_number,
        is_admin_or_owner=is_admin_or_owner,
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


@router.post("/deduplicate", response_model=APIResponse[MemoryDeduplicationResponse])
async def deduplicate_memories(
    data: MemoryDeduplicationRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Automated memory redundancy deduplication engine.
    Scans active memories in the workspace, computes pairwise similarity,
    consolidates duplicates exceeding threshold into primary records,
    and invalidates the RAG semantic cache.
    """
    result = await MemoryService.deduplicate_workspace_memories(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        similarity_threshold=data.similarity_threshold,
        auto_merge=data.auto_merge,
    )
    return APIResponse(
        success=True,
        data=MemoryDeduplicationResponse(**result),
    )


@router.post("/{memory_id}/reinforce", response_model=APIResponse[MemoryReinforceResponse])
async def reinforce_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """
    Biological memory reinforcement engine.
    Boosts memory stability, resets elapsed decay window, and increases retention probability.
    """
    result = await MemoryService.reinforce_memory(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=MemoryReinforceResponse(**result),
    )


@router.post(
    "/{memory_id}/resolve-conflict",
    response_model=APIResponse[MemoryConflictResolutionResponse],
)
async def resolve_memory_conflict(
    memory_id: str,
    data: MemoryConflictResolutionRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """Interactively resolve candidate memory contradictions using supersede, merge, keep_both, or discard."""
    is_admin_or_owner = current_user.is_superuser
    if not is_admin_or_owner:
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == current_workspace.id,
            WorkspaceMember.user_id == current_user.id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        is_admin_or_owner = role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)

    result = await MemoryService.resolve_conflict(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
        data=data,
        is_admin_or_owner=is_admin_or_owner,
    )
    return APIResponse(
        success=True,
        data=MemoryConflictResolutionResponse(**result),
    )


@router.get(
    "/{memory_id}/conflict-diff",
    response_model=APIResponse[SemanticFactDiffResponse],
)
async def get_memory_conflict_diff(
    memory_id: str,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Preview fine-grained semantic fact diff between candidate memory and its conflicting counterpart."""
    result = await MemoryService.preview_conflict_diff(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        user_id=current_user.id,
    )
    return APIResponse(
        success=True,
        data=SemanticFactDiffResponse(**result),
    )


@router.get(
    "/{memory_id}/associations",
    response_model=APIResponse[MemoryAssociationsResponse],
)
async def get_memory_associations(
    memory_id: str,
    max_hops: int = Query(default=2, ge=1, le=4),
    min_activation: float = Query(default=0.15, ge=0.01, le=1.0),
    limit: int = Query(default=10, ge=1, le=50),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:read")),
):
    """Explore multi-hop spreading activation associative graph for seed memory."""
    result = await MemoryService.get_memory_associations(
        db=db,
        workspace_id=current_workspace.id,
        memory_id=memory_id,
        max_hops=max_hops,
        min_activation=min_activation,
        limit=limit,
    )
    return APIResponse(
        success=True,
        data=MemoryAssociationsResponse(**result),
    )


@router.post(
    "/auto-consolidate",
    response_model=APIResponse[MemoryAutoConsolidateResponse],
)
async def auto_consolidate_memories(
    data: MemoryAutoConsolidateRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope_guard: None = Depends(require_scope("memories:write")),
):
    """Abstract and consolidate granular episodic memories into high-order semantic principles."""
    result = await MemoryService.auto_consolidate_workspace_memories(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        request=data,
    )
    return APIResponse(
        success=True,
        data=MemoryAutoConsolidateResponse(**result),
    )
