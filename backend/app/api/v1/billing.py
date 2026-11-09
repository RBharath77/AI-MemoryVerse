from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace, get_db
from app.core.config import settings
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.billing import (
    PLAN_CATALOG,
    CheckoutRequest,
    CheckoutResponse,
    PlanInfo,
    SubscriptionResponse,
    WorkspaceUsageResponse,
)
from app.schemas.common import APIResponse
from app.services.billing_service import BillingService
from app.services.payment_provider import get_payment_provider

router = APIRouter()


async def _assert_billing_admin(
    db: AsyncSession,
    workspace_id: str,
    user: User,
) -> None:
    """Enforce that only workspace OWNER or ADMIN can perform financial/subscription operations."""
    if user.is_superuser:
        return
    q = select(WorkspaceMember.role).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    )
    role = (await db.execute(q)).scalar_one_or_none()
    if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing and subscription operations require workspace Admin or Owner permissions.",
        )


@router.get("/plans", response_model=APIResponse[list[PlanInfo]])
async def get_plans_catalog() -> APIResponse[list[PlanInfo]]:
    """Return all available subscription tiers, pricing, and limits."""
    plans = list(PLAN_CATALOG.values())
    return APIResponse(data=plans)


@router.get("/usage", response_model=APIResponse[WorkspaceUsageResponse])
async def get_workspace_usage(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[WorkspaceUsageResponse]:
    """Return real-time usage metrics and quota consumption for active workspace."""
    usage = await BillingService.get_workspace_usage(db, workspace.id)
    return APIResponse(data=usage)


@router.get("/subscription", response_model=APIResponse[SubscriptionResponse])
async def get_subscription(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SubscriptionResponse]:
    """Return current subscription state, plan tier, and invoice history."""
    sub = await BillingService.get_subscription_details(db, workspace.id)
    return APIResponse(data=sub)


@router.post("/checkout", response_model=APIResponse[CheckoutResponse])
async def create_checkout_session(
    payload: CheckoutRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CheckoutResponse]:
    """Initialize a payment checkout session for plan upgrade."""
    await _assert_billing_admin(db, workspace.id, current_user)
    provider = get_payment_provider()
    session_data = await provider.create_checkout_session(
        workspace_id=workspace.id,
        plan_tier=payload.plan_tier,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )
    return APIResponse(
        data=CheckoutResponse(
            checkout_url=session_data["checkout_url"],
            session_id=session_data["session_id"],
            plan_tier=session_data["plan_tier"],
        )
    )


@router.post("/upgrade", response_model=APIResponse[SubscriptionResponse])
async def upgrade_plan_direct(
    payload: CheckoutRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SubscriptionResponse]:
    """Instantly apply plan upgrade (supported in sandbox mode and verified payments)."""
    await _assert_billing_admin(db, workspace.id, current_user)
    if settings.PAYMENT_PROVIDER != "sandbox" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct plan upgrades are restricted to sandbox environments. Please complete payment via /checkout.",
        )

    updated_sub = await BillingService.upgrade_plan(
        db=db,
        workspace_id=workspace.id,
        new_plan=payload.plan_tier,
        user_id=current_user.id,
    )
    return APIResponse(data=updated_sub)


@router.post("/cancel", response_model=APIResponse[SubscriptionResponse])
async def cancel_subscription(
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SubscriptionResponse]:
    """Schedule current subscription to cancel at the end of the billing period."""
    await _assert_billing_admin(db, workspace.id, current_user)
    updated_sub = await BillingService.cancel_subscription(
        db=db,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )
    return APIResponse(data=updated_sub)
