import abc
import uuid
from typing import Any

from app.core.config import settings
from app.models.workspace import WorkspacePlan


class BasePaymentProvider(abc.ABC):
    @abc.abstractmethod
    async def create_checkout_session(
        self,
        workspace_id: str,
        plan_tier: WorkspacePlan,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a checkout session for plan subscription/upgrade."""
        pass

    @abc.abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel subscription at payment gateway."""
        pass


class StripePaymentProvider(BasePaymentProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            import stripe

            stripe.api_key = self.api_key
            self.stripe = stripe
        except ImportError:
            self.stripe = None

    async def create_checkout_session(
        self,
        workspace_id: str,
        plan_tier: WorkspacePlan,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        if not self.stripe:
            raise RuntimeError("stripe package is not installed.")

        # Real Stripe checkout session creation
        session = self.stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"AI-MemoryVerse {plan_tier.value.capitalize()} Plan",
                        },
                        "unit_amount": (
                            1500
                            if plan_tier == WorkspacePlan.PERSONAL
                            else 3900
                            if plan_tier == WorkspacePlan.PRO
                            else 9900
                        ),
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }
            ],
            mode="subscription",
            metadata={"workspace_id": workspace_id, "plan_tier": plan_tier.value},
            success_url=success_url
            or "http://localhost:3000/billing?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url or "http://localhost:3000/billing?canceled=true",
        )
        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "plan_tier": plan_tier,
        }

    async def cancel_subscription(self, subscription_id: str) -> bool:
        if not self.stripe:
            return False
        try:
            self.stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
            return True
        except Exception:
            return False


class SandboxPaymentProvider(BasePaymentProvider):
    """Deterministic offline payment simulator for testing and local development."""

    async def create_checkout_session(
        self,
        workspace_id: str,
        plan_tier: WorkspacePlan,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        session_id = f"cs_sandbox_{uuid.uuid4().hex[:16]}"
        base_url = success_url or "http://localhost:3000/billing"
        separator = "&" if "?" in base_url else "?"
        simulated_url = (
            f"{base_url}{separator}session_id={session_id}&plan={plan_tier.value}&status=success"
        )
        return {
            "session_id": session_id,
            "checkout_url": simulated_url,
            "plan_tier": plan_tier,
        }

    async def cancel_subscription(self, subscription_id: str) -> bool:
        return True


def get_payment_provider() -> BasePaymentProvider:
    if settings.PAYMENT_PROVIDER == "stripe" and settings.PAYMENT_SECRET_KEY:
        return StripePaymentProvider(api_key=settings.PAYMENT_SECRET_KEY)
    return SandboxPaymentProvider()
