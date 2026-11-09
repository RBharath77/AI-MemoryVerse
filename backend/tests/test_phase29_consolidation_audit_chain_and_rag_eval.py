from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import database as core_db
from app.core.audit import SecurityAuditLogger
from app.models.billing import AuditEvent
from app.models.memory import Memory, MemoryCategory, MemoryLink


@pytest.mark.asyncio
async def test_memory_auto_consolidation_dry_run_and_clustering(client: AsyncClient):
    """Verify memory auto-consolidation clusters memories and previews synthesis in dry-run mode."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "consolidator@phase29.ai",
            "password": "Password123!",
            "full_name": "Memory Consolidator",
            "workspace_name": "Consolidation WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Insert 4 episodic memories: 2 for Theme, 2 for Database
    m1 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "User prefers Solarized Dark theme in VS Code",
            "category": "episodic",
            "tags": ["theme", "editor"],
        },
    )
    assert m1.status_code == 201

    m2 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "User switches to dark theme in terminals to reduce eye strain",
            "category": "episodic",
            "tags": ["theme", "terminal"],
        },
    )
    assert m2.status_code == 201

    m3 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Production database runs PostgreSQL 16 with pgvector",
            "category": "episodic",
            "tags": ["database", "infrastructure"],
        },
    )
    assert m3.status_code == 201

    m4 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Staging database mirrors PostgreSQL 16 vector configuration",
            "category": "episodic",
            "tags": ["database", "infrastructure"],
        },
    )
    assert m4.status_code == 201

    # 3. Dry-run Auto-Consolidation
    dry_resp = await client.post(
        "/api/v1/memories/auto-consolidate",
        headers=headers,
        json={"dry_run": True, "min_memories": 2},
    )
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()["data"]

    assert dry_data["dry_run"] is True
    assert dry_data["consolidated_memories_created"] == 0
    assert len(dry_data["new_memory_ids"]) == 0
    assert dry_data["total_source_memories"] >= 4
    assert len(dry_data["clusters"]) >= 2

    # Verify cluster previews
    topics = [c["topic"].lower() for c in dry_data["clusters"]]
    assert any("theme" in t for t in topics)
    assert any("database" in t for t in topics)

    for cluster in dry_data["clusters"]:
        assert len(cluster["source_memory_ids"]) >= 2
        assert len(cluster["synthesized_content"]) > 0
        assert cluster["confidence"] > 0.0
        assert cluster["compression_ratio"] > 0.0


@pytest.mark.asyncio
async def test_memory_auto_consolidation_commit_and_lineage(client: AsyncClient):
    """Verify memory auto-consolidation commit mode creates synthesized memories with bidirectional links."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "committer@phase29.ai",
            "password": "Password123!",
            "full_name": "Consolidation Committer",
            "workspace_name": "Commit WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Insert 2 episodic memories for Tech Stack
    res1 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Frontend is built with Next.js 14 and Tailwind CSS",
            "category": "episodic",
            "tags": ["techstack", "frontend"],
        },
    )
    assert res1.status_code == 201
    mem1_id = res1.json()["data"]["id"]

    res2 = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Backend is built with FastAPI and PostgreSQL",
            "category": "episodic",
            "tags": ["techstack", "backend"],
        },
    )
    assert res2.status_code == 201
    mem2_id = res2.json()["data"]["id"]

    # 3. Commit mode Auto-Consolidation targeting topic "techstack"
    commit_resp = await client.post(
        "/api/v1/memories/auto-consolidate",
        headers=headers,
        json={
            "dry_run": False,
            "min_memories": 2,
            "topic": "techstack",
            "target_category": "semantic",
        },
    )
    assert commit_resp.status_code == 200
    commit_data = commit_resp.json()["data"]

    assert commit_data["dry_run"] is False
    assert commit_data["consolidated_memories_created"] >= 1
    assert len(commit_data["new_memory_ids"]) >= 1

    synth_id = commit_data["new_memory_ids"][0]

    # 4. Verify Database Records and Lineage
    async with core_db.AsyncSessionLocal() as session:
        # Check newly synthesized memory
        synth_mem = await session.get(Memory, synth_id)
        assert synth_mem is not None
        assert synth_mem.category == MemoryCategory.SEMANTIC
        assert synth_mem.source_type == "consolidation"
        assert "consolidated" in synth_mem.tags
        assert "synthesized" in synth_mem.tags
        assert "techstack" in synth_mem.tags
        assert mem1_id in synth_mem.extra_metadata["synthesized_from_ids"]
        assert mem2_id in synth_mem.extra_metadata["synthesized_from_ids"]

        # Check MemoryLink records
        links_q = select(MemoryLink).where(MemoryLink.source_memory_id == synth_id)
        links = list((await session.execute(links_q)).scalars().all())
        assert len(links) == 2
        assert all(lnk.relationship_type == "CONSOLIDATES" for lnk in links)
        linked_target_ids = {lnk.target_memory_id for lnk in links}
        assert mem1_id in linked_target_ids
        assert mem2_id in linked_target_ids

        # Check source memories have been annotated
        m1_db = await session.get(Memory, mem1_id)
        m2_db = await session.get(Memory, mem2_id)
        assert m1_db.extra_metadata.get("consolidated_into") == synth_id
        assert m2_db.extra_metadata.get("consolidated_into") == synth_id


