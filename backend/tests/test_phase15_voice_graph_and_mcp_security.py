from __future__ import annotations

import io
import wave

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.models.chat import ChatMessage, Conversation
from app.models.graph import EntityType, GraphEntity, GraphRelationship


def _create_minimal_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 400)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_voice_transcribe_malware_and_extension_blocking(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that /voice/transcribe blocks executable malware and disallowed extensions."""
    # 1. Disallowed extension (.exe)
    res_exe = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("malware.exe", b"not a wav", "application/octet-stream")},
        headers=auth_headers,
    )
    assert res_exe.status_code == 400
    assert "Unsupported audio format" in res_exe.text

    # 2. Disallowed extension (.sh)
    res_sh = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("script.sh", b"#!/bin/bash\necho 1", "text/x-shellscript")},
        headers=auth_headers,
    )
    assert res_sh.status_code == 400
    assert "Unsupported audio format" in res_sh.text

    # 3. Executable Windows PE signature masquerading as .wav
    pe_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    res_pe = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("trojan.wav", pe_bytes, "audio/wav")},
        headers=auth_headers,
    )
    assert res_pe.status_code == 400
    assert "Executable binary" in res_pe.text

    # 4. Executable Linux ELF signature masquerading as .mp3
    elf_bytes = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
    res_elf = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("exploit.mp3", elf_bytes, "audio/mpeg")},
        headers=auth_headers,
    )
    assert res_elf.status_code == 400
    assert "Executable binary" in res_elf.text

    # 5. Valid WAV bytes -> Success
    valid_wav = _create_minimal_wav()
    res_valid = await client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("valid_sample.wav", valid_wav, "audio/wav")},
        headers=auth_headers,
    )
    assert res_valid.status_code == 200
    assert "text" in res_valid.json()["data"]


@pytest.mark.asyncio
async def test_voice_synthesize_and_chat_credential_redaction(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that secret credentials are automatically scrubbed from voice synthesis and voice chat."""
    # 1. Test credential scrubbing on synthesize endpoint
    raw_secret = (
        "The secret database key is sk-proj-1234567890abcdef1234567890 and AWS AKIAIOSFODNN7EXAMPLE"
    )
    synth_res = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": raw_secret, "voice": "alloy"},
        headers=auth_headers,
    )
    assert synth_res.status_code == 200
    assert "audio" in synth_res.headers["content-type"]

    # 2. Cross-tenant conversation validation in voice chat
    # Create another tenant's conversation
    async with core_db.async_session_factory() as db:
        foreign_conv = Conversation(
            workspace_id="00000000-0000-0000-0000-000000000000",
            user_id="foreign_user",
            title="Foreign Conversation",
        )
        db.add(foreign_conv)
        await db.commit()
        await db.refresh(foreign_conv)
        foreign_conv_id = foreign_conv.id

    # Attempt voice chat referencing foreign conversation -> 404
    foreign_chat_res = await client.post(
        "/api/v1/voice/chat",
        json={
            "query": "Synthesize status update",
            "conversation_id": foreign_conv_id,
            "voice": "alloy",
        },
        headers=auth_headers,
    )
    assert foreign_chat_res.status_code == 404


