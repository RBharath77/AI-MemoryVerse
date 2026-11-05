from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_detection(client: AsyncClient, auth_headers: dict):
    # 1. Create original memory
    res1 = await client.post(
        "/api/v1/memories",
        json={
            "content": "User prefers concise Python code without unnecessary classes.",
            "category": "preference",
            "importance": 7,
        },
        headers=auth_headers,
    )
    assert res1.status_code == 201
    mem1_id = res1.json()["data"]["id"]

    # 2. Attempt creating exact duplicate
    res2 = await client.post(
        "/api/v1/memories",
        json={
            "content": "user prefers concise python code without unnecessary classes.",
            "category": "preference",
            "importance": 7,
        },
        headers=auth_headers,
    )
    assert res2.status_code in (200, 201)
    # Deduplication should return the original memory ID rather than creating a duplicate
    assert res2.json()["data"]["id"] == mem1_id


@pytest.mark.asyncio
async def test_conflict_detection_and_review_inbox(client: AsyncClient, auth_headers: dict):
    # 1. Create baseline preference: prefers dark mode
    res1 = await client.post(
        "/api/v1/memories",
        json={
            "content": "User strongly prefers dark mode in all UI applications.",
            "category": "preference",
            "importance": 8,
        },
        headers=auth_headers,
    )
    assert res1.status_code == 201
    assert res1.json()["data"]["status"] == "approved"

    # 2. Add conflicting preference: prefers light mode
    res2 = await client.post(
        "/api/v1/memories",
        json={
            "content": "User prefers light mode for readability during daytime.",
            "category": "preference",
            "importance": 8,
        },
        headers=auth_headers,
    )
    assert res2.status_code == 201
    data2 = res2.json()["data"]
    # Conflict detector flags it and places it in pending_review
    assert data2["status"] == "pending_review"
    assert data2["extra_metadata"].get("conflict_detected") is True

    # 3. Check memory reviews inbox
    rev_res = await client.get("/api/v1/memory-reviews?status=pending", headers=auth_headers)
    assert rev_res.status_code == 200
    rev_items = rev_res.json()["data"]["items"]
    target_review = next((r for r in rev_items if r["memory_id"] == data2["id"]), None)
    assert target_review is not None
    assert target_review["review_status"] == "pending"

    # 4. Correct and approve the memory through review action
    act_res = await client.post(
        f"/api/v1/memory-reviews/{target_review['id']}/action",
        json={
            "review_status": "corrected",
            "corrected_text": "User prefers system theme (automatic dark/light switching).",
            "review_notes": "Resolved contradiction by adopting system dynamic theme.",
        },
        headers=auth_headers,
    )
    assert act_res.status_code == 200
    assert act_res.json()["data"]["review_status"] == "corrected"

    # 5. Verify the memory is now approved with corrected text
    mem_check = await client.get(f"/api/v1/memories/{data2['id']}", headers=auth_headers)
    assert mem_check.status_code == 200
    assert mem_check.json()["data"]["status"] == "approved"
    assert "system theme" in mem_check.json()["data"]["content"]


@pytest.mark.asyncio
async def test_extract_memories_pipeline_and_sensitive_guardrail(
    client: AsyncClient, auth_headers: dict
):
    # Unstructured conversation containing preferences, projects, events, and a sensitive password
    raw_text = """
    I really love working with FastAPI and TypeScript.
    Our project deadline for the memory service is next Friday.
    Yesterday we met with the architecture team to design vector indexing.
    My database password is: super_secret_pwd_12345
    """

    res = await client.post(
        "/api/v1/memories/extract",
        json={
            "text": raw_text,
            "source_type": "conversation",
            "auto_approve": True,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["extracted_count"] >= 3

    # Sensitive guardrail: The password must NEVER be extracted into memories
    all_contents = [m["content"].lower() for m in data["memories"]]
    assert not any("super_secret_pwd_12345" in c for c in all_contents)

    # Categories should be identified
    categories = [m["category"] for m in data["memories"]]
    assert any(c in ("preference", "project", "episodic", "semantic") for c in categories)


@pytest.mark.asyncio
async def test_version_history_and_restore(client: AsyncClient, auth_headers: dict):
    # 1. Create memory
    res = await client.post(
        "/api/v1/memories",
        json={"content": "Version 1 content", "category": "semantic"},
        headers=auth_headers,
    )
    memory_id = res.json()["data"]["id"]

    # 2. Update to Version 2
    await client.patch(
        f"/api/v1/memories/{memory_id}",
        json={"content": "Version 2 updated content"},
        headers=auth_headers,
    )

    # 3. Update to Version 3
    await client.patch(
        f"/api/v1/memories/{memory_id}",
        json={"content": "Version 3 final content"},
        headers=auth_headers,
    )

    # 4. List versions
    v_res = await client.get(f"/api/v1/memories/{memory_id}/versions", headers=auth_headers)
    assert v_res.status_code == 200
    versions = v_res.json()["data"]
    assert len(versions) == 3
    assert versions[0]["version_number"] == 3
    assert versions[2]["version_number"] == 1
    assert versions[2]["content"] == "Version 1 content"

    # 5. Restore Version 1
    restore_res = await client.post(
        f"/api/v1/memories/{memory_id}/restore?version_number=1",
        headers=auth_headers,
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["data"]["content"] == "Version 1 content"

    # 6. Verify version count incremented to 4
    v_res_after = await client.get(f"/api/v1/memories/{memory_id}/versions", headers=auth_headers)
    assert len(v_res_after.json()["data"]) == 4


@pytest.mark.asyncio
async def test_memory_consolidation(client: AsyncClient, auth_headers: dict):
    # Create two related memories
    res1 = await client.post(
        "/api/v1/memories",
        json={"content": "Phase 1 implements user auth with JWT rotation.", "category": "project"},
        headers=auth_headers,
    )
    mem1_id = res1.json()["data"]["id"]

    res2 = await client.post(
        "/api/v1/memories",
        json={
            "content": "Phase 2 implements frontend views for workspace and memories.",
            "category": "project",
        },
        headers=auth_headers,
    )
    mem2_id = res2.json()["data"]["id"]

    # Consolidate
    con_res = await client.post(
        "/api/v1/memories/consolidate",
        json={
            "memory_ids": [mem1_id, mem2_id],
            "consolidated_content": (
                "Phases 1 & 2 deliver full-stack authentication, "
                "workspace management, and foundational UI views."
            ),
            "category": "project",
        },
        headers=auth_headers,
    )
    assert con_res.status_code == 200
    con_data = con_res.json()["data"]
    assert con_data["status"] == "approved"
    assert con_data["source_type"] == "consolidation"

    # Check original memories are now superseded
    check1 = await client.get(f"/api/v1/memories/{mem1_id}", headers=auth_headers)
    check2 = await client.get(f"/api/v1/memories/{mem2_id}", headers=auth_headers)
    assert check1.json()["data"]["status"] == "superseded"
    assert check1.json()["data"]["superseded_by"] == con_data["id"]
    assert check2.json()["data"]["status"] == "superseded"
    assert check2.json()["data"]["superseded_by"] == con_data["id"]


@pytest.mark.asyncio
async def test_memory_timeline_and_temporal_filters(client: AsyncClient, auth_headers: dict):
    now = datetime.now(UTC)
    past = now - timedelta(days=10)
    future = now + timedelta(days=30)

    # Expired memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Temporary beta access key valid until yesterday.",
            "category": "project",
            "valid_from": (past - timedelta(days=5)).isoformat(),
            "valid_until": past.isoformat(),
        },
        headers=auth_headers,
    )

    # Active memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Current ongoing enterprise subscription.",
            "category": "project",
            "valid_from": now.isoformat(),
            "valid_until": future.isoformat(),
        },
        headers=auth_headers,
    )

    # 1. Timeline endpoint
    timeline_res = await client.get("/api/v1/memories/timeline", headers=auth_headers)
    assert timeline_res.status_code == 200
    assert timeline_res.json()["data"]["total"] >= 2

    # 2. Active-only filter
    active_res = await client.get("/api/v1/memories?active_only=true", headers=auth_headers)
    assert active_res.status_code == 200
    active_items = active_res.json()["data"]["items"]
    # Expired memory should not be in active items
    assert not any("Temporary beta access key" in m["content"] for m in active_items)


