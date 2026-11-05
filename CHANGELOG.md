# AI-MemoryVerse — Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Phase 0 & Phase 1

### Added
- **Phase 0 — Repository Audit & Foundation**:
  - Full repository audit identifying existing empty skeleton.
  - Git repository initialization with `main` branch.
  - Comprehensive `.gitignore` covering Python, Node, OS, Docker, secrets, and upload caches.
  - Persistent agent instructions in `AGENTS.md` and `GEMINI.md`.
  - Project governance suite: `PROJECT_STATUS.md`, `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, `TECHNICAL_DECISIONS.md`, `KNOWN_ISSUES.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TESTING_STRATEGY.md`, `RESUME_PROJECT_SUMMARY.md`.
  - Production infrastructure configs: `render.yaml`, `docker-compose.yml`, multi-stage Dockerfiles (`docker/Dockerfile.*`).
  - GitHub Actions CI workflow in `.github/workflows/ci.yml`.

- **Phase 1 — Full-Stack Application Foundation**:
  - Asynchronous SQLAlchemy 2.0 database engine and session dependency in `app/core/database.py`.
  - Settings management using Pydantic Settings in `app/core/config.py`.
  - Argon2id password hashing and JWT token handling with rotation in `app/core/security.py`.
  - Relational database models for `User`, `UserProfile`, `UserSession`, `Workspace`, `WorkspaceMember` with JSONB/JSON cross-compatibility.
  - Alembic migrations configuration and initial migration `0001_initial_identity_and_workspaces.py`.
  - Business logic services for authentication and workspace management in `app/services/`.
  - Protected API routes for authentication (`/register`, `/login`, `/refresh`, `/logout`, `/me`), workspaces (`/workspaces`), and health probes (`/health`, `/ready`).
  - Pytest automated test suite with 15 passing tests and 100% pass rate.
  - Ruff linter configuration with strict PEP 8 formatting.

- **Phase 2 — UI Scaffolding & Front-End Setup**:
  - Next.js 14+ App Router, React 18, and TypeScript configuration.
  - Dark-themed knowledge workspace design system with Tailwind CSS in `globals.css` and `tailwind.config.ts`.
  - API client in `lib/api.ts` with automatic auth header and workspace injection.
  - Zustand auth store with localStorage persistence in `store/auth-store.ts`.
  - Marketing landing page with hero, features, workflow, security whitepaper, and transparent pricing.
  - Accessible authentication pages for Sign In and Sign Up.
  - Authenticated dashboard layout with category navigation, mobile drawer, and dynamic workspace switcher.
  - Verified static compilation of all routes via `npm run build`.

- **Phase 3 — Intelligent Memory Engine**:
  - Pluggable AI Provider Abstraction layer in `app/ai/base.py` (`BaseLLMProvider`, `BaseEmbeddingProvider`, `ExtractedFact`, `LLMResponse`).
  - Provider implementations for OpenAI (`app/ai/openai_provider.py`), Google Gemini (`app/ai/gemini_provider.py`), and Deterministic Mock (`app/ai/mock_provider.py`).
  - Dynamic AI provider factory (`app/ai/factory.py`) with automatic fallback to mock engine when API keys are not present.
  - Automatic Fact Extraction pipeline (`app/ai/memory_extractor.py`) with sensitive PII and credential guardrails.
  - Conflict & Contradiction Detection engine (`app/ai/conflict_detector.py`) with lexical antonym pairing, mode inversion, and relocation detection.
  - Human-in-the-Loop Memory Review Inbox router (`app/api/v1/memory_reviews.py`) with approval, rejection, and inline fact correction workflows.
  - Full revision version history and one-click version restoration (`/api/v1/memories/{id}/restore`).
  - Memory Consolidation endpoint (`/api/v1/memories/consolidate`) with automatic supersession and relationship links.
  - Temporal validity management with `valid_from`, `valid_until`, and chronological timeline (`/api/v1/memories/timeline`).
  - Tenancy-isolated Graph links (`MemoryLink`) and user feedback tracking (`MemoryFeedback`).
  - Workspace analytics endpoint (`/api/v1/memories/analytics`) and bulk import/export (JSON and CSV).
  - Alembic database migration `0002_memories` for all Phase 3 tables.
  - 8 new comprehensive automated tests in `tests/test_memory_engine.py` (total 30 passing backend tests).
  - Frontend Review Inbox updated with real review action handlers, conflict warnings, and correction modal.

- **Phase 4 — Document Intelligence**:
  - Pluggable Object Storage Provider adapter in `app/core/storage.py` (`BaseStorageProvider`, `LocalStorageProvider`, `S3StorageProvider`).
  - Document parser in `app/ai/document_parser.py` supporting PDF (`pypdf`), Word (`docx`), Text/Markdown, CSV, JSON, and HTML.
  - Chunking engine in `app/ai/chunker.py` with fixed-size with token overlap, paragraph-based, and markdown semantic header-aware chunking.
  - Asynchronous background worker setup with Celery and Redis in `app/workers/celery_app.py` and `app/workers/tasks.py`.
  - Database models for `Document` and `DocumentChunk` with status tracking (`completed`, `processing`, `failed`), word/token counts, and summary.
  - Alembic database migration `0003_documents` for documents and document_chunks.
  - REST endpoints in `app/api/v1/documents.py` for `/upload`, `/retry`, `/chunks`, `/download`, and CRUD operations.
  - 8 new comprehensive automated tests in `tests/test_document_intelligence.py` (total 38 passing backend tests).
  - Frontend Document Library page connected to live APIs with multipart upload, status badges, chunk inspection modal, retry, and deletion.

- **Phase 5 — Full AI and RAG Engine**:
  - pgvector HNSW database integration with `VectorType` dual-dialect fallback for fast in-memory SQLite unit testing.
  - Vector embedding generation and automated embedding attachment to memories and document chunks.
  - Hybrid Search Engine in `app/ai/retrieval.py` fusing lexical keyword search and dense vector similarity using Reciprocal Rank Fusion (RRF).
  - Multi-signal Reranker in `app/ai/reranker.py` boosting pinned memories, importance weights, and exact keyword alignments.
  - Budget-aware Context Assembler in `app/ai/context_assembler.py` formatting prompts with inline source citation markers (`[1]`, `[2]`).
  - Conversation and Chat Message models (`Conversation`, `ChatMessage`) in `app/models/chat.py`.
  - Alembic database migration `0004_rag_chat` adding conversations, chat_messages, and vector embedding columns.
  - Chat service with session persistence, automatic conversation titling, Server-Sent Events (SSE) streaming, and response feedback ratings.
  - REST endpoints in `app/api/v1/search.py` and `app/api/v1/chat.py`.
  - 5 new comprehensive automated tests in `tests/test_rag_and_chat.py` (total 43 passing backend tests).
  - Frontend Chat page connected to live APIs with conversation sidebar, grounded answer rendering, citation popovers, and feedback buttons.

- **Phase 6 — Advanced Memory & Knowledge Graph**:
  - Relational knowledge graph models (`GraphEntity`, `GraphRelationship`, `EntityType`) in `app/models/graph.py` with multi-tenant workspace isolation and selectin eager loading.
  - Entity and Relationship extraction pipeline (`GraphExtractor`) in `app/ai/graph_extractor.py` supporting rule-based regex patterns and LLM JSON extraction.
  - Graph service (`GraphService`) in `app/services/graph_service.py` with entity CRUD, edge creation, degree computation, neighborhood queries, and graph analytics.
  - Alembic database migration `0005_knowledge_graph` adding `graph_entities` and `graph_relationships` with foreign key cascades and unique constraints.
  - REST endpoints in `app/api/v1/graph.py` mounted at `/api/v1/graph` for `/entities`, `/relationships`, `/workspace`, `/neighborhood/{entity_id}`, `/analytics`, and `/extract`.
  - 5 comprehensive automated tests in `tests/test_knowledge_graph.py` (total 48 passing backend tests).
  - Interactive SVG/Canvas Knowledge Graph explorer page in `frontend/app/(dashboard)/graph/page.tsx` with pan, zoom, node drag, search filtering by entity type, selected entity details drawer, and create entity / connect modals.

- **Phase 7 — Personal AI Features**:
  - Speech-to-Text and Text-to-Speech audio provider abstraction and implementations in `app/ai/audio_providers.py` (`MockSTTProvider`, `MockTTSProvider`, `OpenAISTTProvider`, `OpenAITTSProvider`) and factory `app/ai/audio_factory.py`.
  - Audio transcription endpoint (`/api/v1/voice/transcribe`) and real-time audio synthesis endpoint (`/api/v1/voice/synthesize`).
  - Real-time voice chat endpoint (`/api/v1/voice/chat`) retrieving memory context and streaming back grounded answers with instant base64 audio data.
  - Multi-document research synthesis engine in `app/services/research_service.py` supporting `topic_research`, `daily_digest`, `weekly_summary`, and `project_brief`.
  - Automated Smart Knowledge Insights scanner identifying stale facts, unresolved contradiction flags, high-centrality graph hubs, and undocumented project gaps.
  - Relational database models for `ResearchReport` and `KnowledgeInsight` in `app/models/research.py` with Alembic migration `0006_research_and_insights`.
  - REST endpoints mounted in `app/api/v1/research.py` (`/reports`, `/generate`, `/insights`, `/insights/refresh`, `/insights/{id}/dismiss`).
  - 6 comprehensive automated tests in `tests/test_personal_ai.py` (total 54 passing backend tests).
  - Frontend Voice Assistant page in `frontend/app/(dashboard)/voice/page.tsx` with Web Audio MediaRecorder recording, pulsing waveform visualizer, and live audio playback.
  - Frontend Research Lab page in `frontend/app/(dashboard)/research/page.tsx` with report generator, scope configuration, and markdown reader.
  - Frontend Smart Insights page in `frontend/app/(dashboard)/insights/page.tsx` with diagnostic cards and 1-click remediation actions.

- **Phase 8 — Controlled Agents & Integrations**:
  - SSRF protection module in `app/core/ssrf.py` validating scheme, host, and resolving IP addresses against loopback (`127.0.0.0/8`), RFC 1918 private networks, AWS/cloud metadata (`169.254.169.254`), carrier-grade NAT, and IPv6 loopback.
  - Webpage text extractor and HTML sanitizer in `app/services/url_service.py` stripping scripts, stylesheets, and formatting semantic text.
  - Autonomous Tool Registry (`ToolRegistry`) in `app/ai/tools.py` with 7 pre-registered tools (`search_memories`, `search_documents`, `lookup_knowledge_graph`, `fetch_web_url`, `propose_memory`, `delete_memory`, `trigger_webhook`) and risk classification (`LOW`, `MEDIUM`, `HIGH`).
  - Relational models for `AgentTask`, `AgentAction`, and `APIToken` in `app/models/agent.py` with Alembic database migration `0007_agents_and_integrations`.
  - Autonomous Agent Service (`AgentService`) in `app/services/agent_service.py` managing multi-step task execution, step limits, latency measurement, and Human-in-the-Loop approval/rejection checkpoints for high-risk actions.
  - Cryptographic API token service generating SHA-256 hashed tokens with customizable permission scopes and expiration policies.
  - REST API endpoints for agent tasks (`/api/v1/agents/tasks`), action approvals (`/api/v1/agents/actions/{id}/approve`), web importer (`/api/v1/agents/import-url`), and tokens (`/api/v1/tokens`).
  - 7 comprehensive automated tests in `tests/test_agents_and_integrations.py` (total 61 passing backend tests).
  - Frontend Controlled Agents management page in `frontend/app/(dashboard)/automation/page.tsx` with urgent approval banners, task progress bars, action audit trail, tool registry drawer, and SSRF webpage importer modal.
  - Frontend Developer API Keys & Integrations Hub in `frontend/app/(dashboard)/integrations/page.tsx` with token table, scope configurator, one-time plaintext key reveal modal, and cURL quickstart documentation.

- **Phase 9 — SaaS Product System**:
  - SaaS subscription models and plan definitions (`Free`, `Personal`, `Pro`, `Team`) with strict quota limits for memory vault count, documents, storage bytes, and AI queries.
  - Real-time Quota Metering Service in `app/services/billing_service.py` computing live storage size, memory counts, document uploads, and query consumptions.
  - Pluggable Payment Provider abstraction in `app/services/payment_provider.py` (`BasePaymentProvider`, `StripePaymentProvider`, `SandboxPaymentProvider`).
  - Automatic invoice generation and lifecycle tracking with unique invoice numbering and paid status.
  - Admin Console and Telemetry Service in `app/services/admin_service.py` measuring database query latency, cache status, storage health, and background worker queue depths.
  - Security and operational audit log stream in `app/models/billing.py` (`AuditEvent`) capturing events with IP, user agent, and payload metadata.
  - Alembic database migration `0008_billing_and_admin` creating `subscriptions`, `invoices`, and `audit_events`.
  - REST API endpoints for billing (`/api/v1/billing/*`) and admin oversight (`/api/v1/admin/*`).
  - 9 comprehensive automated tests in `tests/test_billing_and_admin.py` (total 70 passing backend tests).
  - Frontend Usage & Billing dashboard in `frontend/app/(dashboard)/billing/page.tsx` with real-time progress bars, plan comparison grid, 1-click sandbox upgrade, and invoice table.
  - Frontend Admin Telemetry & Health console in `frontend/app/(dashboard)/admin/page.tsx` with service health probes, subscription breakdown, and expandable audit log viewer.