@pytest.mark.asyncio
async def test_graph_entity_and_relationship_deletion_rbac(client: AsyncClient):
    """Verify that regular workspace members cannot delete graph entities or relationships."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "graph_owner@phase15.ai",
            "password": "Password123!",
            "full_name": "Graph Owner",
            "workspace_name": "Graph RBAC WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member
    reg_mem = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "graph_member@phase15.ai",
            "password": "Password123!",
            "full_name": "Graph Member",
        },
    )
    mem_token = reg_mem.json()["data"]["tokens"]["access_token"]
    mem_user_id = reg_mem.json()["data"]["user"]["id"]
    mem_headers = {"Authorization": f"Bearer {mem_token}", "X-Workspace-ID": ws_id}

    # Add member to workspace
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": mem_user_id, "role": "member"},
        headers=owner_headers,
    )

    # 3. Owner creates two graph entities and a relationship
    async with core_db.async_session_factory() as db:
        e1 = GraphEntity(
            workspace_id=ws_id,
            name="FastAPI Service",
            entity_type=EntityType.TECHNOLOGY,
            description="High-performance async API server",
        )
        e2 = GraphEntity(
            workspace_id=ws_id,
            name="PostgreSQL Database",
            entity_type=EntityType.TECHNOLOGY,
            description="Primary relational datastore",
        )
        db.add_all([e1, e2])
        await db.commit()
        await db.refresh(e1)
        await db.refresh(e2)

        rel = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e1.id,
            target_entity_id=e2.id,
            relationship_type="connects_to",
            weight=1.0,
        )
        db.add(rel)
        await db.commit()
        await db.refresh(rel)
        rel_id = rel.id
        e1_id = e1.id

    # 4. Regular member attempts to delete relationship -> 403 Forbidden
    del_rel_mem = await client.delete(
        f"/api/v1/graph/relationships/{rel_id}",
        headers=mem_headers,
    )
    assert del_rel_mem.status_code == 403
    assert "Insufficient permissions" in del_rel_mem.text

    # 5. Regular member attempts to delete entity -> 403 Forbidden
    del_ent_mem = await client.delete(
        f"/api/v1/graph/entities/{e1_id}",
        headers=mem_headers,
    )
    assert del_ent_mem.status_code == 403
    assert "Insufficient permissions" in del_ent_mem.text

    # 6. Owner deletes relationship -> 200 OK
    del_rel_owner = await client.delete(
        f"/api/v1/graph/relationships/{rel_id}",
        headers=owner_headers,
    )
    assert del_rel_owner.status_code == 200

    # 7. Owner deletes entity -> 200 OK
    del_ent_owner = await client.delete(
        f"/api/v1/graph/entities/{e1_id}",
        headers=owner_headers,
    )
    assert del_ent_owner.status_code == 200


@pytest.mark.asyncio
async def test_chat_feedback_conversation_idor_isolation(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that message feedback requires message to belong strictly to specified conversation."""
    ws_id = auth_headers["X-Workspace-ID"]

    async with core_db.async_session_factory() as db:
        # Create Conv 1 with Message 1
        conv1 = Conversation(workspace_id=ws_id, user_id="test_user", title="Conv 1")
        # Create Conv 2 with Message 2
        conv2 = Conversation(workspace_id=ws_id, user_id="test_user", title="Conv 2")
        db.add_all([conv1, conv2])
        await db.commit()
        await db.refresh(conv1)
        await db.refresh(conv2)

        msg1 = ChatMessage(
            conversation_id=conv1.id,
            workspace_id=ws_id,
            user_id="test_user",
            role="assistant",
            content="Answer 1",
            token_count=10,
        )
        msg2 = ChatMessage(
            conversation_id=conv2.id,
            workspace_id=ws_id,
            user_id="test_user",
            role="assistant",
            content="Answer 2",
            token_count=10,
        )
        db.add_all([msg1, msg2])
        await db.commit()
        await db.refresh(msg1)
        await db.refresh(msg2)

        conv1_id = conv1.id
        msg1_id = msg1.id
        msg2_id = msg2.id

    # 1. Mismatched: Submit feedback for Msg 2 using Conv 1 URL -> 404 Not Found
    res_mismatch = await client.post(
        f"/api/v1/chat/conversations/{conv1_id}/messages/{msg2_id}/feedback",
        json={"rating": 1},
        headers=auth_headers,
    )
    assert res_mismatch.status_code == 404

    # 2. Matched: Submit feedback for Msg 1 using Conv 1 URL -> 200 OK
    res_match = await client.post(
        f"/api/v1/chat/conversations/{conv1_id}/messages/{msg1_id}/feedback",
        json={"rating": 1},
        headers=auth_headers,
    )
    assert res_match.status_code == 200
    assert res_match.json()["data"]["feedback"] == 1


@pytest.mark.asyncio
async def test_mcp_server_models_and_schema_integrity():
    """Verify that all application tables are registered in Base.metadata for MCP server bootstrap."""
    import app.models  # noqa: F401
    from app.core.database import Base

    table_names = set(Base.metadata.tables.keys())

    required_tables = {
        "users",
        "user_profiles",
        "workspaces",
        "workspace_members",
        "memories",
        "memory_reviews",
        "documents",
        "document_chunks",
        "graph_entities",
        "graph_relationships",
        "conversations",
        "chat_messages",
        "agent_tasks",
        "agent_actions",
        "api_tokens",
        "audit_events",
        "research_reports",
        "knowledge_insights",
    }

    missing = required_tables - table_names
    assert not missing, f"MCP bootstrap missing tables in Base.metadata: {missing}"