@pytest.mark.asyncio
async def test_memory_links_and_feedback(client: AsyncClient, auth_headers: dict):
    res1 = await client.post(
        "/api/v1/memories",
        json={
            "content": "React Hook Form simplifies frontend input validation.",
            "category": "semantic",
        },
        headers=auth_headers,
    )
    res2 = await client.post(
        "/api/v1/memories",
        json={
            "content": "Zod ensures schema validation matches TypeScript types.",
            "category": "semantic",
        },
        headers=auth_headers,
    )
    m1_id = res1.json()["data"]["id"]
    m2_id = res2.json()["data"]["id"]

    # 1. Create relationship link
    link_res = await client.post(
        f"/api/v1/memories/{m1_id}/links",
        json={
            "target_memory_id": m2_id,
            "relationship_type": "complements",
            "confidence": 0.95,
        },
        headers=auth_headers,
    )
    assert link_res.status_code == 200
    assert link_res.json()["data"]["relationship_type"] == "complements"

    # 2. List links
    list_links = await client.get(f"/api/v1/memories/{m1_id}/links", headers=auth_headers)
    assert list_links.status_code == 200
    assert len(list_links.json()["data"]) >= 1

    # 3. Add feedback
    fb_res = await client.post(
        f"/api/v1/memories/{m1_id}/feedback",
        json={
            "rating": 1,
            "feedback_text": "Extremely accurate insight.",
        },
        headers=auth_headers,
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["data"]["rating"] == 1


@pytest.mark.asyncio
async def test_memory_export_import_and_analytics(client: AsyncClient, auth_headers: dict):
    # 0. Seed an initial memory
    await client.post(
        "/api/v1/memories",
        json={"content": "Seeded baseline memory for workspace analytics.", "category": "semantic"},
        headers=auth_headers,
    )

    # 1. Analytics
    analytics_res = await client.get("/api/v1/memories/analytics", headers=auth_headers)
    assert analytics_res.status_code == 200
    stats = analytics_res.json()["data"]
    assert stats["total_memories"] >= 1
    assert "by_category" in stats
    assert "top_tags" in stats

    # 2. Export JSON
    export_json = await client.get("/api/v1/memories/export?format=json", headers=auth_headers)
    assert export_json.status_code == 200
    assert export_json.headers["content-type"].startswith("application/json")

    # 3. Export CSV
    export_csv = await client.get("/api/v1/memories/export?format=csv", headers=auth_headers)
    assert export_csv.status_code == 200
    assert "text/csv" in export_csv.headers["content-type"]
    assert "content" in export_csv.text

    # 4. Import
    import_res = await client.post(
        "/api/v1/memories/import",
        json={
            "memories": [
                {
                    "content": "Imported fact A: PostgreSQL 16 is the standard database.",
                    "category": "semantic",
                },
                {
                    "content": "Imported fact B: Celery handles asynchronous background tasks.",
                    "category": "semantic",
                },
            ]
        },
        headers=auth_headers,
    )
    assert import_res.status_code == 200
    assert import_res.json()["data"]["imported_count"] == 2
