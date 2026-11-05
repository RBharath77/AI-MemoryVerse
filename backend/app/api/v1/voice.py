import base64
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audio_factory import get_stt_provider, get_tts_provider
from app.ai.base import STTResponse, TTSResponse
from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.chat import ConversationCreate
from app.schemas.common import APIResponse
from app.schemas.research import VoiceChatRequest, VoiceChatResponse
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = "alloy"


@router.post("/transcribe", response_model=APIResponse[dict[str, Any]])
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[dict[str, Any]]:
    """Transcribe an uploaded audio recording into text."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file must have a valid filename.",
        )

    # Read audio bytes
    audio_data = await file.read()
    if len(audio_data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file cannot be empty.",
        )
    if len(audio_data) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds 25 MB limit.",
        )

    stt = get_stt_provider()
    result: STTResponse = await stt.transcribe_audio(
        audio_data=audio_data,
        filename=file.filename,
        content_type=file.content_type or "audio/wav",
    )

    return APIResponse(
        success=True,
        data={
            "text": result.text,
            "language": result.language,
            "duration": round(result.duration, 2),
            "confidence": result.confidence,
        },
    )


@router.post("/synthesize")
async def synthesize_speech(
    data: SynthesizeRequest,
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> Response:
    """Synthesize text into spoken audio bytes."""
    tts = get_tts_provider()
    result: TTSResponse = await tts.synthesize_speech(
        text=data.text,
        voice=data.voice,
    )

    return Response(
        content=result.audio_bytes,
        media_type=result.content_type,
        headers={
            "X-Estimated-Duration": str(result.duration_estimate),
            "Content-Disposition": 'inline; filename="synthesized.wav"',
        },
    )


@router.post("/chat", response_model=APIResponse[VoiceChatResponse])
async def voice_chat(
    data: VoiceChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[VoiceChatResponse]:
    """Execute a voice query against the workspace RAG engine and synthesize an audio response."""
    # 1. Resolve or create conversation
    conv_id = data.conversation_id
    if not conv_id:
        new_conv = await ChatService.create_conversation(
            db=db,
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            data=ConversationCreate(title=f"Voice: {data.query[:30]}"),
        )
        conv_id = new_conv.id

    # 2. Process query via RAG engine
    assistant_msg = await ChatService.send_message(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        conversation_id=conv_id,
        content=data.query,
    )

    # 3. Synthesize audio response
    tts = get_tts_provider()
    tts_result: TTSResponse = await tts.synthesize_speech(
        text=assistant_msg.content,
        voice=data.voice,
    )

    audio_b64 = base64.b64encode(tts_result.audio_bytes).decode("utf-8")

    return APIResponse(
        success=True,
        data=VoiceChatResponse(
            user_query=data.query,
            assistant_response=assistant_msg.content,
            conversation_id=conv_id,
            citations=assistant_msg.citations or [],
            audio_base64=audio_b64,
            audio_mime_type=tts_result.content_type,
        ),
    )
