# AI-MemoryVerse — Agent & Engineering Guidelines

## 1. Project Identity & Vision
**Product Name:** AI-MemoryVerse  
**Category:** Personal AI Memory and Knowledge Intelligence Platform  
**Tagline:** *Remember. Connect. Understand. Retrieve.*  
**Architecture:** Modular Monolith (FastAPI + Next.js App Router + PostgreSQL with pgvector + Celery/Redis + S3/MinIO Object Storage)

---

## 2. Core Engineering Principles
1. **Genuine Working Functionality**: No decorative non-functional buttons, fabricated AI statistics, hardcoded mock responses masquerading as real data, or pretended database transactions.
2. **Multi-Tenant Data Isolation**: Every database query, vector search, document ingestion, and conversation retrieval MUST enforce strict user and workspace tenancy (`workspace_id` and `user_id` ownership checks).
3. **Defense-in-Depth Security**:
   - Argon2id password hashing.
   - HttpOnly, SameSite, Secure JWT session handling.
   - Strict input validation via Pydantic v2 (Backend) and Zod (Frontend).
   - Prompt-injection defenses and untrusted document sanitization.
   - Parameterized SQL execution (SQLAlchemy 2.x ORM / Core).
   - SSRF protection on any URL fetcher/crawler.
4. **Provider Abstraction**: Never tightly couple core business logic to OpenAI, Anthropic, or Gemini. Utilize pluggable provider adapters (`LLMProvider`, `EmbeddingProvider`, `SpeechToTextProvider`, `TextToSpeechProvider`, `VisionProvider`).
5. **Asynchronous Background Processing**: Never process large documents, embeddings, OCR, or heavy reports in the request-response cycle. Offload to Celery workers with idempotent job tracking in PostgreSQL.
6. **Stateless App & Ephemeral Disk Awareness**: Application servers (Render Web Services) must remain stateless. Uploaded documents and artifacts reside in S3-compatible object storage, metadata in PostgreSQL.

---

## 3. Technology Stack & Directory Conventions

### Backend (`/backend`)
- **Runtime:** Python 3.11+ / 3.14 (FastAPI + Uvicorn)
- **Data Layer:** SQLAlchemy 2.x (async engine), Alembic for schema migrations, `pgvector` for vector similarity searches.
- **Background Processing:** Celery + Redis.
- **Folder Structure:**
  - `app/api/v1/`: API route controllers grouping endpoints by domain (`auth`, `users`, `workspaces`, `memories`, `documents`, `chat`, `search`, `graph`, `analytics`, etc.).
  - `app/core/`: Security utilities (Argon2id, JWT), database engine session managers, base configurations (`config.py`).
  - `app/models/`: SQLAlchemy 2.0 ORM models.
  - `app/schemas/`: Pydantic models for request validation and response serialization.
  - `app/services/`: Pure business logic decoupling database operations from routing.
  - `app/ai/`: Provider adapters, RAG pipelines, chunking, memory extraction, reranking, graph entity extractors.
  - `app/workers/`: Celery tasks for background processing.
  - `tests/`: Pytest suite (unit, integration, security, evaluation).

### Frontend (`/frontend`)
- **Framework:** Next.js 14+ (App Router), React 18/19, TypeScript.
- **Styling & UI:** Tailwind CSS, shadcn/ui component architecture, Lucide icons.
- **State & Data Fetching:** TanStack Query v5, Zustand for local client state, React Hook Form + Zod.
- **Folder Structure:**
  - `app/`: Next.js App Router pages, layouts, route handlers.
  - `components/ui/`: Base shadcn/ui accessible primitives.
  - `components/`: Shared application components (Header, Sidebar, Modals, EmptyStates).
  - `features/`: Domain-specific components, hooks, and views (`chat`, `memory`, `documents`, `graph`, `analytics`, `settings`, `billing`).
  - `lib/`: Axios/Fetch API client, auth helpers, utility functions.
  - `types/`: Shared TypeScript interfaces and types.

---

## 4. Coding Standards & Conventions
- **Python**: PEP 8 compliance, explicit type hints (`typing`), Pydantic models for validation, descriptive docstrings.
- **TypeScript**: Strict mode enabled (`strict: true`), zero `any` wherever possible, strict Zod schemas for all forms and API payloads.
- **REST Endpoints**: Base prefix `/api/v1`. Consistent JSON error responses:
  ```json
  {
    "success": false,
    "error": {
      "code": "RESOURCE_NOT_FOUND",
      "message": "The requested memory does not exist or access is unauthorized",
      "details": {}
    }
  }
  ```
- **Git Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

---

## 5. Testing & Verification Standards
- Every phase must pass its acceptance criteria with automated tests before advancing.
- Backend tests must run via `pytest` and verify:
  1. Authentication & RBAC boundaries.
  2. Data isolation between tenants.
  3. Memory extraction and RAG retrieval pipelines.
  4. Document ingestion and chunking logic.
  5. Failure recovery & idempotency.
