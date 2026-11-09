import io

import pytest
from docx import Document as DocxDocument
from httpx import AsyncClient
from pypdf import PdfWriter


def create_sample_pdf_bytes() -> bytes:
    """Generate a minimal valid PDF in-memory for testing."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_sample_docx_bytes() -> bytes:
    """Generate a minimal valid DOCX in-memory for testing."""
    doc = DocxDocument()
    doc.add_heading("Architecture Overview", level=1)
    doc.add_paragraph("AI-MemoryVerse utilizes PostgreSQL with pgvector for HNSW indexing.")
    doc.add_paragraph(
        "Celery executes asynchronous document ingestion and memory extraction pipelines."
    )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_and_parse_text_document(client: AsyncClient, auth_headers: dict):
    content = (
        "Project Orion Architecture.\n\n"
        "The backend is powered by FastAPI and SQLAlchemy 2.0 async engine.\n\n"
        "Security is enforced with Argon2id hashing and JWT token rotation."
    )
    files = {"file": ("orion_architecture.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    data = {"title": "Orion Architecture Specification"}

    res = await client.post(
        "/api/v1/documents/upload", files=files, data=data, headers=auth_headers
    )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    doc = body["data"]["document"]

    assert doc["title"] == "Orion Architecture Specification"
    assert doc["filename"] == "orion_architecture.txt"
    assert doc["status"] == "completed"
    assert doc["word_count"] > 10
    assert doc["chunk_count"] >= 1

    doc_id = doc["id"]

    # Retrieve chunks
    chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers)
    assert chunks_res.status_code == 200
    chunks_data = chunks_res.json()["data"]
    assert chunks_data["total"] >= 1
    assert "FastAPI" in chunks_data["items"][0]["content"]


@pytest.mark.asyncio
async def test_markdown_semantic_header_chunking(client: AsyncClient, auth_headers: dict):
    md_content = """# Memory Ingestion Engine

The memory engine automatically identifies atomic facts from user interactions.

## Duplicate Detection

Deduplication uses token-level Jaccard similarity and exact normalized matching.

## Contradiction Detection

