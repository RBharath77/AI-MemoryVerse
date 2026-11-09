import json
import logging
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ssrf import validate_and_resolve_url_safe
from app.core.webhook import WebhookSignatureService
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.models.workspace import WorkspaceMember, WorkspaceRole
from app.schemas.webhook import WebhookEndpointCreate

logger = logging.getLogger(__name__)


class WebhookDispatcherService:
    """
    Enterprise Webhook Dispatcher and Dead-Letter Queue (DLQ) Management Engine.
    Enforces SSRF validation on destination URLs, signs outgoing payloads with HMAC-SHA256,
    tracks delivery attempts, and quarantines failed requests into the DLQ with manual redrive capability.
    """

    MAX_RETRIES: int = 3

    @staticmethod
    def _mask_secret(secret: str) -> str:
        if not secret:
            return ""
        if len(secret) <= 8:
            return "••••••••"
        return f"{secret[:4]}••••{secret[-4:]}"

    @staticmethod
    async def _verify_admin(db: AsyncSession, workspace_id: str, user_id: str) -> None:
        q = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        res = await db.execute(q)
        member = res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to manage workspace webhooks.",
            )

    @staticmethod
    async def register_endpoint(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: WebhookEndpointCreate,
    ) -> dict:
        await WebhookDispatcherService._verify_admin(db, workspace_id, user_id)

        # 1. Anti-SSRF Destination URL Validation
        safe_url, _ = validate_and_resolve_url_safe(data.url)

        secret = data.secret or f"whsec_{uuid.uuid4().hex}"
        event_types = data.event_types or ["*"]

        endpoint = WebhookEndpoint(
            workspace_id=workspace_id,
            url=data.url,
            secret=secret,
            event_types=event_types,
            is_active=True,
        )
        db.add(endpoint)
        await db.commit()
        await db.refresh(endpoint)

        return {
            "id": endpoint.id,
            "workspace_id": endpoint.workspace_id,
            "url": endpoint.url,
            "masked_secret": WebhookDispatcherService._mask_secret(secret),
            "event_types": endpoint.event_types,
            "is_active": endpoint.is_active,
            "created_at": endpoint.created_at,
        }

    @staticmethod
    async def list_endpoints(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> list[dict]:
        await WebhookDispatcherService._verify_admin(db, workspace_id, user_id)
        q = select(WebhookEndpoint).where(WebhookEndpoint.workspace_id == workspace_id)
        res = await db.execute(q)
        endpoints = res.scalars().all()

        return [
            {
                "id": ep.id,
                "workspace_id": ep.workspace_id,
                "url": ep.url,
                "masked_secret": WebhookDispatcherService._mask_secret(ep.secret),
                "event_types": ep.event_types,
                "is_active": ep.is_active,
                "created_at": ep.created_at,
            }
            for ep in endpoints
        ]

    @staticmethod
    async def delete_endpoint(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        endpoint_id: str,
    ) -> bool:
        await WebhookDispatcherService._verify_admin(db, workspace_id, user_id)
        q = select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.workspace_id == workspace_id,
        )
        res = await db.execute(q)
        ep = res.scalar_one_or_none()
        if not ep:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook endpoint not found.",
            )

        await db.delete(ep)
        await db.commit()
        return True

    @staticmethod
    async def dispatch_event(
        db: AsyncSession,
        workspace_id: str,
        event_type: str,
        payload: dict,
    ) -> list[dict]:
        """
        Deliver signed event payload to all subscribed workspace endpoints.
        Quarantines delivery record into DLQ if target fails or times out.
        """
        q = select(WebhookEndpoint).where(
            WebhookEndpoint.workspace_id == workspace_id,
            WebhookEndpoint.is_active.is_(True),
        )
        res = await db.execute(q)
        endpoints = res.scalars().all()

        deliveries_out = []
        payload_bytes = json.dumps(payload, default=str).encode("utf-8")

        for ep in endpoints:
            # Check subscription filter
            if "*" not in ep.event_types and event_type not in ep.event_types:
                continue

            sig_header, ts = WebhookSignatureService.sign_payload(payload_bytes, ep.secret)
            headers = {
                "Content-Type": "application/json",
                "X-MemoryVerse-Event": event_type,
                "X-MemoryVerse-Signature": sig_header,
                "X-MemoryVerse-Timestamp": str(ts),
            }

            delivery = WebhookDelivery(
                workspace_id=workspace_id,
                endpoint_id=ep.id,
                event_type=event_type,
                payload=payload,
                attempt_count=1,
                is_dlq=False,
            )
            db.add(delivery)
            await db.flush()

            # Attempt dispatch
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(ep.url, content=payload_bytes, headers=headers)
                    delivery.status_code = resp.status_code
                    delivery.response_body = resp.text[:1000]

                    if 200 <= resp.status_code < 300:
                        delivery.delivered_at = datetime.now(UTC)
                        delivery.is_dlq = False
                    else:
                        delivery.is_dlq = True
            except Exception as exc:
                delivery.status_code = 0
                delivery.response_body = f"Connection error: {str(exc)}"[:1000]
                delivery.is_dlq = True

            deliveries_out.append(
                {
                    "id": delivery.id,
                    "workspace_id": delivery.workspace_id,
                    "endpoint_id": delivery.endpoint_id,
                    "event_type": delivery.event_type,
                    "status_code": delivery.status_code,
                    "is_dlq": delivery.is_dlq,
                    "attempt_count": delivery.attempt_count,
                    "delivered_at": delivery.delivered_at,
                }
            )

        await db.commit()
        return deliveries_out

    @staticmethod
    async def list_dlq(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> list[WebhookDelivery]:
        await WebhookDispatcherService._verify_admin(db, workspace_id, user_id)
        q = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.workspace_id == workspace_id,
                WebhookDelivery.is_dlq.is_(True),
            )
            .order_by(WebhookDelivery.created_at.desc())
        )
        res = await db.execute(q)
        return list(res.scalars().all())

    @staticmethod
    async def redrive_delivery(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        delivery_id: str,
    ) -> WebhookDelivery:
        await WebhookDispatcherService._verify_admin(db, workspace_id, user_id)

        q = select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.workspace_id == workspace_id,
        )
        res = await db.execute(q)
        delivery = res.scalar_one_or_none()
        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery record not found.",
            )

        # Fetch endpoint
        ep_res = await db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.id == delivery.endpoint_id)
        )
        ep = ep_res.scalar_one_or_none()
        if not ep:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target webhook endpoint no longer exists.",
            )

        payload_bytes = json.dumps(delivery.payload, default=str).encode("utf-8")
        sig_header, ts = WebhookSignatureService.sign_payload(payload_bytes, ep.secret)
        headers = {
            "Content-Type": "application/json",
            "X-MemoryVerse-Event": delivery.event_type,
            "X-MemoryVerse-Signature": sig_header,
            "X-MemoryVerse-Timestamp": str(ts),
        }

        delivery.attempt_count += 1
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(ep.url, content=payload_bytes, headers=headers)
                delivery.status_code = resp.status_code
                delivery.response_body = resp.text[:1000]

                if 200 <= resp.status_code < 300:
                    delivery.delivered_at = datetime.now(UTC)
                    delivery.is_dlq = False
                else:
                    delivery.is_dlq = True
        except Exception as exc:
            delivery.status_code = 0
            delivery.response_body = f"Connection error: {str(exc)}"[:1000]
            delivery.is_dlq = True

        await db.commit()
        await db.refresh(delivery)
        return delivery
