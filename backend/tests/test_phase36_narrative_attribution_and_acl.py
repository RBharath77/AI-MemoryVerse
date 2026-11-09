from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.models.graph import EntityType, GraphEntity
from app.models.memory import Memory, MemoryCategory, MemoryStatus
from app.models.workspace import WorkspaceMember, WorkspaceRole


@pytest.mark.asyncio
async def test_narrative_synthesis_multi_act_structure(client: AsyncClient):
    """
    Test Contextual Narrative Memory Synthesis & Executive Storytelling Engine:
    verifies multi-act chronological narrative structure, grounding entity linking,
    coherence score, and forward guidance recommendations.
    """
    # 1. Register user and setup workspace
    user_email = f"narrative_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Executive Storyteller",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 2. Seed chronological memories and graph entities
    now_dt = datetime.now(UTC)
    async with core_db.AsyncSessionLocal() as session:
        m1 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="Initial bootstrap: Adopted FastAPI and async SQLAlchemy with PostgreSQL engine.",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
            created_at=now_dt - timedelta(days=60),
            updated_at=now_dt - timedelta(days=60),
        )
        m2 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="Mid-cycle pivot: Introduced cryptographic HMAC integrity seals and zero-trust tenant boundaries.",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
            created_at=now_dt - timedelta(days=30),
            updated_at=now_dt - timedelta(days=30),
        )
        m3 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="Current state: Production deployment active with automated cognitive sleep-cycle synaptic compaction.",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
            created_at=now_dt - timedelta(days=5),
            updated_at=now_dt - timedelta(days=5),
        )
        session.add_all([m1, m2, m3])

        e1 = GraphEntity(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            name="FastAPI",
            entity_type=EntityType.TECHNOLOGY,
            description="Core asynchronous backend framework",
        )
        e2 = GraphEntity(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            name="PostgreSQL",
            entity_type=EntityType.TECHNOLOGY,
            description="Relational database persistence engine",
        )
        session.add_all([e1, e2])
        await session.commit()

    # 3. Call narrative synthesis endpoint
    synth_res = await client.post(
        "/api/v1/research/narrative-synthesis",
        headers=headers,
        json={
            "focus_topic": "System Architecture Evolution",
            "lookback_days": 90,
            "include_forward_guidance": True,
        },
    )
    assert synth_res.status_code == 200
    res_data = synth_res.json()["data"]
    assert res_data["workspace_id"] == ws_id
    assert res_data["focus_topic"] == "System Architecture Evolution"
    assert res_data["total_sources_synthesized"] >= 3
    assert res_data["coherence_score"] >= 0.80
    assert res_data["continuity_index"] >= 0.90
    assert len(res_data["acts"]) >= 3
    assert len(res_data["forward_guidance"]) >= 2

    # Verify act structure
    act_titles = [act["act_title"] for act in res_data["acts"]]
    assert any("Genesis" in t for t in act_titles)
    assert any("Evolution" in t for t in act_titles)
    assert any("Maturation" in t for t in act_titles)
    assert any("Strategic Horizon" in t for t in act_titles)


@pytest.mark.asyncio
async def test_hallucination_attribution_verifier_entailment(client: AsyncClient):
    """
    Test Semantic Knowledge Grounding & Hallucination Attribution Verifier:
    verifies that claims grounded in workspace memory premises are correctly tagged SUPPORTED
    with high grounding fidelity and low hallucination risk.
    """
    user_email = f"grounding_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Grounding Specialist",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 1. Seed grounding memory in workspace
    async with core_db.AsyncSessionLocal() as session:
        m = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=auth_data["user"]["id"],
            content="MemoryVerse utilizes PostgreSQL with pgvector for hybrid semantic retrieval and metadata indexing.",
            category=MemoryCategory.PROJECT,
            status=MemoryStatus.APPROVED,
        )
        session.add(m)
        await session.commit()

    # 2. Verify fully supported generated text
    verify_res = await client.post(
        "/api/v1/chat/verify-attribution",
        headers=headers,
        json={
            "generated_text": (
                "MemoryVerse utilizes PostgreSQL with pgvector for hybrid semantic retrieval. "
                "Metadata indexing is maintained in PostgreSQL."
            ),
            "strictness": 0.8,
        },
    )
    assert verify_res.status_code == 200
    res_data = verify_res.json()["data"]
    assert res_data["workspace_id"] == ws_id
    assert res_data["total_claims"] >= 1
    assert res_data["supported_claims"] >= 1
    assert res_data["contradicted_claims"] == 0
    assert res_data["grounding_fidelity_score"] > 0.50
    assert res_data["hallucination_risk_index"] < 0.40
    assert res_data["is_grounded"] is True


