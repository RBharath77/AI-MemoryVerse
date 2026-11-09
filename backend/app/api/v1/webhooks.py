from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookDispatchEventRequest,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
)
from app.services.webhook_dispatcher_service import WebhookDispatcherService

router = APIRouter(prefix="/workspaces/{workspace_id}/webhooks", tags=["Webhooks"])


@router.post(
    "",
    response_model=APIResponse[WebhookEndpointResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register_webhook_endpoint(
    workspace_id: str,
    data: WebhookEndpointCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Register destination webhook URL with automated SSRF validation and HMAC secret."""
    res = await WebhookDispatcherService.register_endpoint(db, workspace_id, current_user.id, data)
    return APIResponse(
        success=True,
        data=WebhookEndpointResponse(**res),
    )


@router.get("", response_model=APIResponse[list[WebhookEndpointResponse]])
async def list_webhook_endpoints(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List registered workspace webhook endpoints with masked secrets."""
    endpoints = await WebhookDispatcherService.list_endpoints(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=[WebhookEndpointResponse(**ep) for ep in endpoints],
    )


@router.delete("/{endpoint_id}", response_model=APIResponse[dict])
async def delete_webhook_endpoint(
    workspace_id: str,
    endpoint_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a registered webhook endpoint and associated delivery history."""
    deleted = await WebhookDispatcherService.delete_endpoint(
        db, workspace_id, current_user.id, endpoint_id
    )
    return APIResponse(
        success=True,
        data={"deleted": deleted, "endpoint_id": endpoint_id},
    )


@router.post("/dispatch", response_model=APIResponse[list[dict]])
async def trigger_event_dispatch(
    workspace_id: str,
    data: WebhookDispatchEventRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger real-time webhook event dispatch to subscribed workspace endpoints."""
    await WebhookDispatcherService._verify_admin(db, workspace_id, current_user.id)
    deliveries = await WebhookDispatcherService.dispatch_event(
        db, workspace_id, data.event_type, data.payload
    )
    return APIResponse(
        success=True,
        data=deliveries,
    )


@router.get("/dlq", response_model=APIResponse[list[WebhookDeliveryResponse]])
async def list_webhook_dlq(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Inspect Dead-Letter Queue (DLQ) for failed webhook delivery attempts."""
    dlq_items = await WebhookDispatcherService.list_dlq(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=[WebhookDeliveryResponse.model_validate(item) for item in dlq_items],
    )


@router.post(
    "/dlq/{delivery_id}/redrive",
    response_model=APIResponse[WebhookDeliveryResponse],
)
async def redrive_webhook_delivery(
    workspace_id: str,
    delivery_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually redrive a failed delivery record from the Dead-Letter Queue."""
    delivery = await WebhookDispatcherService.redrive_delivery(
        db, workspace_id, current_user.id, delivery_id
    )
    return APIResponse(
        success=True,
        data=WebhookDeliveryResponse.model_validate(delivery),
    )
