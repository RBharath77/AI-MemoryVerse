from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_binary_malware_upload_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify executable binaries (Linux ELF, Windows PE) renamed to .txt or .pdf are blocked."""
    # 1. Linux ELF binary disguised as .txt
    elf_bytes = b"\x7fELF" + b"\x01\x01\x01\x00" * 20
    files_elf = {"file": ("malicious_script.txt", io.BytesIO(elf_bytes), "text/plain")}
    res_elf = await client.post("/api/v1/documents/upload", files=files_elf, headers=auth_headers)
    assert res_elf.status_code == 400
    assert "Executable binary" in res_elf.json()["error"]["message"]

    # 2. Windows PE binary disguised as .pdf
    pe_bytes = b"MZ" + b"\x90\x00\x03\x00" * 20
    files_pe = {"file": ("invoice.pdf", io.BytesIO(pe_bytes), "application/pdf")}
    res_pe = await client.post("/api/v1/documents/upload", files=files_pe, headers=auth_headers)
    assert res_pe.status_code == 400
    assert "Executable binary" in res_pe.json()["error"]["message"]


@pytest.mark.asyncio
async def test_corrupt_pdf_header_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that a file with .pdf extension lacking %PDF- magic bytes is rejected."""
    corrupt_pdf_bytes = b"This is just plain text masquerading as a PDF document."
    files = {"file": ("report.pdf", io.BytesIO(corrupt_pdf_bytes), "application/pdf")}
    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 400
    assert "Corrupted or invalid PDF header" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_filename_traversal_sanitized(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify path traversal sequences in filenames are sanitized to prevent directory escaping."""
    safe_content = b"# Valid Markdown Document\n\nSanitized filename upload test."
    files = {"file": ("../../../../etc/passwd.md", io.BytesIO(safe_content), "text/markdown")}
    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 201
    doc_data = res.json()["data"]["document"]
    assert ".." not in doc_data["filename"]
    assert "/" not in doc_data["filename"]
    assert doc_data["filename"] == "passwd.md"


@pytest.mark.asyncio
async def test_raw_download_security_headers(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify raw document streaming endpoints enforce sandbox CSP and nosniff headers."""
    # 1. Upload a markdown file
    files = {"file": ("security_test.md", io.BytesIO(b"# Security Test"), "text/markdown")}
    upload_res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["data"]["document"]["id"]

    # 2. Download raw file
    raw_res = await client.get(f"/api/v1/documents/{doc_id}/raw", headers=auth_headers)
    assert raw_res.status_code == 200
    assert raw_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert "sandbox" in raw_res.headers.get("Content-Security-Policy", "")
    assert "attachment" in raw_res.headers.get("Content-Disposition", "")


@pytest.mark.asyncio
async def test_production_billing_direct_upgrade_forbidden(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify direct plan upgrades are blocked in non-sandbox environments for regular users."""
    original_provider = settings.PAYMENT_PROVIDER
    try:
        # Simulate production payment provider
        settings.PAYMENT_PROVIDER = "stripe"

        res = await client.post(
            "/api/v1/billing/upgrade",
            json={"plan_tier": "pro"},
            headers=auth_headers,
        )
        assert res.status_code == 403
        assert "restricted to sandbox environments" in res.json()["error"]["message"]
    finally:
        settings.PAYMENT_PROVIDER = original_provider
