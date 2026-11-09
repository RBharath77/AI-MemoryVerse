import json
import logging
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_assembler import ContextAssembler
from app.ai.data_leakage_guard import DataLeakageGuard
from app.ai.factory import get_llm_provider
from app.ai.reranker import Reranker
from app.ai.retrieval import HybridSearchEngine
from app.models.chat import ChatMessage, Conversation, MessageRole
from app.models.user import UserProfile
from app.schemas.chat import ConversationCreate

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: ConversationCreate,
    ) -> Conversation:
        title = data.title.strip() if data.title and data.title.strip() else "New Conversation"
        conv = Conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            system_prompt=data.system_prompt,
            model=data.model or "gpt-4o-mini",
            temperature=data.temperature,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        workspace_id: str,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Conversation], int]:
        query = select(Conversation).where(Conversation.workspace_id == workspace_id)
        if search:
            query = query.where(Conversation.title.ilike(f"%{search}%"))

        count_query = select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace_id
        )
        if search:
            count_query = count_query.where(Conversation.title.ilike(f"%{search}%"))

        total = (await db.execute(count_query)).scalar() or 0

        query = (
            query.order_by(desc(Conversation.is_pinned), desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        conversations = (await db.execute(query)).scalars().all()
        return list(conversations), total

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        workspace_id: str,
        conversation_id: str,
    ) -> Conversation:
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
        res = await db.execute(query)
        conv = res.scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized.",
            )
        return conv

    @staticmethod
    async def delete_conversation(
        db: AsyncSession,
        workspace_id: str,
        conversation_id: str,
        current_user_id: str | None = None,
        is_admin_or_owner: bool = False,
    ) -> bool:
        conv = await ChatService.get_conversation(db, workspace_id, conversation_id)
        if current_user_id and conv.user_id != current_user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete this conversation.",
            )
        await db.delete(conv)
        await db.commit()
        return True

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        workspace_id: str,
        conversation_id: str,
    ) -> list[ChatMessage]:
        await ChatService.get_conversation(db, workspace_id, conversation_id)
        query = (
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.workspace_id == workspace_id,
            )
            .order_by(ChatMessage.created_at)
        )
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def send_message(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> ChatMessage:
        conv = await ChatService.get_conversation(db, workspace_id, conversation_id)

        # 1. Save user message
        user_msg = ChatMessage(
            conversation_id=conv.id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=MessageRole.USER.value,
            content=content,
            token_count=int(len(content.split()) * 1.3),
        )
        db.add(user_msg)
        await db.flush()

        # Update conversation title if default
        if conv.title == "New Conversation":
            words = content.split()[:5]
            conv.title = " ".join(words)
            if len(content.split()) > 5:
                conv.title += "..."

        # 2. Fetch user custom instructions if present
        prof_q = select(UserProfile.ai_custom_instructions).where(UserProfile.user_id == user_id)
        custom_inst = (await db.execute(prof_q)).scalar() or conv.system_prompt

        # 3. Retrieve grounding contexts
        candidates = await HybridSearchEngine.search(
            db=db,
            workspace_id=workspace_id,
            query=content,
            top_k=8,
        )

        # 4. Rerank
        reranked = Reranker.rerank(candidates, top_k=4)

        # 5. Fetch previous conversation turns
        prev_messages = await ChatService.get_messages(db, workspace_id, conversation_id)
        history = [
            {"role": m.role, "content": m.content} for m in prev_messages if m.id != user_msg.id
        ]

        # Multi-Tenant Semantic Cache Check
        from app.ai.semantic_cache import SemanticCache

        if len(history) == 0:
            cached_result = SemanticCache.get(workspace_id, content)
            if cached_result:
                cached_content, cached_citations = cached_result
                assistant_msg = ChatMessage(
                    conversation_id=conv.id,
                    workspace_id=workspace_id,
                    role=MessageRole.ASSISTANT.value,
                    content=cached_content,
                    token_count=int(len(cached_content.split()) * 1.3),
                    citations=cached_citations,
                    extra_metadata={"model": conv.model, "cached": True, "cache_hit": True},
                )
                db.add(assistant_msg)
                await db.commit()
                await db.refresh(assistant_msg)
                return assistant_msg

        # 6. Assemble context
        assembled = ContextAssembler.assemble(
            user_query=content,
            conversation_history=history,
            grounding_contexts=reranked,
            custom_instructions=custom_inst,
        )

        # 7. Generate LLM response
        llm = get_llm_provider()
        llm_response = await llm.chat(
            messages=assembled.messages,
            temperature=conv.temperature,
        )

        # Cache synthesized response for identical subsequent queries
        from app.ai.data_leakage_guard import DataLeakageGuard

        leakage_check = DataLeakageGuard.sanitize(
            text=llm_response.content,
            current_workspace_id=workspace_id,
        )
        safe_content = leakage_check.sanitized_text

        if len(history) == 0:
            SemanticCache.set(
                workspace_id=workspace_id,
                query=content,
                content=safe_content,
                citations=assembled.citations,
                ttl_seconds=3600,
            )

        # 8. Save assistant message
        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            workspace_id=workspace_id,
            role=MessageRole.ASSISTANT.value,
            content=safe_content,
            token_count=int(len(safe_content.split()) * 1.3),
            citations=assembled.citations,
            extra_metadata={
                "model": conv.model,
                "usage": llm_response.usage,
                "leakage_sanitized": not leakage_check.is_clean,
            },
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)
        return assistant_msg

    @staticmethod
    async def stream_message(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AsyncGenerator[str, None]:
        """Server-Sent Events generator streaming message chunks."""
        conv = await ChatService.get_conversation(db, workspace_id, conversation_id)

        # Save user message
        user_msg = ChatMessage(
            conversation_id=conv.id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=MessageRole.USER.value,
            content=content,
            token_count=int(len(content.split()) * 1.3),
        )
        db.add(user_msg)
        await db.flush()

        candidates = await HybridSearchEngine.search(
            db=db,
            workspace_id=workspace_id,
            query=content,
            top_k=6,
        )
        reranked = Reranker.rerank(candidates, top_k=4)
        prev_messages = await ChatService.get_messages(db, workspace_id, conversation_id)
        history = [
            {"role": m.role, "content": m.content} for m in prev_messages if m.id != user_msg.id
        ]

        assembled = ContextAssembler.assemble(
            user_query=content,
            conversation_history=history,
            grounding_contexts=reranked,
        )

        # Emit citations first
        yield f"event: citations\ndata: {json.dumps(assembled.citations)}\n\n"

        llm = get_llm_provider()
        llm_resp = await llm.chat(messages=assembled.messages, temperature=conv.temperature)

        # Stream text tokens simulated / real
        tokens = llm_resp.content.split(" ")
        for token in tokens:
            yield f"event: token\ndata: {json.dumps({'token': token + ' '})}\n\n"

        # Save complete message
        leakage_stream_check = DataLeakageGuard.sanitize(
            text=llm_resp.content,
            current_workspace_id=workspace_id,
        )
        safe_stream_content = leakage_stream_check.sanitized_text

        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            workspace_id=workspace_id,
            role=MessageRole.ASSISTANT.value,
            content=safe_stream_content,
            token_count=int(len(safe_stream_content.split()) * 1.3),
            citations=assembled.citations,
            extra_metadata={
                "leakage_sanitized": not leakage_stream_check.is_clean,
            },
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg.id})}\n\n"

    @staticmethod
    async def add_feedback(
        db: AsyncSession,
        workspace_id: str,
        message_id: str,
        rating: int,
        conversation_id: str | None = None,
    ) -> ChatMessage:
        query = select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.workspace_id == workspace_id,
        )
        if conversation_id:
            query = query.where(ChatMessage.conversation_id == conversation_id)
        res = await db.execute(query)
        msg = res.scalar_one_or_none()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat message not found in specified conversation.",
            )
        msg.feedback = rating
        await db.commit()
        await db.refresh(msg)
        return msg
