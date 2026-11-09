from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_user,
    get_current_workspace,
    require_scope,
)
from app.core.database import get_db
from app.core.idempotency import IdempotencyService, get_idempotency_key
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.chat import (
    AttributionVerificationRequest,
    AttributionVerificationResponse,
    ChatFeedbackRequest,
    ChatMessageCreate,
    ChatMessageResponse,
    ConsensusDebateRequest,
    ConsensusDebateResponse,
    ConversationCreate,
    ConversationResponse,
    PromptInspectionRequest,
    PromptInspectionResponse,
    UncertaintyCalibrationRequest,
    UncertaintyCalibrationResponse,
)
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/conversations", response_model=APIResponse[PaginatedResponse[ConversationResponse]])
async def list_conversations(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    convs, total = await ChatService.list_conversations(
        db=db,
        workspace_id=current_workspace.id,
        search=search,
        limit=page_size,
        offset=offset,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = [
        ConversationResponse(
            id=c.id,
            workspace_id=c.workspace_id,
            user_id=c.user_id,
            title=c.title,
            system_prompt=c.system_prompt,
            model=c.model,
            temperature=c.temperature,
            is_pinned=c.is_pinned,
            is_archived=c.is_archived,
            message_count=len(c.messages) if c.messages is not None else 0,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]

    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post(
    "/conversations",
    response_model=APIResponse[ConversationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    conv = await ChatService.create_conversation(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=ConversationResponse(
            id=conv.id,
            workspace_id=conv.workspace_id,
            user_id=conv.user_id,
            title=conv.title,
            system_prompt=conv.system_prompt,
            model=conv.model,
            temperature=conv.temperature,
            is_pinned=conv.is_pinned,
            is_archived=conv.is_archived,
            message_count=0,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ),
    )


@router.get("/conversations/{conversation_id}", response_model=APIResponse[ConversationResponse])
async def get_conversation(
    conversation_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    conv = await ChatService.get_conversation(db, current_workspace.id, conversation_id)
    return APIResponse(
        success=True,
        data=ConversationResponse(
            id=conv.id,
            workspace_id=conv.workspace_id,
            user_id=conv.user_id,
            title=conv.title,
            system_prompt=conv.system_prompt,
            model=conv.model,
            temperature=conv.temperature,
            is_pinned=conv.is_pinned,
            is_archived=conv.is_archived,
            message_count=len(conv.messages) if conv.messages is not None else 0,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ),
    )


@router.delete("/conversations/{conversation_id}", response_model=APIResponse[dict])
async def delete_conversation(
    conversation_id: str,
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

    await ChatService.delete_conversation(
        db=db,
        workspace_id=current_workspace.id,
        conversation_id=conversation_id,
        current_user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner,
    )
    return APIResponse(
        success=True,
        data={"message": "Conversation deleted successfully."},
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=APIResponse[list[ChatMessageResponse]],
)
async def list_conversation_messages(
    conversation_id: str,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    messages = await ChatService.get_messages(db, current_workspace.id, conversation_id)
    return APIResponse(
        success=True,
        data=[ChatMessageResponse.model_validate(m) for m in messages],
    )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    data: ChatMessageCreate,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("chat:write")),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    if data.stream:
        # Stream response chunks via Server-Sent Events
        stream_gen = ChatService.stream_message(
            db=db,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=data.content,
        )
        return StreamingResponse(stream_gen, media_type="text/event-stream")

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
        msg = await ChatService.send_message(
            db=db,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=data.content,
        )
        res_data = APIResponse(
            success=True,
            data=ChatMessageResponse.model_validate(msg),
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


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/feedback",
    response_model=APIResponse[ChatMessageResponse],
)
async def submit_message_feedback(
    conversation_id: str,
    message_id: str,
    data: ChatFeedbackRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    msg = await ChatService.add_feedback(
        db=db,
        workspace_id=current_workspace.id,
        message_id=message_id,
        rating=data.rating,
        conversation_id=conversation_id,
    )
    return APIResponse(
        success=True,
        data=ChatMessageResponse.model_validate(msg),
    )


@router.post(
    "/guard/inspect-prompt",
    response_model=APIResponse[PromptInspectionResponse],
)
async def inspect_prompt_guard(
    data: PromptInspectionRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    _scope: None = Depends(require_scope("chat")),
):
    """Inspect and evaluate prompt text against adversarial prompt injection & jailbreak patterns."""
    from app.ai.prompt_guard import PromptInjectionGuard

    inspection = PromptInjectionGuard.inspect(data.prompt)
    return APIResponse(
        success=True,
        data=PromptInspectionResponse(
            original_prompt=inspection.original_prompt,
            sanitized_prompt=inspection.sanitized_prompt,
            is_safe=inspection.is_safe,
            risk_score=inspection.risk_score,
            threat_level=inspection.threat_level,
            detected_patterns=inspection.detected_patterns,
            recommendation=inspection.recommendation,
            metadata=inspection.metadata,
        ),
    )


@router.post(
    "/consensus-debate",
    response_model=APIResponse[ConsensusDebateResponse],
)
async def conduct_consensus_debate(
    data: ConsensusDebateRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("chat")),
):
    """Conduct multi-agent collaborative consensus debate across Proponent, Skeptic, and Arbitrator roles."""
    from app.ai.consensus_debate import ConsensusDebateEngine

    result = await ConsensusDebateEngine.run_consensus_debate(
        db=db,
        workspace_id=current_workspace.id,
        topic=data.topic,
        rounds=data.rounds,
        include_grounding=data.include_grounding_memories,
    )
    return APIResponse(
        success=True,
        data=result,
    )


@router.post(
    "/verify-attribution",
    response_model=APIResponse[AttributionVerificationResponse],
)
async def verify_chat_attribution(
    data: AttributionVerificationRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("chat")),
):
    """
    Semantic Knowledge Grounding & Hallucination Attribution Verifier.
    Audits generated assistant responses against retrieved workspace memories or explicit context,
    deconstructing claims into atomic propositions, evaluating premise entailment,
    and calculating grounding fidelity and hallucination risk indices.
    """
    from app.ai.attribution_verifier import GroundingAttributionVerifier

    result = await GroundingAttributionVerifier.verify(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)


@router.post(
    "/calibrate-uncertainty",
    response_model=APIResponse[UncertaintyCalibrationResponse],
)
async def calibrate_chat_uncertainty(
    data: UncertaintyCalibrationRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    _scope: None = Depends(require_scope("chat")),
):
    """
    Active Continuous Epistemic Uncertainty & Confidence Calibration Engine.
    Disentangles epistemic knowledge deficits from aleatoric ambiguity,
    evaluating evidence entropy and computing calibrated confidence intervals.
    """
    from app.ai.uncertainty_calibrator import EpistemicUncertaintyCalibrator

    result = await EpistemicUncertaintyCalibrator.calibrate(
        db=db,
        workspace_id=current_workspace.id,
        request=data,
    )
    return APIResponse(success=True, data=result)
