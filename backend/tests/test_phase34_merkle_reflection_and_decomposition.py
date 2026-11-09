from __future__ import annotations

import hashlib
import uuid

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.core.audit import SecurityAuditLogger
from app.core.merkle import MerkleAuditEngine
from app.models.workspace import WorkspaceMember, WorkspaceRole


@pytest.mark.asyncio
async def test_merkle_tree_construction_and_inclusion_proof_verification():
    """
    Cryptographic unit test for Merkle Tree construction, RFC 6962 domain separation,
    and zero-knowledge inclusion proof verification.
    """
    # 1. Single leaf test
    single_leaf = [hashlib.sha256(b"leaf:test1").hexdigest()]
    root_1 = MerkleAuditEngine.get_merkle_root(single_leaf)
    assert root_1 == single_leaf[0]
    proof_1 = MerkleAuditEngine.generate_proof(single_leaf, 0)
    assert proof_1 == []
    assert MerkleAuditEngine.verify_proof(single_leaf[0], proof_1, root_1) is True

    # 2. Multi-leaf tree with odd count (3 leaves)
    leaves_3 = [
        hashlib.sha256(b"leaf:event_A").hexdigest(),
        hashlib.sha256(b"leaf:event_B").hexdigest(),
        hashlib.sha256(b"leaf:event_C").hexdigest(),
    ]
    tree_levels = MerkleAuditEngine.build_tree(leaves_3)
    # 3 leaves -> level 0 (padded to 4), level 1 (2 nodes), level 2 (1 root)
    assert len(tree_levels) == 3
    root_3 = tree_levels[-1][0]
    assert len(root_3) == 64

    # 3. Generate and verify inclusion proofs for all 3 leaves
    for idx, leaf in enumerate(leaves_3):
        proof = MerkleAuditEngine.generate_proof(leaves_3, idx)
        assert len(proof) > 0
        is_valid = MerkleAuditEngine.verify_proof(leaf, proof, root_3)
        assert is_valid is True

    # 4. Tampered leaf hash must fail verification
    tampered_leaf = hashlib.sha256(b"leaf:tampered").hexdigest()
    proof_0 = MerkleAuditEngine.generate_proof(leaves_3, 0)
    assert MerkleAuditEngine.verify_proof(tampered_leaf, proof_0, root_3) is False

    # 5. Tampered proof sibling must fail verification
    tampered_proof = [{"position": proof_0[0]["position"], "hash": "0" * 64}] + proof_0[1:]
    assert MerkleAuditEngine.verify_proof(leaves_3[0], tampered_proof, root_3) is False


