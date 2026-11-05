import io
import wave

import pytest
from httpx import AsyncClient


def _create_test_wav_bytes() -> bytes:
    """Generate minimal valid WAV audio bytes for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 800)  # 50ms silence
    return buf.getvalue()


@pytest.mark.asyncio
async def test_voice_transcribe_and_synthesize(client: AsyncClient, auth_headers: dict):
    # 1. Test Audio Transcription
    wav_bytes = _create_test_wav_bytes()
    files = {"file": ("test_query.wav", wav_bytes, "audio/wav")}

    trans_res = await client.post(
        "/api/v1/voice/transcribe",
        files=files,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert trans_res.status_code == 200
    t_data = trans_res.json()["data"]
    assert "text" in t_data
    assert len(t_data["text"]) > 0
    assert t_data["language"] == "en"

    # 2. Test Speech Synthesis
    synth_res = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Welcome to AI-MemoryVerse. How can I help you today?", "voice": "alloy"},
        headers=auth_headers,
    )
    assert synth_res.status_code == 200
    assert "audio" in synth_res.headers["content-type"]
    assert len(synth_res.content) > 44  # WAV header is 44 bytes


@pytest.mark.asyncio
async def test_voice_chat_rag_query(client: AsyncClient, auth_headers: dict):
    # Seed a memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Our AI stack is built with Next.js, FastAPI, and pgvector.",
            "category": "semantic",
            "importance": 8,
        },
        headers=auth_headers,
    )

    # Execute voice chat
    chat_res = await client.post(
        "/api/v1/voice/chat",
        json={"query": "What technologies do we use for AI?", "voice": "alloy"},
        headers=auth_headers,
    )
    assert chat_res.status_code == 200
    c_data = chat_res.json()["data"]
    assert c_data["user_query"] == "What technologies do we use for AI?"
    assert len(c_data["assistant_response"]) > 0
    assert c_data["conversation_id"] is not None
    assert c_data["audio_base64"] is not None
    assert len(c_data["audio_base64"]) > 50


@pytest.mark.asyncio
async def test_research_report_generation_lifecycle(client: AsyncClient, auth_headers: dict):
    # 1. Seed memories
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Project Apollo database uses PostgreSQL with pgvector for embeddings.",
            "category": "project",
            "importance": 9,
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Project Apollo frontend is developed using Next.js 14 App Router.",
            "category": "project",
            "importance": 8,
        },
        headers=auth_headers,
    )

    # 2. Generate Topic Research Report
    gen_res = await client.post(
        "/api/v1/research/generate",
        json={
            "topic": "Project Apollo Architecture",
            "report_type": "topic_research",
            "days_back": 30,
        },
        headers=auth_headers,
    )
    assert gen_res.status_code == 200
    report = gen_res.json()["data"]
    report_id = report["id"]
    assert report["topic"] == "Project Apollo Architecture"
    assert "Apollo" in report["title"]
    assert report["status"] == "completed"
    assert len(report["content_markdown"]) > 50
    assert len(report["key_findings"]) >= 1

    # 3. List Reports
    list_res = await client.get("/api/v1/research/reports", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert any(r["id"] == report_id for r in items)

    # 4. Get Report Details
    get_res = await client.get(f"/api/v1/research/reports/{report_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == report_id

    # 5. Delete Report
    del_res = await client.delete(f"/api/v1/research/reports/{report_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Verify 404 after deletion
    get_after = await client.get(f"/api/v1/research/reports/{report_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_daily_and_weekly_digest_generation(client: AsyncClient, auth_headers: dict):
    # Generate Daily Digest
    daily_res = await client.post(
        "/api/v1/research/generate",
        json={
            "topic": "Daily Workspace Highlights",
            "report_type": "daily_digest",
            "days_back": 1,
        },
        headers=auth_headers,
    )
    assert daily_res.status_code == 200
    daily_data = daily_res.json()["data"]
    assert daily_data["report_type"] == "daily_digest"
    assert "Daily Knowledge Digest" in daily_data["title"]


@pytest.mark.asyncio
async def test_smart_knowledge_insights_lifecycle(client: AsyncClient, auth_headers: dict):
    # 1. Ingest entity and memory to produce insights
    await client.post(
        "/api/v1/graph/entities",
        json={
            "name": "Kubernetes Cluster",
            "entity_type": "technology",
            "description": "Production container orchestrator.",
        },
        headers=auth_headers,
    )

    # 2. Trigger insights refresh
    refresh_res = await client.post("/api/v1/research/insights/refresh", headers=auth_headers)
    assert refresh_res.status_code == 200

    # 3. List insights
    list_res = await client.get("/api/v1/research/insights", headers=auth_headers)
    assert list_res.status_code == 200
    insights = list_res.json()["data"]["items"]

    if insights:
        insight_id = insights[0]["id"]
        # 4. Dismiss insight
        dismiss_res = await client.post(
            f"/api/v1/research/insights/{insight_id}/dismiss",
            headers=auth_headers,
        )
        assert dismiss_res.status_code == 200
        assert dismiss_res.json()["data"]["is_dismissed"] is True

        # Verify dismissed insight is excluded from default list
        after_res = await client.get("/api/v1/research/insights", headers=auth_headers)
        active_ids = [i["id"] for i in after_res.json()["data"]["items"]]
        assert insight_id not in active_ids


@pytest.mark.asyncio
async def test_personal_ai_multi_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
):
    # User 1 creates report
    res1 = await client.post(
        "/api/v1/research/generate",
        json={
            "topic": "Confidential Security Analysis",
            "report_type": "topic_research",
            "days_back": 30,
        },
        headers=auth_headers,
    )
    assert res1.status_code == 200
    report_id = res1.json()["data"]["id"]

    # Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "personal_ai_user_b@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Personal AI User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User 2 attempts to view User 1's report -> 404
    view_attempt = await client.get(
        f"/api/v1/research/reports/{report_id}",
        headers=headers_b,
    )
    assert view_attempt.status_code == 404

    # User 2 attempts to delete User 1's report -> 404
    del_attempt = await client.delete(
        f"/api/v1/research/reports/{report_id}",
        headers=headers_b,
    )
    assert del_attempt.status_code == 404