@pytest.mark.asyncio
async def test_cryptographic_audit_log_hash_chain_verification(client: AsyncClient):
    """Verify unbroken cryptographic hash chain calculation and verification across audit events."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "auditor@phase29.ai",
            "password": "Password123!",
            "full_name": "Audit Officer",
            "workspace_name": "Audit Security WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Record 4 explicit security audit events
    async with core_db.AsyncSessionLocal() as session:
        e1 = await SecurityAuditLogger.log_event(
            db=session,
            action="user.login",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"method": "password", "ip": "127.0.0.1"},
        )
        assert e1 is not None
        assert "_chain" in e1.details
        assert e1.details["_chain"]["previous_hash"] == "0" * 64
        assert len(e1.details["_chain"]["chain_hash"]) == 64

        e2 = await SecurityAuditLogger.log_event(
            db=session,
            action="memory.created",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"memory_id": "mem_101", "tokens": 45},
        )
        assert e2 is not None
        assert e2.details["_chain"]["previous_hash"] == e1.details["_chain"]["chain_hash"]

        e3 = await SecurityAuditLogger.log_event(
            db=session,
            action="secret.rotated",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"key_version": 2},
        )
        assert e3 is not None
        assert e3.details["_chain"]["previous_hash"] == e2.details["_chain"]["chain_hash"]

        e4 = await SecurityAuditLogger.log_event(
            db=session,
            action="document.uploaded",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"doc_name": "spec.pdf", "size_bytes": 1024},
        )
        assert e4 is not None
        assert e4.details["_chain"]["previous_hash"] == e3.details["_chain"]["chain_hash"]

    # 3. Verify Chain via Endpoint
    v_resp = await client.get("/api/v1/admin/audit-logs/verify-chain", headers=headers)
    assert v_resp.status_code == 200
    v_data = v_resp.json()["data"]

    assert v_data["is_valid"] is True
    assert v_data["total_records_checked"] >= 4
    assert v_data["tampered_record_id"] is None
    assert v_data["chain_head_hash"] == e4.details["_chain"]["chain_hash"]
    assert "intact" in v_data["message"].lower()


@pytest.mark.asyncio
async def test_audit_chain_tamper_detection(client: AsyncClient):
    """Verify cryptographic audit verification immediately detects and pinpoints out-of-band database tampering."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tampertest@phase29.ai",
            "password": "Password123!",
            "full_name": "Tamper Tester",
            "workspace_name": "Tamper WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Record 3 audit events
    async with core_db.AsyncSessionLocal() as session:
        _t1 = await SecurityAuditLogger.log_event(
            db=session,
            action="auth.mfa_setup",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"step": "initiated"},
        )
        t2 = await SecurityAuditLogger.log_event(
            db=session,
            action="auth.mfa_enabled",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"step": "completed"},
        )
        await SecurityAuditLogger.log_event(
            db=session,
            action="session.created",
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            details={"sid": "sess_123"},
        )
        t2_id = t2.id

    # 3. Simulate direct database tampering: maliciously alter event t2's payload without recalculating hash
    async with core_db.AsyncSessionLocal() as session:
        ev_to_tamper = await session.get(AuditEvent, t2_id)
        assert ev_to_tamper is not None
        tampered_details = dict(ev_to_tamper.details)
        tampered_details["step"] = "MALICIOUSLY_MUTATED_VALUE"
        ev_to_tamper.details = tampered_details
        await session.commit()

    # 4. Verify Chain via Endpoint - Must Detect Tampering!
    v_resp = await client.get("/api/v1/admin/audit-logs/verify-chain", headers=headers)
    assert v_resp.status_code == 200
    v_data = v_resp.json()["data"]

    assert v_data["is_valid"] is False
    assert v_data["tampered_record_id"] == t2_id
    assert "violation" in v_data["message"].lower() or "altered" in v_data["message"].lower()