@pytest.mark.asyncio
async def test_admin_merkle_root_and_proof_api_lifecycle(client: AsyncClient):
    """
    Test Merkle Root calculation, Merkle Proof generation, and zero-knowledge proof verification
    via administrative endpoints.
    """
    # 1. Register user and create workspace
    user_email = f"merkle_admin_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "full_name": "Merkle Admin"},
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    user_id = auth_data["user"]["id"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 2. Record 4 distinct security audit events
    events = []
    actions = ["cmek.rotated", "secret.accessed", "ip_allowlist.updated", "dlp_policy.enforced"]
    async with core_db.AsyncSessionLocal() as session:
        for act in actions:
            evt = await SecurityAuditLogger.log_event(
                db=session,
                action=act,
                workspace_id=ws_id,
                user_id=user_id,
                details={"test_seq": len(events) + 1},
            )
            assert evt is not None
            events.append(evt)

    # 3. Request Merkle Root for workspace
    root_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-root",
        headers=headers,
        json={"workspace_id": ws_id},
    )
    assert root_res.status_code == 200
    root_data = root_res.json()["data"]
    assert root_data["total_leaves"] >= 4
    assert len(root_data["merkle_root"]) == 64
    merkle_root = root_data["merkle_root"]

    # 4. Generate Merkle inclusion proof for event #2
    target_event = events[1]
    proof_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-proof",
        headers=headers,
        json={"event_id": target_event.id, "workspace_id": ws_id},
    )
    assert proof_res.status_code == 200
    proof_data = proof_res.json()["data"]
    assert proof_data["event_id"] == target_event.id
    assert proof_data["merkle_root"] == merkle_root
    assert len(proof_data["audit_path"]) > 0

    # 5. Verify the generated proof
    verify_res = await client.post(
        "/api/v1/admin/audit-logs/verify-merkle-proof",
        headers=headers,
        json={
            "leaf_hash": proof_data["leaf_hash"],
            "merkle_root": merkle_root,
            "audit_path": proof_data["audit_path"],
        },
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()["data"]
    assert verify_data["is_valid"] is True
    assert verify_data["computed_root"] == merkle_root

    # 6. Verify tampered proof fails
    tampered_path = list(proof_data["audit_path"])
    tampered_path[0] = {"position": "left", "hash": "a" * 64}
    tampered_res = await client.post(
        "/api/v1/admin/audit-logs/verify-merkle-proof",
        headers=headers,
        json={
            "leaf_hash": proof_data["leaf_hash"],
            "merkle_root": merkle_root,
            "audit_path": tampered_path,
        },
    )
    assert tampered_res.status_code == 200
    assert tampered_res.json()["data"]["is_valid"] is False


@pytest.mark.asyncio
async def test_admin_merkle_proof_rbac_enforcement(client: AsyncClient):
    """
    Verify that unprivileged regular members cannot generate Merkle roots or proofs,
    and non-existent events return 404.
    """
    # 1. Register Owner
    owner_email = f"merkle_owner_{uuid.uuid4().hex[:6]}@example.com"
    o_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": owner_email, "password": "SecurePassword123!", "full_name": "Merkle Owner"},
    )
    assert o_reg.status_code == 201
    owner_token = o_reg.json()["data"]["tokens"]["access_token"]
    ws_id = o_reg.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-Id": ws_id}

    # 2. Register Regular Member
    member_email = f"merkle_member_{uuid.uuid4().hex[:6]}@example.com"
    m_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "password": "SecurePassword123!",
            "full_name": "Regular Member",
        },
    )
    assert m_reg.status_code == 201
    member_token = m_reg.json()["data"]["tokens"]["access_token"]
    member_id = m_reg.json()["data"]["user"]["id"]
    member_headers = {"Authorization": f"Bearer {member_token}", "X-Workspace-Id": ws_id}

    # Add member to owner's workspace with MEMBER role
    async with core_db.AsyncSessionLocal() as session:
        membership = WorkspaceMember(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=member_id,
            role=WorkspaceRole.MEMBER,
        )
        session.add(membership)
        await session.commit()

    # 3. Regular member requests Merkle Root -> 403 Forbidden
    root_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-root",
        headers=member_headers,
        json={"workspace_id": ws_id},
    )
    assert root_res.status_code == 403

    # 4. Regular member requests Merkle Proof -> 403 Forbidden
    proof_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-proof",
        headers=member_headers,
        json={"event_id": str(uuid.uuid4()), "workspace_id": ws_id},
    )
    assert proof_res.status_code == 403

    # 5. Owner requests non-existent event proof -> 404 Not Found
    missing_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-proof",
        headers=owner_headers,
        json={"event_id": str(uuid.uuid4()), "workspace_id": ws_id},
    )
    assert missing_res.status_code == 404


@pytest.mark.asyncio
async def test_cognitive_memory_reflection_dry_run_and_commit(client: AsyncClient):
    """
    Test cognitive reflection over episodic memories with dry-run and auto-commit,
    verifying synthesized insights, confidence scoring, and existing reflections query.
    """
    user_email = f"reflect_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Reflection Researcher",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Ingest technical memories across categories
    mem_payloads = [
        {
            "content": "We build asynchronous REST endpoints in Python using FastAPI with strict Pydantic v2 schemas.",
            "category": "episodic",
            "importance": 8,
            "tags": ["fastapi", "pydantic", "architecture"],
        },
        {
            "content": "All database operations use SQLAlchemy 2.0 async session with parameterized ORM statements.",
            "category": "episodic",
            "importance": 7,
            "tags": ["sqlalchemy", "postgres", "architecture"],
        },
        {
            "content": "Every mutation endpoint must verify HMAC-SHA256 signatures and enforce tenant data boundaries.",
            "category": "episodic",
            "importance": 9,
            "tags": ["security", "hmac", "auth"],
        },
        {
            "content": "Always run pytest regressions and enforce ruff check with zero lint warnings before release.",
            "category": "episodic",
            "importance": 8,
            "tags": ["pytest", "quality", "lint"],
        },
    ]

    for p in mem_payloads:
        create_res = await client.post("/api/v1/memories", headers=headers, json=p)
        assert create_res.status_code == 201

    # 1. Dry-run reflection
    dry_res = await client.post(
        "/api/v1/memories/reflect",
        headers=headers,
        json={"lookback_days": 30, "auto_commit": False},
    )
    assert dry_res.status_code == 200
    dry_data = dry_res.json()["data"]
    assert dry_data["total_memories_analyzed"] >= 4
    assert dry_data["total_reflections_generated"] >= 2
    assert dry_data["committed_memory_ids"] == []
    assert dry_data["auto_committed"] is False

    # Check structure of insights
    for insight in dry_data["insights"]:
        assert insight["title"] is not None
        assert insight["confidence"] >= 0.70
        assert len(insight["source_memory_ids"]) >= 1
        assert insight["suggested_action"] is not None

    # 2. Auto-commit reflection
    commit_res = await client.post(
        "/api/v1/memories/reflect",
        headers=headers,
        json={"lookback_days": 30, "auto_commit": True},
    )
    assert commit_res.status_code == 200
    commit_data = commit_res.json()["data"]
    assert len(commit_data["committed_memory_ids"]) >= 2
    assert commit_data["auto_committed"] is True

    # 3. Retrieve committed reflections via GET /api/v1/memories/reflections
    list_ref_res = await client.get("/api/v1/memories/reflections", headers=headers)
    assert list_ref_res.status_code == 200
    ref_list = list_ref_res.json()["data"]["reflections"]
    assert len(ref_list) >= 2
    for r in ref_list:
        assert "reflection" in r["tags"]
        assert r["category"] == "semantic"


