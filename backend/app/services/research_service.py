import json
import logging
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_llm_provider
from app.ai.retrieval import HybridSearchEngine
from app.models.graph import EntityType, GraphEntity
from app.models.memory import Memory, MemoryReview, MemoryStatus
from app.models.research import (
    InsightType,
    KnowledgeInsight,
    ReportStatus,
    ReportType,
    ResearchReport,
)
from app.schemas.research import ReportGenerateRequest

logger = logging.getLogger(__name__)


class ResearchService:
    @staticmethod
    async def generate_report(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: ReportGenerateRequest,
    ) -> ResearchReport:
        llm = get_llm_provider()
        cutoff_date = datetime.now(UTC) - timedelta(days=data.days_back)

        # 1. Retrieve relevant memories & document context
        mem_q = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
                Memory.created_at >= cutoff_date,
            )
            .order_by(desc(Memory.importance), desc(Memory.created_at))
            .limit(30)
        )
        memories = (await db.execute(mem_q)).scalars().all()

        # Perform hybrid search for topic-specific items if requested
        search_results = []
        if data.report_type in (ReportType.TOPIC_RESEARCH, ReportType.PROJECT_BRIEF):
            search_results = await HybridSearchEngine.search(
                db=db,
                workspace_id=workspace_id,
                query=data.topic,
                top_k=15,
                include_memories=True,
                include_documents=True,
            )

        # Compile sources text and metadata
        source_texts = []
        sources_used = []

        seen_mem_ids = set()
        for res in search_results:
            source_texts.append(f"- [{res.source_type.upper()}] {res.title}: {res.content}")
            sources_used.append(
                {
                    "source_id": res.id,
                    "title": res.title,
                    "type": res.source_type,
                    "score": round(res.score, 3),
                }
            )
            if res.source_type == "memory":
                seen_mem_ids.add(res.id)

        for m in memories:
            if m.id not in seen_mem_ids and len(source_texts) < 25:
                source_texts.append(f"- [MEMORY ({m.category.value})] {m.content}")
                sources_used.append(
                    {
                        "source_id": m.id,
                        "title": m.content[:50],
                        "type": "memory",
                        "score": 1.0,
                    }
                )

        context_block = (
            "\n".join(source_texts)
            if source_texts
            else "- No previous memories or documents found for this topic."
        )

        title = f"{data.topic} — {data.report_type.value.replace('_', ' ').title()}"
        if data.report_type == ReportType.DAILY_DIGEST:
            title = f"Daily Knowledge Digest — {datetime.now(UTC).strftime('%b %d, %Y')}"
        elif data.report_type == ReportType.WEEKLY_SUMMARY:
            title = f"Weekly Knowledge Summary — {datetime.now(UTC).strftime('Week of %b %d, %Y')}"

        # 2. Synthesize using LLM
        prompt = (
            "You are a Principal Research Analyst and Knowledge Intelligence Assistant.\n"
            f"Generate an insightful, well-structured {data.report_type.value} report on: "
            f"'{data.topic}'.\n\n"
            f"Source Knowledge Context:\n{context_block}\n\n"
            "Requirements:\n"
            "1. Produce structured markdown with: # Executive Summary, ## Key Findings, "
            "## Strategic Implications, and ## Action Items & Next Steps.\n"
            "2. Be concise, rigorous, factual, and strictly grounded in the provided context.\n"
            "3. Return at the end a JSON block inside ```json with:\n"
            '{"key_findings": ["finding 1", ...], "action_items": ["action 1", ...]}\n'
        )

        resp = await llm.generate_text(
            prompt=prompt,
            system_prompt="You synthesize research reports in Markdown and JSON.",
            max_tokens=1500,
        )

        raw_output = resp.content.strip()

        # Extract markdown and structured JSON
        key_findings = []
        action_items = []
        markdown_content = raw_output

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                key_findings = parsed.get("key_findings", [])
                action_items = parsed.get("action_items", [])
                markdown_content = raw_output[: json_match.start()].strip()
            except Exception:
                pass

        if not key_findings:
            key_findings = [
                f"Knowledge syntheses analyzed across {len(sources_used)} verified sources.",
                f"Core theme centered around {data.topic}.",
            ]
        if not action_items:
            action_items = [
                "Review linked sources for technical verification.",
                "Capture subsequent project milestones as new memories.",
            ]

        # 3. Store in database
        report = ResearchReport(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            topic=data.topic,
            report_type=data.report_type,
            status=ReportStatus.COMPLETED,
            content_markdown=markdown_content,
            key_findings=key_findings,
            action_items=action_items,
            sources_used=sources_used,
            extra_metadata={"generated_by_model": resp.model},
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

    @staticmethod
    async def get_reports(
        db: AsyncSession,
        workspace_id: str,
        report_type: ReportType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ResearchReport], int]:
        q = select(ResearchReport).where(ResearchReport.workspace_id == workspace_id)
        count_q = select(func.count(ResearchReport.id)).where(
            ResearchReport.workspace_id == workspace_id
        )

        if report_type:
            q = q.where(ResearchReport.report_type == report_type)
            count_q = count_q.where(ResearchReport.report_type == report_type)

        total = (await db.execute(count_q)).scalar() or 0
        q = q.order_by(desc(ResearchReport.created_at)).limit(limit).offset(offset)
        reports = (await db.execute(q)).scalars().all()
        return list(reports), total

    @staticmethod
    async def get_report(
        db: AsyncSession,
        workspace_id: str,
        report_id: str,
    ) -> ResearchReport:
        q = select(ResearchReport).where(
            ResearchReport.id == report_id,
            ResearchReport.workspace_id == workspace_id,
        )
        report = (await db.execute(q)).scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Research report not found or unauthorized.",
            )
        return report

    @staticmethod
    async def delete_report(
        db: AsyncSession,
        workspace_id: str,
        report_id: str,
    ) -> bool:
        report = await ResearchService.get_report(db, workspace_id, report_id)
        await db.delete(report)
        await db.commit()
        return True

    @staticmethod
    async def refresh_insights(
        db: AsyncSession,
        workspace_id: str,
    ) -> list[KnowledgeInsight]:
        """Proactively scan workspace memories and graph to generate actionable insights."""
        now = datetime.now(UTC)
        created_insights: list[KnowledgeInsight] = []

        # 1. Stale memories check (>30 days old without updates)
        stale_cutoff = now - timedelta(days=30)
        stale_q = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
                Memory.created_at < stale_cutoff,
            )
            .order_by(desc(Memory.importance))
            .limit(3)
        )
        stale_mems = (await db.execute(stale_q)).scalars().all()
        for mem in stale_mems:
            title = f"Stale Memory: '{mem.content[:45]}…'"
            # Check existing active insight
            ex_q = select(KnowledgeInsight).where(
                KnowledgeInsight.workspace_id == workspace_id,
                KnowledgeInsight.title == title,
                KnowledgeInsight.is_dismissed.is_(False),
            )
            if not (await db.execute(ex_q)).scalar_one_or_none():
                ins = KnowledgeInsight(
                    workspace_id=workspace_id,
                    insight_type=InsightType.STALE_KNOWLEDGE,
                    title=title,
                    description=(
                        f"This memory was recorded on {mem.created_at.strftime('%Y-%m-%d')} "
                        "and has not been reviewed or updated in over 30 days."
                    ),
                    suggested_action="Review this memory in the vault to confirm accuracy.",
                    related_memory_ids=[mem.id],
                )
                db.add(ins)
                created_insights.append(ins)

        # 2. Pending review inbox items check
        pending_q = select(func.count(MemoryReview.id)).where(
            MemoryReview.workspace_id == workspace_id,
            MemoryReview.review_status == "pending",
        )
        pending_count = (await db.execute(pending_q)).scalar() or 0
        if pending_count > 0:
            title = f"{pending_count} Pending Review Inbox Items"
            ex_q = select(KnowledgeInsight).where(
                KnowledgeInsight.workspace_id == workspace_id,
                KnowledgeInsight.title == title,
                KnowledgeInsight.is_dismissed.is_(False),
            )
            if not (await db.execute(ex_q)).scalar_one_or_none():
                ins = KnowledgeInsight(
                    workspace_id=workspace_id,
                    insight_type=InsightType.CONTRADICTION_ALERT,
                    title=title,
                    description=(
                        f"You have {pending_count} memory candidates or conflict flags "
                        "waiting in your Review Inbox."
                    ),
                    suggested_action="Navigate to Review Inbox to approve or edit candidates.",
                    related_memory_ids=[],
                )
                db.add(ins)
                created_insights.append(ins)

        # 3. Trending graph entities / high central hubs
        hub_q = (
            select(GraphEntity)
            .where(
                GraphEntity.workspace_id == workspace_id,
                GraphEntity.mention_count >= 2,
            )
            .order_by(desc(GraphEntity.mention_count))
            .limit(2)
        )
        hubs = (await db.execute(hub_q)).scalars().all()
        for hub in hubs:
            title = f"High Centrality: '{hub.name}' ({hub.entity_type.value})"
            ex_q = select(KnowledgeInsight).where(
                KnowledgeInsight.workspace_id == workspace_id,
                KnowledgeInsight.title == title,
                KnowledgeInsight.is_dismissed.is_(False),
            )
            if not (await db.execute(ex_q)).scalar_one_or_none():
                ins = KnowledgeInsight(
                    workspace_id=workspace_id,
                    insight_type=InsightType.TRENDING_TOPIC,
                    title=title,
                    description=(
                        f"Entity '{hub.name}' is heavily referenced ({hub.mention_count} mentions) "
                        "and acts as an architectural hub in your knowledge graph."
                    ),
                    suggested_action="Generate a Topic Research report to consolidate findings.",
                    related_entity_id=hub.id,
                )
                db.add(ins)
                created_insights.append(ins)

        # 4. Knowledge Gap detection: Project entities with no description
        gap_q = (
            select(GraphEntity)
            .where(
                GraphEntity.workspace_id == workspace_id,
                GraphEntity.entity_type == EntityType.PROJECT,
                GraphEntity.description.is_(None),
            )
            .limit(1)
        )
        gap_proj = (await db.execute(gap_q)).scalar_one_or_none()
        if gap_proj:
            title = f"Knowledge Gap: '{gap_proj.name}'"
            ex_q = select(KnowledgeInsight).where(
                KnowledgeInsight.workspace_id == workspace_id,
                KnowledgeInsight.title == title,
                KnowledgeInsight.is_dismissed.is_(False),
            )
            if not (await db.execute(ex_q)).scalar_one_or_none():
                ins = KnowledgeInsight(
                    workspace_id=workspace_id,
                    insight_type=InsightType.KNOWLEDGE_GAP,
                    title=title,
                    description=(
                        f"Project '{gap_proj.name}' was detected in your graph "
                        "but lacks a detailed architectural description or scope."
                    ),
                    suggested_action="Add notes or documentation defining this project's roadmap.",
                    related_entity_id=gap_proj.id,
                )
                db.add(ins)
                created_insights.append(ins)

        if created_insights:
            await db.commit()

        # Fetch all active insights
        active_q = (
            select(KnowledgeInsight)
            .where(
                KnowledgeInsight.workspace_id == workspace_id,
                KnowledgeInsight.is_dismissed.is_(False),
            )
            .order_by(desc(KnowledgeInsight.created_at))
        )
        return list((await db.execute(active_q)).scalars().all())

    @staticmethod
    async def get_insights(
        db: AsyncSession,
        workspace_id: str,
        include_dismissed: bool = False,
    ) -> tuple[list[KnowledgeInsight], int]:
        q = select(KnowledgeInsight).where(KnowledgeInsight.workspace_id == workspace_id)
        if not include_dismissed:
            q = q.where(KnowledgeInsight.is_dismissed.is_(False))

        count_q = select(func.count(KnowledgeInsight.id)).where(
            KnowledgeInsight.workspace_id == workspace_id
        )
        if not include_dismissed:
            count_q = count_q.where(KnowledgeInsight.is_dismissed.is_(False))

        total = (await db.execute(count_q)).scalar() or 0
        q = q.order_by(desc(KnowledgeInsight.created_at))
        insights = (await db.execute(q)).scalars().all()
        return list(insights), total

    @staticmethod
    async def dismiss_insight(
        db: AsyncSession,
        workspace_id: str,
        insight_id: str,
    ) -> KnowledgeInsight:
        q = select(KnowledgeInsight).where(
            KnowledgeInsight.id == insight_id,
            KnowledgeInsight.workspace_id == workspace_id,
        )
        insight = (await db.execute(q)).scalar_one_or_none()
        if not insight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insight not found or unauthorized.",
            )
        insight.is_dismissed = True
        await db.commit()
        await db.refresh(insight)
        return insight
