from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.ai.table_extractor import StructuredTableExtractor
from app.core import database as core_db
from app.models.memory import Memory, MemoryCategory


@pytest.mark.asyncio
async def test_markdown_table_extraction_and_chunking(client: AsyncClient):
    """Verify StructuredTableExtractor parses markdown tables into structured records and header-preserving chunks."""
    markdown_doc = """# Financial Overview

Here is the quarterly regional breakdown:

| Region | Q1 Revenue | Q2 Revenue | Margin |
| :--- | :--- | :--- | :--- |
| North America | $12.5M | $14.2M | 24% |
| Europe | $8.1M | $9.3M | 19% |
| Asia Pacific | $15.0M | $18.4M | 28% |
| Latin America | $3.2M | $3.8M | 15% |

Summary analysis follows below the table.
"""

    # 1. Direct Extractor Engine Test
    tables = StructuredTableExtractor.extract_markdown_tables(markdown_doc, rows_per_chunk=2)
    assert len(tables) == 1
    t = tables[0]
    assert t.columns == ["Region", "Q1 Revenue", "Q2 Revenue", "Margin"]
    assert t.row_count == 4
    assert len(t.structured_records) == 4
    assert t.structured_records[0]["Region"] == "North America"
    assert t.structured_records[0]["Q1 Revenue"] == "$12.5M"
    assert t.structured_records[2]["Region"] == "Asia Pacific"

    # Verify header preservation across chunks
    assert len(t.chunks) == 2
    for chunk in t.chunks:
        assert "| Region | Q1 Revenue | Q2 Revenue | Margin |" in chunk.content
        assert "| :--- | :--- | :--- | :--- |" in chunk.content

    # 2. API Endpoint Test
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tabletester@phase31.ai",
            "password": "Password123!",
            "full_name": "Table Tester",
            "workspace_name": "Table WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    resp = await client.post(
        "/api/v1/documents/parse-tables",
        json={"content": markdown_doc, "rows_per_chunk": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["total_tables_detected"] == 1
    parsed_t = res_data["tables"][0]
    assert parsed_t["columns"] == ["Region", "Q1 Revenue", "Q2 Revenue", "Margin"]
    assert parsed_t["row_count"] == 4
    assert len(parsed_t["records"]) == 4
    assert len(parsed_t["chunks"]) == 2


@pytest.mark.asyncio
async def test_csv_table_extraction_and_chunking(client: AsyncClient):
    """Verify CSV extraction into column schemas, structured records, and markdown tabular chunks."""
    csv_payload = """Hostname,IP Address,Environment,Role,Status
node-01,10.0.1.10,production,k8s-control-plane,ready
node-02,10.0.1.11,production,k8s-worker,ready
node-03,10.0.1.12,staging,redis-cache,degraded
node-04,10.0.1.13,development,database-primary,ready
"""

    tables = StructuredTableExtractor.extract_csv_tables(csv_payload, rows_per_chunk=2)
    assert len(tables) == 1
    t = tables[0]
    assert t.columns == ["Hostname", "IP Address", "Environment", "Role", "Status"]
    assert t.row_count == 4
    assert t.structured_records[0]["Hostname"] == "node-01"
    assert t.structured_records[2]["Role"] == "redis-cache"
    assert t.structured_records[2]["Status"] == "degraded"

    # Tabular chunks should be formatted in Markdown with header preserved
    assert len(t.chunks) == 2
    assert "| Hostname | IP Address | Environment | Role | Status |" in t.chunks[0].content
    assert "| node-01 | 10.0.1.10 | production | k8s-control-plane | ready |" in t.chunks[0].content
    assert "| Hostname | IP Address | Environment | Role | Status |" in t.chunks[1].content
    assert "| node-03 | 10.0.1.12 | staging | redis-cache | degraded |" in t.chunks[1].content


@pytest.mark.asyncio
async def test_temporal_memory_centroid_drift_detection(client: AsyncClient):
    """Verify MemoryDriftDetector detects semantic centroid shifts and tag acceleration."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "drifttester@phase31.ai",
            "password": "Password123!",
            "full_name": "Drift Tester",
            "workspace_name": "Drift WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    u_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Seed baseline and recent memories into DB
    async with core_db.AsyncSessionLocal() as session:
        now_dt = datetime.now(UTC)
        old_dt = now_dt - timedelta(days=45)

        m1 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="PostgreSQL database query optimization using B-Tree and GIN indexes",
            category=MemoryCategory.SEMANTIC,
            importance=8,
            tags=["postgres", "sql", "database"],
            created_at=old_dt,
        )
        m2 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Relational database transaction isolation levels and ACID benchmarks",
            category=MemoryCategory.SEMANTIC,
            importance=7,
            tags=["postgres", "database", "acid"],
            created_at=old_dt,
        )
        m3 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Kubernetes pod auto-scaling and Helm chart ingress deployment",
            category=MemoryCategory.PREFERENCE,
            importance=9,
            tags=["kubernetes", "k8s", "helm"],
            created_at=now_dt,
        )
        m4 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Container orchestration with microservice service mesh and Envoy proxy",
            category=MemoryCategory.PREFERENCE,
            importance=8,
            tags=["kubernetes", "envoy", "mesh"],
            created_at=now_dt,
        )
        session.add_all([m1, m2, m3, m4])
        await session.commit()

    # Query API drift-analysis
    resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/drift-analysis?window_days=30",
        headers=headers,
    )
    assert resp.status_code == 200
    drift_data = resp.json()["data"]
    assert drift_data["workspace_id"] == ws_id
    assert drift_data["baseline_memory_count"] >= 2
    assert drift_data["recent_memory_count"] >= 2
    assert drift_data["centroid_distance"] > 0.0
    assert drift_data["drift_status"] in ("MODERATE_DRIFT", "HIGH_DRIFT", "STABLE")

    # Accelerating tags should include kubernetes or mesh
    accel_tags = [t["tag"] for t in drift_data["top_accelerating_topics"]]
    assert any("k" in tag or "mesh" in tag or "envoy" in tag or "helm" in tag for tag in accel_tags)


@pytest.mark.asyncio
async def test_compliance_scorecard_evaluation(client: AsyncClient):
    """Verify 8-point regulatory compliance evaluation and letter grade scoring."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "compliancetester@phase31.ai",
            "password": "Password123!",
            "full_name": "Compliance Tester",
            "workspace_name": "Compliance WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/compliance/scorecard",
        headers=headers,
    )
    assert resp.status_code == 200
    scorecard = resp.json()["data"]
    assert scorecard["workspace_id"] == ws_id
    assert 0 <= scorecard["compliance_score"] <= 100
    assert scorecard["platform_grade"] in ("A+", "A", "B", "C", "D")

    # Verify all 8 regulatory controls are evaluated
    ctrl_ids = [c["control_id"] for c in scorecard["controls"]]
    expected_controls = [
        "CMEK_ENCRYPTION",
        "DLP_ENFORCEMENT",
        "CIDR_GEOFENCING",
        "AUDIT_CHAIN_INTEGRITY",
        "MEMORY_HMAC_TAMPER",
        "MEMBER_MFA_ADOPTION",
        "TTL_RETENTION_PRUNING",
        "STORAGE_QUOTA_COMPLIANCE",
    ]
    for exp in expected_controls:
        assert exp in ctrl_ids

    # Each control must have a valid status
    for c in scorecard["controls"]:
        assert c["status"] in ("PASS", "WARN", "FAIL")
        assert len(c["details"]) > 0


