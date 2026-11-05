import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_plan_catalog_retrieval(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/billing/plans",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    plans = data["data"]
    assert len(plans) == 4

    tiers = [p["tier"] for p in plans]
    assert "free" in tiers
    assert "personal" in tiers
    assert "pro" in tiers
    assert "team" in tiers

    free_plan = next(p for p in plans if p["tier"] == "free")
    assert free_plan["price_monthly"] == 0
    assert free_plan["limits"]["max_memories"] == 100

    pro_plan = next(p for p in plans if p["tier"] == "pro")
    assert pro_plan["price_monthly"] == 39
    assert pro_plan["limits"]["max_memories"] == 25000


@pytest.mark.asyncio
async def test_workspace_usage_metering(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/billing/usage",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    usage = data["data"]

    assert usage["plan_tier"] == "free"
    assert "memories" in usage
    assert "documents" in usage
    assert "storage" in usage
    assert "ai_queries" in usage
    assert usage["memories"]["limit"] == 100
    assert isinstance(usage["memories"]["used"], int)


@pytest.mark.asyncio
async def test_subscription_lifecycle_and_invoices(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/billing/subscription",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    sub = data["data"]

    assert sub["plan_tier"] == "free"
    assert sub["status"] == "active"
    assert sub["cancel_at_period_end"] is False


@pytest.mark.asyncio
async def test_sandbox_checkout_session(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan_tier": "pro",
            "success_url": "http://localhost:3000/billing?status=success",
            "cancel_url": "http://localhost:3000/billing?status=canceled",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    res = data["data"]
    assert "cs_sandbox_" in res["session_id"]
    assert "plan=pro" in res["checkout_url"]


@pytest.mark.asyncio
async def test_plan_upgrade_and_invoice_generation(client: AsyncClient, auth_headers: dict):
    # Upgrade to Personal tier ($15/mo)
    upgrade_res = await client.post(
        "/api/v1/billing/upgrade",
        headers=auth_headers,
        json={"plan_tier": "personal"},
    )
    assert upgrade_res.status_code == 200
    sub = upgrade_res.json()["data"]
    assert sub["plan_tier"] == "personal"
    assert sub["status"] == "active"
    assert len(sub["invoices"]) >= 1

    invoice = sub["invoices"][0]
    assert invoice["amount_cents"] == 1500
    assert invoice["status"] == "paid"
    assert "INV-" in invoice["invoice_number"]

    # Verify usage reflects updated personal limits (2,500 memories)
    usage_res = await client.get(
        "/api/v1/billing/usage",
        headers=auth_headers,
    )
    assert usage_res.status_code == 200
    usage = usage_res.json()["data"]
    assert usage["plan_tier"] == "personal"
    assert usage["memories"]["limit"] == 2500


@pytest.mark.asyncio
async def test_subscription_cancellation(client: AsyncClient, auth_headers: dict):
    cancel_res = await client.post(
        "/api/v1/billing/cancel",
        headers=auth_headers,
    )
    assert cancel_res.status_code == 200
    sub = cancel_res.json()["data"]
    assert sub["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_admin_system_overview_and_telemetry(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/admin/overview",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    overview = data["data"]

    assert overview["total_users"] >= 1
    assert overview["total_workspaces"] >= 1
    assert "health" in overview
    assert overview["health"]["database"]["status"] == "healthy"
    assert "latency_ms" in overview["health"]["database"]
    assert overview["health"]["storage_provider"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_audit_logs_trail(client: AsyncClient, auth_headers: dict):
    # Trigger an upgrade to create audit log
    await client.post(
        "/api/v1/billing/upgrade",
        headers=auth_headers,
        json={"plan_tier": "pro"},
    )

    response = await client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    logs = data["data"]
    assert len(logs) >= 1

    actions = [log_item["action"] for log_item in logs]
    assert "billing.plan_upgraded" in actions


@pytest.mark.asyncio
async def test_billing_multi_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
):
    # Register a second tenant
    user2_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant2@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Tenant Two",
            "workspace_name": "Tenant Two Workspace",
        },
    )
    assert user2_resp.status_code == 201
    user2_data = user2_resp.json()["data"]
    user2_headers = {
        "Authorization": f"Bearer {user2_data['tokens']['access_token']}",
        "X-Workspace-ID": user2_data["workspace"]["id"],
    }

    # User 1 upgrades Workspace 1 to Team
    upgrade_res = await client.post(
        "/api/v1/billing/upgrade",
        headers=auth_headers,
        json={"plan_tier": "team"},
    )
    assert upgrade_res.status_code == 200

    # User 2 checks their workspace; must remain Free
    user2_sub_res = await client.get(
        "/api/v1/billing/subscription",
        headers=user2_headers,
    )
    assert user2_sub_res.status_code == 200
    user2_sub = user2_sub_res.json()["data"]
    assert user2_sub["workspace_id"] == user2_data["workspace"]["id"]
    assert user2_sub["plan_tier"] == "free"
    assert len(user2_sub["invoices"]) == 0

    # User 2 checks usage; must be free limits
    user2_usage_res = await client.get(
        "/api/v1/billing/usage",
        headers=user2_headers,
    )
    assert user2_usage_res.status_code == 200
    assert user2_usage_res.json()["data"]["plan_tier"] == "free"
    assert user2_usage_res.json()["data"]["memories"]["limit"] == 100