@pytest.mark.asyncio
async def test_hallucination_attribution_verifier_contradiction(client: AsyncClient):
    """
    Test Semantic Knowledge Grounding & Hallucination Attribution Verifier:
    verifies detection of direct polarity contradictions between generated assertions and grounding premises.
    """
    user_email = f"contradiction_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "NLI Verifier",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Verify claim contradictory to explicit grounding source
    verify_res = await client.post(
        "/api/v1/chat/verify-attribution",
        headers=headers,
        json={
            "generated_text": "Authentication session cookies are always insecure and never encrypted.",
            "grounding_sources": [
                {
                    "id": "sec-policy-doc",
                    "content": "Authentication session cookies are always secure and encrypted across all environments.",
                }
            ],
            "strictness": 0.9,
        },
    )
    assert verify_res.status_code == 200
    res_data = verify_res.json()["data"]
    assert res_data["contradicted_claims"] >= 1
    assert res_data["is_grounded"] is False
    assert res_data["hallucination_risk_index"] > 0.50

    # Inspect contradiction detail
    contradicted = [c for c in res_data["claims"] if c["status"] == "CONTRADICTED"]
    assert len(contradicted) >= 1
    assert "sec-policy-doc" in contradicted[0]["supporting_sources"]
    assert "Polarity mismatch" in (contradicted[0]["contradiction_detail"] or "")


@pytest.mark.asyncio
async def test_memory_acl_policy_crud_and_abac_enforcement(client: AsyncClient):
    """
    Test Attribute-Based Access Control (ABAC) dynamic ACL policy updates:
    verifies retrieving default workspace visibility and modifying to restricted scope with role allowlists.
    """
    user_email = f"acl_admin_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "ACL Administrator",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 1. Create a memory
    create_res = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "Executive financial forecast and enterprise roadmap for Q4.",
            "category": "project",
        },
    )
    assert create_res.status_code == 201
    mem_id = create_res.json()["data"]["id"]

    # 2. Read default ACL policy
    acl_res = await client.get(
        f"/api/v1/memories/{mem_id}/access-control",
        headers=headers,
    )
    assert acl_res.status_code == 200
    acl_data = acl_res.json()["data"]
    assert acl_data["visibility"] == "workspace"
    assert acl_data["can_read"] is True
    assert acl_data["can_write"] is True

    # 3. Update ACL policy to restricted
    update_res = await client.patch(
        f"/api/v1/memories/{mem_id}/access-control",
        headers=headers,
        json={
            "visibility": "restricted",
            "allowed_roles": ["admin", "owner"],
            "allowed_user_ids": [auth_data["user"]["id"]],
        },
    )
    assert update_res.status_code == 200
    updated_acl = update_res.json()["data"]
    assert updated_acl["visibility"] == "restricted"
    assert "admin" in updated_acl["allowed_roles"]
    assert auth_data["user"]["id"] in updated_acl["allowed_user_ids"]
    assert updated_acl["can_read"] is True
    assert updated_acl["can_write"] is True