@pytest.mark.asyncio
async def test_compliance_auto_remediation_execution(client: AsyncClient):
    """Verify automated remediation resolves auto-fixable controls (DLP, TTL, HMAC) and elevates score."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "remediatetester@phase31.ai",
            "password": "Password123!",
            "full_name": "Remediate Tester",
            "workspace_name": "Remediate WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Fetch initial scorecard
    initial_resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/compliance/scorecard",
        headers=headers,
    )
    assert initial_resp.status_code == 200
    initial_score = initial_resp.json()["data"]["compliance_score"]

    # Execute auto-remediation
    remed_resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/compliance/auto-remediate",
        headers=headers,
    )
    assert remed_resp.status_code == 200
    remed_data = remed_resp.json()["data"]
    assert remed_data["workspace_id"] == ws_id
    assert remed_data["updated_score"] >= remed_data["previous_score"]
    assert "DLP_ENFORCEMENT" in remed_data["remediated_controls"]
    assert "TTL_RETENTION_PRUNING" in remed_data["remediated_controls"]

    # Post-remediation verification
    post_resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/compliance/scorecard",
        headers=headers,
    )
    assert post_resp.status_code == 200
    post_card = post_resp.json()["data"]
    assert post_card["compliance_score"] >= initial_score

    # Controls should now be PASS
    post_controls = {c["control_id"]: c["status"] for c in post_card["controls"]}
    assert post_controls["DLP_ENFORCEMENT"] == "PASS"
    assert post_controls["TTL_RETENTION_PRUNING"] == "PASS"


@pytest.mark.asyncio
async def test_compliance_and_drift_multi_tenant_isolation(client: AsyncClient):
    """Verify strict multi-tenant isolation prevents cross-workspace drift and compliance inspection."""
    # Register Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_a_p31@phase31.ai",
            "password": "Password123!",
            "full_name": "Tenant A",
            "workspace_name": "Workspace A",
        },
    )
    assert reg_a.status_code == 201
    auth_a = reg_a.json()["data"]
    _token_a = auth_a["tokens"]["access_token"]
    ws_a_id = auth_a["workspace"]["id"]

    # Register Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_b_p31@phase31.ai",
            "password": "Password123!",
            "full_name": "Tenant B",
            "workspace_name": "Workspace B",
        },
    )
    assert reg_b.status_code == 201
    auth_b = reg_b.json()["data"]
    token_b = auth_b["tokens"]["access_token"]
    ws_b_id = auth_b["workspace"]["id"]

    # Tenant B tries to inspect Tenant A's drift telemetry
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b_id}
    drift_attack = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/drift-analysis",
        headers=headers_b,
    )
    assert drift_attack.status_code in (403, 404)

    # Tenant B tries to inspect Tenant A's compliance scorecard
    card_attack = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/compliance/scorecard",
        headers=headers_b,
    )
    assert card_attack.status_code in (403, 404)

    # Tenant B tries to trigger auto-remediation on Tenant A
    remed_attack = await client.post(
        f"/api/v1/workspaces/{ws_a_id}/compliance/auto-remediate",
        headers=headers_b,
    )
    assert remed_attack.status_code in (403, 404)
