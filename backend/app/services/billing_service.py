import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import AuditEvent, Invoice, Subscription, SubscriptionStatus
from app.models.chat import ChatMessage, Conversation
from app.models.document import Document
from app.models.memory import Memory, MemoryStatus
from app.models.workspace import Workspace, WorkspacePlan
from app.schemas.billing import (
    PLAN_CATALOG,
    InvoiceResponse,
    SubscriptionResponse,
    UsageMetric,
    WorkspaceUsageResponse,
)


class BillingService:
    @staticmethod
    async def get_or_create_subscription(db: AsyncSession, workspace_id: str) -> Subscription:
        stmt = select(Subscription).where(Subscription.workspace_id == workspace_id)
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if not sub:
            # Look up workspace plan
            ws_stmt = select(Workspace).where(Workspace.id == workspace_id)
            ws_res = await db.execute(ws_stmt)
            ws = ws_res.scalar_one_or_none()
            plan = ws.plan_tier if ws else WorkspacePlan.FREE

            now = datetime.now(UTC)
            sub = Subscription(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                plan_tier=plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                cancel_at_period_end=False,
            )
            db.add(sub)
            await db.commit()
            await db.refresh(sub)

        return sub

    @staticmethod
    async def get_workspace_usage(db: AsyncSession, workspace_id: str) -> WorkspaceUsageResponse:
        # 1. Workspace plan
        ws_stmt = select(Workspace).where(Workspace.id == workspace_id)
        ws_res = await db.execute(ws_stmt)
        ws = ws_res.scalar_one_or_none()
        plan_tier = ws.plan_tier if ws else WorkspacePlan.FREE
        plan_limits = PLAN_CATALOG[plan_tier].limits

        # 2. Memories count
        mem_stmt = select(func.count(Memory.id)).where(
            Memory.workspace_id == workspace_id,
            Memory.status != MemoryStatus.ARCHIVED,
        )
        mem_count = (await db.execute(mem_stmt)).scalar() or 0

        # 3. Documents count and Storage size
        doc_stmt = select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.file_size), 0),
        ).where(Document.workspace_id == workspace_id)
        doc_res = (await db.execute(doc_stmt)).first()
        doc_count = doc_res[0] if doc_res else 0
        storage_bytes = doc_res[1] if doc_res else 0

        # 4. AI queries count
        ai_stmt = (
            select(func.count(ChatMessage.id))
            .join(Conversation, ChatMessage.conversation_id == Conversation.id)
            .where(Conversation.workspace_id == workspace_id)
        )
        ai_queries = (await db.execute(ai_stmt)).scalar() or 0

        def calc_percentage(used: int, limit: int) -> float:
            if limit <= 0:
                return 0.0
            return round(min(100.0, (used / limit) * 100), 1)

        return WorkspaceUsageResponse(
            plan_tier=plan_tier,
            memories=UsageMetric(
                used=mem_count,
                limit=plan_limits.max_memories,
                percentage=calc_percentage(mem_count, plan_limits.max_memories),
                unit="records",
            ),
            documents=UsageMetric(
                used=doc_count,
                limit=plan_limits.max_documents,
                percentage=calc_percentage(doc_count, plan_limits.max_documents),
                unit="files",
            ),
            storage=UsageMetric(
                used=storage_bytes,
                limit=plan_limits.max_storage_bytes,
                percentage=calc_percentage(storage_bytes, plan_limits.max_storage_bytes),
                unit="bytes",
            ),
            ai_queries=UsageMetric(
                used=ai_queries,
                limit=plan_limits.max_ai_queries,
                percentage=calc_percentage(ai_queries, plan_limits.max_ai_queries),
                unit="requests",
            ),
        )

    @staticmethod
    async def get_subscription_details(db: AsyncSession, workspace_id: str) -> SubscriptionResponse:
        sub = await BillingService.get_or_create_subscription(db, workspace_id)

        # Invoices
        inv_stmt = (
            select(Invoice)
            .where(Invoice.workspace_id == workspace_id)
            .order_by(Invoice.created_at.desc())
        )
        invoices = (await db.execute(inv_stmt)).scalars().all()

        return SubscriptionResponse(
            id=sub.id,
            workspace_id=sub.workspace_id,
            plan_tier=sub.plan_tier,
            status=sub.status.value,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            invoices=[
                InvoiceResponse(
                    id=inv.id,
                    invoice_number=inv.invoice_number,
                    amount_cents=inv.amount_cents,
                    currency=inv.currency,
                    status=inv.status,
                    invoice_url=inv.invoice_url,
                    paid_at=inv.paid_at,
                    created_at=inv.created_at,
                )
                for inv in invoices
            ],
        )

    @staticmethod
    async def upgrade_plan(
        db: AsyncSession,
        workspace_id: str,
        new_plan: WorkspacePlan,
        user_id: str | None = None,
    ) -> SubscriptionResponse:
        # Update workspace plan
        ws_stmt = select(Workspace).where(Workspace.id == workspace_id)
        ws = (await db.execute(ws_stmt)).scalar_one_or_none()
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

        ws.plan_tier = new_plan

        sub = await BillingService.get_or_create_subscription(db, workspace_id)
        now = datetime.now(UTC)
        sub.plan_tier = new_plan
        sub.status = SubscriptionStatus.ACTIVE
        sub.cancel_at_period_end = False
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)

        # Create paid invoice record if upgrading to paid tier
        plan_info = PLAN_CATALOG[new_plan]
        if plan_info.price_monthly > 0:
            invoice = Invoice(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                invoice_number=f"INV-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}",
                amount_cents=plan_info.price_monthly * 100,
                currency="USD",
                status="paid",
                paid_at=now,
                invoice_url=f"/invoices/download/{uuid.uuid4().hex[:12]}",
            )
            db.add(invoice)

        # Record audit log
        audit = AuditEvent(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            action="billing.plan_upgraded",
            details={"previous_plan": ws.plan_tier.value, "new_plan": new_plan.value},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(sub)
        return await BillingService.get_subscription_details(db, workspace_id)

    @staticmethod
    async def cancel_subscription(
        db: AsyncSession,
        workspace_id: str,
        user_id: str | None = None,
    ) -> SubscriptionResponse:
        sub = await BillingService.get_or_create_subscription(db, workspace_id)
        sub.cancel_at_period_end = True

        audit = AuditEvent(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            action="billing.subscription_cancelled",
            details={"plan_tier": sub.plan_tier.value},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(sub)
        return await BillingService.get_subscription_details(db, workspace_id)