@pytest.mark.asyncio
async def test_semantic_query_decomposition_and_sub_query_search(client: AsyncClient):
    """
    Test Semantic Query Decomposition on compound queries, ensuring sub-queries are generated,
    aspects retrieved in parallel, candidates fused, and contextual briefing synthesized.
    """
    user_email = f"decomposer_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Decomposer Explorer",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Ingest distinct domain memories
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Background workers are powered by Celery 5.x and Redis for reliable asynchronous task execution.",
            "category": "semantic",
            "importance": 9,
            "tags": ["celery", "redis", "workers"],
        },
    )
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Zero-trust security enforces Fernet envelope encryption and cryptographic HMAC-SHA256 verification.",
            "category": "semantic",
            "importance": 9,
            "tags": ["security", "encryption", "auth"],
        },
    )

    # 1. Execute decomposed search on compound query
    compound_query = "How do background workers use Celery and Redis, and what is our security policy for encryption?"
    decomp_res = await client.post(
        "/api/v1/search/decomposed",
        headers=headers,
        json={
            "query": compound_query,
            "max_sub_queries": 4,
            "top_k_per_sub_query": 5,
        },
    )
    assert decomp_res.status_code == 200
    data = decomp_res.json()["data"]
    assert data["original_query"] == compound_query
    assert len(data["sub_queries"]) >= 2
    assert len(data["sub_query_executions"]) >= 2
    assert len(data["fused_results"]) >= 1
    assert "Query Decomposition Synthesis" in data["synthesis_briefing"]


@pytest.mark.asyncio
async def test_phase34_multi_tenant_isolation(client: AsyncClient):
    """
    Verify complete multi-tenant isolation across Merkle proofs, cognitive reflections,
    and decomposed search between Workspace A and Workspace B.
    """
    # 1. Create Workspace A
    user_a = f"tenant_a_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": user_a, "password": "SecurePassword123!", "full_name": "Tenant A"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_id_a = reg_a.json()["data"]["user"]["id"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a}

    # Create private memory and audit event in Workspace A
    await client.post(
        "/api/v1/memories",
        headers=headers_a,
        json={
            "content": "Confidential Alpha Patent Strategy for Project X",
            "category": "semantic",
            "importance": 10,
            "tags": ["top_secret", "patent"],
        },
    )
    async with core_db.AsyncSessionLocal() as session:
        evt_a = await SecurityAuditLogger.log_event(
            db=session,
            action="classified.accessed",
            workspace_id=ws_a,
            user_id=user_id_a,
            details={"project": "Alpha"},
        )
        assert evt_a is not None

    # 2. Create Workspace B
    user_b = f"tenant_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": user_b, "password": "SecurePassword123!", "full_name": "Tenant B"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b}

    # 3. Tenant B attempts to generate Merkle proof for Workspace A's audit event -> 404
    cross_proof_res = await client.post(
        "/api/v1/admin/audit-logs/merkle-proof",
        headers=headers_b,
        json={"event_id": evt_a.id, "workspace_id": ws_b},
    )
    assert cross_proof_res.status_code == 404

    # 4. Tenant B reflects on memories -> should not analyze or reflect Workspace A's memory
    reflect_b_res = await client.post(
        "/api/v1/memories/reflect",
        headers=headers_b,
        json={"lookback_days": 30, "auto_commit": False},
    )
    assert reflect_b_res.status_code == 200
    assert reflect_b_res.json()["data"]["total_memories_analyzed"] == 0

    # 5. Tenant B executes decomposed search for "Alpha Patent Strategy" -> zero matches from A
    decomp_b_res = await client.post(
        "/api/v1/search/decomposed",
        headers=headers_b,
        json={"query": "Confidential Alpha Patent Strategy"},
    )
    assert decomp_b_res.status_code == 200
    assert decomp_b_res.json()["data"]["fused_results"] == []