Contradictions are flagged whenever opposing polarities on shared topics are found.
"""
    files = {"file": ("memory_engine.md", io.BytesIO(md_content.encode("utf-8")), "text/markdown")}
    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 201
    doc_id = res.json()["data"]["document"]["id"]

    # Verify chunks have section titles
    chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers)
    assert chunks_res.status_code == 200
    items = chunks_res.json()["data"]["items"]
    assert len(items) >= 2

    section_titles = [c.get("section_title") for c in items if c.get("section_title")]
    assert any("Duplicate Detection" in t for t in section_titles)
    assert any("Contradiction Detection" in t for t in section_titles)


@pytest.mark.asyncio
async def test_upload_and_parse_docx(client: AsyncClient, auth_headers: dict):
    docx_bytes = create_sample_docx_bytes()
    files = {
        "file": (
            "architecture.docx",
            io.BytesIO(docx_bytes),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 201
    doc = res.json()["data"]["document"]
    assert doc["status"] == "completed"
    assert doc["word_count"] > 5


@pytest.mark.asyncio
async def test_upload_and_parse_pdf(client: AsyncClient, auth_headers: dict):
    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("blank_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 201
    doc = res.json()["data"]["document"]
    assert doc["status"] == "completed"
    assert doc["page_count"] >= 1


@pytest.mark.asyncio
async def test_document_list_and_filters(client: AsyncClient, auth_headers: dict):
    # Upload doc 1
    await client.post(
        "/api/v1/documents/upload",
        files={
            "file": ("searchable_doc.txt", io.BytesIO(b"UniqueSearchTermForFilter"), "text/plain")
        },
        headers=auth_headers,
    )

    # List all
    list_res = await client.get("/api/v1/documents", headers=auth_headers)
    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] >= 1

    # Search filter
    search_res = await client.get("/api/v1/documents?search=searchable_doc", headers=auth_headers)
    assert search_res.status_code == 200
    items = search_res.json()["data"]["items"]
    assert len(items) >= 1
    assert "searchable_doc" in items[0]["filename"]


@pytest.mark.asyncio
async def test_document_retry_and_delete(client: AsyncClient, auth_headers: dict):
    files = {"file": ("retry_test.txt", io.BytesIO(b"Data for retry testing"), "text/plain")}
    upload_res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    doc_id = upload_res.json()["data"]["document"]["id"]

    # Retry endpoint
    retry_res = await client.post(f"/api/v1/documents/{doc_id}/retry", headers=auth_headers)
    assert retry_res.status_code == 200
    assert retry_res.json()["data"]["status"] == "completed"

    # Download URL endpoint
    dl_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    assert dl_res.status_code == 200
    assert "download_url" in dl_res.json()["data"]

    # Delete endpoint
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm 404
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_document_multi_tenant_isolation(client: AsyncClient, auth_headers: dict):
    # User A uploads document
    files = {
        "file": ("user_a_secret.txt", io.BytesIO(b"Top secret document of User A"), "text/plain")
    }
    res_a = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    doc_a_id = res_a.json()["data"]["document"]["id"]

    # Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "docuserb@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Doc User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User B attempts to access User A's document
    res_get = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
    assert res_get.status_code == 404

    # User B attempts to get chunks of User A's document
    res_chunks = await client.get(f"/api/v1/documents/{doc_a_id}/chunks", headers=headers_b)
    assert res_chunks.status_code == 404

    # User B attempts to delete User A's document
    res_del = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
    assert res_del.status_code == 404


@pytest.mark.asyncio
async def test_unsupported_file_type_rejection(client: AsyncClient, auth_headers: dict):
    # Executable file upload attempt
    files = {
        "file": (
            "malicious.exe",
            io.BytesIO(b"MZ executable header binary data"),
            "application/x-msdownload",
        )
    }
    res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_download_document_and_raw_stream(client: AsyncClient, auth_headers: dict):
    """Phase 2: Verify streaming document download routes."""
    test_content = "This is a confidential architecture diagram and documentation text."
    files = {
        "file": (
            "architecture_spec.txt",
            io.BytesIO(test_content.encode("utf-8")),
            "text/plain",
        )
    }
    upload_res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["data"]["document"]["id"]

    # 1. Get download URL
    url_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    assert url_res.status_code == 200
    download_url = url_res.json()["data"]["download_url"]
    assert "download-file?key=" in download_url

    # 2. Execute download via key endpoint
    dl_res = await client.get(download_url, headers=auth_headers)
    assert dl_res.status_code == 200
    assert dl_res.text == test_content
    assert "architecture_spec.txt" in dl_res.headers.get("content-disposition", "")

    # 3. Direct raw download endpoint
    raw_res = await client.get(f"/api/v1/documents/{doc_id}/raw", headers=auth_headers)
    assert raw_res.status_code == 200
    assert raw_res.text == test_content


@pytest.mark.asyncio
async def test_download_document_tenant_isolation_and_path_traversal(
    client: AsyncClient, auth_headers: dict
):
    """Phase 2: Cross-tenant download and path traversal attempts must be rejected."""
    # Upload document in tenant A
    files = {
        "file": (
            "private_report.txt",
            io.BytesIO(b"Tenant A Private Report"),
            "text/plain",
        )
    }
    upload_res = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    doc_id = upload_res.json()["data"]["document"]["id"]

    url_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    download_url = url_res.json()["data"]["download_url"]

    # Register tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "intruder@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Intruder User",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # Tenant B attempts to download Tenant A's document via key
    cross_dl = await client.get(download_url, headers=headers_b)
    assert cross_dl.status_code == 404

    # Tenant B attempts to download Tenant A's document via raw ID
    cross_raw = await client.get(f"/api/v1/documents/{doc_id}/raw", headers=headers_b)
    assert cross_raw.status_code == 404

    # Path traversal attack attempt
    traversal_res = await client.get(
        "/api/v1/documents/download-file?key=../../../../etc/passwd",
        headers=auth_headers,
    )
    assert traversal_res.status_code == 404
