from dataclasses import dataclass, field

from app.ai.base import LLMMessage
from app.ai.retrieval import SearchResultItem


@dataclass
class AssembledContext:
    system_prompt: str
    messages: list[LLMMessage]
    citations: list[dict] = field(default_factory=list)
    token_estimate: int = 0


class ContextAssembler:
    """Assembles budget-aware prompt context from memories and document chunks."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are the AI-MemoryVerse assistant. You provide source-grounded answers.\n"
        "Ground your answers in the provided memories and documents. "
        "Include inline bracketed source markers (e.g. [1], [2]). "
        "If the answer is not present, state what is known without fabricating facts."
    )

    @classmethod
    def assemble(
        cls,
        user_query: str,
        conversation_history: list[dict],  # list of {"role": str, "content": str}
        grounding_contexts: list[SearchResultItem],
        custom_instructions: str | None = None,
        max_context_tokens: int = 3500,
    ) -> AssembledContext:
        citations = []
        context_blocks = []
        token_count = 0

        # Build numbered grounding sources
        for idx, item in enumerate(grounding_contexts, start=1):
            marker = f"[{idx}]"
            snippet = item.content.strip()

            citations.append(
                {
                    "citation_index": idx,
                    "marker": marker,
                    "source_type": item.source_type,
                    "source_id": item.id,
                    "title": item.title,
                    "snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet,
                }
            )

            block = f"{marker} [{item.source_type.upper()}] {item.title}:\n{snippet}"
            context_blocks.append(block)
            token_count += int(len(block.split()) * 1.3)

            if token_count > max_context_tokens:
                break

        # Construct System Prompt
        sys_prompt = cls.DEFAULT_SYSTEM_PROMPT
        if custom_instructions and custom_instructions.strip():
            sys_prompt += f"\n\nUser Custom Instructions:\n{custom_instructions.strip()}"

        if context_blocks:
            sys_prompt += "\n\n=== RELEVANT WORKSPACE CONTEXT ===\n" + "\n\n".join(context_blocks)

        # Assemble Messages
        llm_messages: list[LLMMessage] = [LLMMessage(role="system", content=sys_prompt)]

        # Add recent conversation history (last 10 turns)
        recent_history = conversation_history[-10:] if conversation_history else []
        for msg in recent_history:
            llm_messages.append(LLMMessage(role=msg["role"], content=msg["content"]))

        # Add current user query
        llm_messages.append(LLMMessage(role="user", content=user_query))

        return AssembledContext(
            system_prompt=sys_prompt,
            messages=llm_messages,
            citations=citations,
            token_estimate=token_count,
        )
