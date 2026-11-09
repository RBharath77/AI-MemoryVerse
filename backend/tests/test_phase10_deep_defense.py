from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.context_assembler import ContextAssembler
from app.ai.retrieval import SearchResultItem
from app.core import database as core_db
from app.core.audit import SecurityAuditLogger
from app.core.sanitizer import CredentialSanitizer
from app.core.ssrf import is_ip_allowed


@pytest.mark.asyncio
async def test_ssrf_ipv4_mapped_ipv6_blocked():
    """Verify that IPv4-mapped IPv6 bypasses (e.g. ::ffff:127.0.0.1, ::ffff:169.254.169.254) are rejected."""
    # 1. Loopback mapped IPv6
    assert not is_ip_allowed("::ffff:127.0.0.1")

    # 2. AWS / Cloud metadata mapped IPv6
    assert not is_ip_allowed("::ffff:169.254.169.254")

    # 3. RFC 1918 Private mapped IPv6
    assert not is_ip_allowed("::ffff:10.0.0.1")
    assert not is_ip_allowed("::ffff:192.168.1.1")

    # 4. Valid public internet routable IP
    assert is_ip_allowed("8.8.8.8")
    assert is_ip_allowed("1.1.1.1")


@pytest.mark.asyncio
async def test_credential_sanitizer_redaction():
    """Verify CredentialSanitizer identifies and redacts various high-risk credential types."""
    sample_text = (
        "Here is my OpenAI key " + ("sk-proj-" + "1234567890abcdef1234567890\n") +
        "And AWS credentials " + ("AKIA" + "IOSFODNN7EXAMPLE\n") +
        "GitHub token " + ("ghp_" + "123456789012345678901234567890123456\n") +
        "Card payment 4111111111111111 with SSN 123-45-6789."
    )

    result = CredentialSanitizer.redact(sample_text)
    sanitized = result.sanitized_text

    assert "OPENAI_API_KEY" in result.detected_types
    assert "AWS_ACCESS_KEY" in result.detected_types
    assert "GITHUB_TOKEN" in result.detected_types
    assert "CREDIT_CARD" in result.detected_types
    assert "SSN" in result.detected_types

    assert "sk-proj-" not in sanitized
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "4111111111111111" not in sanitized
    assert "[REDACTED_OPENAI_KEY]" in sanitized
    assert "[REDACTED_AWS_KEY]" in sanitized
    assert "[REDACTED_CREDIT_CARD]" in sanitized


@pytest.mark.asyncio
async def test_context_assembler_credential_sanitization():
    """Verify context assembler redacts sensitive API keys from user prompts and sources before LLM generation."""
    secret_key = "sk-proj-" + "supersecretkeyforproduction123456"
    mock_context = [
        SearchResultItem(
            id="doc-credentials",
            source_type="document",
            title="Dev Environment Guide",
            content=f"Set OPENAI_API_KEY={secret_key} in your terminal.",
            score=0.9,
        )
    ]

    assembled = ContextAssembler.assemble(
        user_query=f"Can you explain how to use {secret_key}?",
        conversation_history=[],
        grounding_contexts=mock_context,
    )

    sys_content = assembled.messages[0].content
    user_content = assembled.messages[1].content

    # The raw secret key must not appear anywhere in system or user prompt messages
    assert secret_key not in sys_content
    assert secret_key not in user_content
    assert "[REDACTED_OPENAI_KEY]" in sys_content
    assert "[REDACTED_OPENAI_KEY]" in user_content


@pytest.mark.asyncio
async def test_security_audit_logger_persistence():
    """Verify security audit logger persists and counts events."""
    async with core_db.async_session_factory() as db:
        event = await SecurityAuditLogger.log_event(
            db=db,
            action="TEST_SECURITY_EVENT",
            workspace_id="test-ws-id",
            user_id="test-user-id",
            ip_address="192.168.1.50",
            details={"reason": "test"},
        )
        assert event is not None
        assert event.action == "TEST_SECURITY_EVENT"

        events = await SecurityAuditLogger.get_recent_events(db, workspace_id="test-ws-id", limit=5)
        assert any(e.action == "TEST_SECURITY_EVENT" for e in events)

        count = await SecurityAuditLogger.get_event_count(db, workspace_id="test-ws-id")
        assert count >= 1


@pytest.mark.asyncio
async def test_security_diagnostics_endpoint_rbac(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """Verify /health/security enforces admin RBAC and returns Grade A+ diagnostics."""
    # 1. Unauthenticated request -> 401
    client.cookies.clear()
    unauth_res = await client.get("/api/v1/health/security")
    assert unauth_res.status_code == 401

    # 2. Regular user request -> 403 Forbidden
    user_res = await client.get("/api/v1/health/security", headers=auth_headers)
    assert user_res.status_code == 403

    # 3. Superuser request -> 200 OK with Grade A+
    admin_res = await client.get("/api/v1/health/security", headers=admin_headers)
    assert admin_res.status_code == 200
    data = admin_res.json()
    assert data["status"] == "healthy"
    assert data["security_grade"] == "A+"
    assert data["controls"]["ssrf_protection_active"] is True
    assert data["controls"]["mcp_authentication_enforced"] is True
    assert data["controls"]["demo_login_disabled"] is True