@pytest.mark.asyncio
async def test_memory_acl_private_and_restricted_read_isolation(client: AsyncClient):
    """
    Test fine-grained ABAC read isolation:
    verifies that private or restricted memories block unauthorized workspace members with 403 Forbidden,
    and permit access when explicitly added to the allowed user list.
    """
    # 1. Register Owner (Alice)
    alice_email = f"alice_{uuid.uuid4().hex[:6]}@example.com"
    alice_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": alice_email,
            "password": "SecurePassword123!",
            "full_name": "Alice Author",
        },
    )
    assert alice_res.status_code == 201
    alice_data = alice_res.json()["data"]
    alice_token = alice_data["tokens"]["access_token"]
    ws_id = alice_data["workspace"]["id"]
    alice_headers = {"Authorization": f"Bearer {alice_token}", "X-Workspace-Id": ws_id}

    # 2. Register Member (Bob) and add to Alice's workspace
    bob_email = f"bob_{uuid.uuid4().hex[:6]}@example.com"
    bob_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": bob_email,
            "password": "SecurePassword123!",
            "full_name": "Bob Member",
        },
    )
    assert bob_res.status_code == 201
    bob_data = bob_res.json()["data"]
    bob_token = bob_data["tokens"]["access_token"]
    bob_id = bob_data["user"]["id"]
    bob_headers = {"Authorization": f"Bearer {bob_token}", "X-Workspace-Id": ws_id}

    async with core_db.AsyncSessionLocal() as session:
        membership = WorkspaceMember(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=bob_id,
            role=WorkspaceRole.MEMBER,
        )
        session.add(membership)
        await session.commit()

    # 3. Alice creates a private memory
    create_res = await client.post(
        "/api/v1/memories",
        headers=alice_headers,
        json={
            "content": "Alice's highly confidential strategic reflections.",
            "category": "preference",
        },
    )
    assert create_res.status_code == 201
    mem_id = create_res.json()["data"]["id"]

    # Mark as private
    acl_set_res = await client.patch(
        f"/api/v1/memories/{mem_id}/access-control",
        headers=alice_headers,
        json={
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": [],
        },
    )
    assert acl_set_res.status_code == 200

    # 4. Alice can read the private memory
    alice_get = await client.get(f"/api/v1/memories/{mem_id}", headers=alice_headers)
    assert alice_get.status_code == 200

    # 5. Bob attempts to read private memory -> 403 Forbidden
    bob_get = await client.get(f"/api/v1/memories/{mem_id}", headers=bob_headers)
    assert bob_get.status_code == 403
    err_msg = bob_get.json().get("error", {}).get("message", "") or bob_get.json().get("detail", "")
    assert "forbidden by dynamic access control list policy" in err_msg

    # 6. Alice modifies ACL to restricted and allows Bob's user ID
    allow_bob_res = await client.patch(
        f"/api/v1/memories/{mem_id}/access-control",
        headers=alice_headers,
        json={
            "visibility": "restricted",
            "allowed_roles": ["admin"],
            "allowed_user_ids": [bob_id],
        },
    )
    assert allow_bob_res.status_code == 200

    # 7. Bob now successfully reads the memory
    bob_granted_get = await client.get(f"/api/v1/memories/{mem_id}", headers=bob_headers)
    assert bob_granted_get.status_code == 200
    assert bob_granted_get.json()["data"]["id"] == mem_id


@pytest.mark.asyncio
async def test_phase36_multi_tenant_isolation(client: AsyncClient):
    """
    Test Phase 36 multi-tenant boundaries:
    verifies that users in Workspace B cannot access or modify ACL policies of Workspace A memories.
    """
    # 1. Setup Tenant A
    user_a = f"tenant_a_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": user_a, "password": "SecurePassword123!", "full_name": "Tenant A User"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a}

    # 2. Setup Tenant B
    user_b = f"tenant_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": user_b, "password": "SecurePassword123!", "full_name": "Tenant B User"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b}

    # 3. Tenant A creates memory
    create_res = await client.post(
        "/api/v1/memories",
        headers=headers_a,
        json={
            "content": "Tenant A confidential operational parameters.",
            "category": "project",
        },
    )
    assert create_res.status_code == 201
    mem_a_id = create_res.json()["data"]["id"]

    # 4. Tenant B attempts to read Tenant A memory ACL -> 404 Not Found (tenant isolated)
    b_acl_get = await client.get(
        f"/api/v1/memories/{mem_a_id}/access-control",
        headers=headers_b,
    )
    assert b_acl_get.status_code == 404

    # 5. Tenant B attempts to update Tenant A memory ACL -> 404 Not Found
    b_acl_patch = await client.patch(
        f"/api/v1/memories/{mem_a_id}/access-control",
        headers=headers_b,
        json={"visibility": "workspace", "allowed_roles": [], "allowed_user_ids": []},
    )
    assert b_acl_patch.status_code == 404
