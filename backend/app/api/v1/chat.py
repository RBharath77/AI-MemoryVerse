from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.chat import (
    ChatFeedbackRequest,
    ChatMessageCreate,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
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
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    await ChatService.delete_conversation(db, current_workspace.id, conversation_id)
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
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
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

    msg = await ChatService.send_message(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        conversation_id=conversation_id,
        content=data.content,
    )
    return APIResponse(
        success=True,
        data=ChatMessageResponse.model_validate(msg),
    )


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
    )
    return APIResponse(
        success=True,
        data=ChatMessageResponse.model_validate(msg),
    )