@pytest.mark.asyncio
async def test_workspace_rag_probe_benchmark_and_history(client: AsyncClient):
    """Verify automated synthetic RAG retrieval probe benchmark and historical telemetry."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ragprober@phase29.ai",
            "password": "Password123!",
            "full_name": "RAG Prober",
            "workspace_name": "RAG Probing WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Add ground-truth memories
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={"content": "User lives in Seattle and works at Microsoft", "category": "semantic"},
    )
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "User prefers Vim keybindings in all text editors",
            "category": "preference",
        },
    )
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Primary database architecture utilizes CockroachDB for multi-region replication",
            "category": "project",
        },
    )

    # 3. Execute Synthetic RAG Probe Benchmark
    probe_resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/eval/run-probe",
        headers=headers,
        json={"sample_size": 3, "top_k": 5},
    )
    assert probe_resp.status_code == 200
    p_data = probe_resp.json()["data"]

    assert p_data["workspace_id"] == ws_id
    assert p_data["total_probes"] == 3
    assert p_data["hit_rate"] >= 0.0
    assert p_data["mean_reciprocal_rank"] >= 0.0
    assert p_data["average_precision"] >= 0.0
    assert p_data["average_groundedness"] >= 0.0
    assert p_data["overall_score"] >= 0.0
    assert p_data["letter_grade"] in ["A+", "A", "B", "C", "Needs Attention"]
    assert len(p_data["probes"]) == 3

    for p in p_data["probes"]:
        assert "probe_id" in p
        assert len(p["query"]) > 0
        assert "ground_truth_memory_id" in p
        assert isinstance(p["hit"], bool)
        assert 0.0 <= p["reciprocal_rank"] <= 1.0
        assert 0.0 <= p["context_precision"] <= 1.0
        assert 0.0 <= p["groundedness_score"] <= 1.0

    # 4. Check Historical Telemetry
    hist_resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/eval/history",
        headers=headers,
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()["data"]

    assert hist_data["workspace_id"] == ws_id
    assert hist_data["total_runs"] >= 1
    assert hist_data["history"][0]["run_id"] == p_data["run_id"]


@pytest.mark.asyncio
async def test_phase29_rbac_and_tenancy_isolation(client: AsyncClient):
    """Verify strict multi-tenant boundary checks and RBAC across Phase 29 endpoints."""
    # 1. Register User A in Workspace A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_a@phase29.ai",
            "password": "Password123!",
            "full_name": "User Alpha",
            "workspace_name": "Alpha WS",
        },
    )
    assert reg_a.status_code == 201
    auth_a = reg_a.json()["data"]
    token_a = auth_a["tokens"]["access_token"]
    ws_a_id = auth_a["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_a_id}

    # 2. Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_b@phase29.ai",
            "password": "Password123!",
            "full_name": "User Beta",
            "workspace_name": "Beta WS",
        },
    )
    assert reg_b.status_code == 201
    auth_b = reg_b.json()["data"]
    token_b = auth_b["tokens"]["access_token"]
    ws_b_id = auth_b["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b_id}

    # 3. Cross-Tenant Probe Execution: User B queries Workspace A's probe endpoint -> Must be 404
    cross_probe = await client.post(
        f"/api/v1/workspaces/{ws_a_id}/eval/run-probe",
        headers=headers_b,
        json={"sample_size": 2, "top_k": 3},
    )
    assert cross_probe.status_code == 404

    # 4. Cross-Tenant Eval History: User B queries Workspace A's history -> Must be 404
    cross_hist = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/eval/history",
        headers=headers_b,
    )
    assert cross_hist.status_code == 404

    # 5. Non-Admin Member Role Access on /audit-logs/verify-chain
    # Add User B to Workspace A as regular MEMBER
    add_member = await client.post(
        f"/api/v1/workspaces/{ws_a_id}/members",
        headers=headers_a,
        json={"user_id": auth_b["user"]["id"], "role": "member"},
    )
    assert add_member.status_code == 201

    # User B switches header to Workspace A as regular member
    headers_b_in_a = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_a_id}
    member_verify = await client.get(
        "/api/v1/admin/audit-logs/verify-chain", headers=headers_b_in_a
    )
    # Regular members cannot verify audit chains (OWNER or ADMIN only)
    assert member_verify.status_code == 403

    # Owner User A can verify audit chain
    owner_verify = await client.get("/api/v1/admin/audit-logs/verify-chain", headers=headers_a)
    assert owner_verify.status_code == 200
