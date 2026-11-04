# AI-MemoryVerse — Technical Decisions & ADRs

## ADR-001: Architecture Pattern — Modular Monolith over Microservices
- **Context:** The application requires high developer velocity, transactional consistency across identity, memories, documents, and chat, while running on resource-constrained environments (Apple Silicon Mac local dev + Render cloud deployment).
- **Decision:** Build a modular monolith in FastAPI with decoupled domain packages (`auth`, `memories`, `documents`, `chat`, `ai`, `graph`, `workers`).
- **Consequences:** Eliminates network serialization overhead, simplifies transaction handling, reduces deployment surface to 1 API service, 1 Worker service, 1 Web service, and simplifies local development.

---

## ADR-002: Vector Storage — PostgreSQL + pgvector vs Dedicated Vector DB (Pinecone/Milvus)
- **Context:** Memories and document chunks have rich relational metadata (user ownership, workspace permissions, tags, version history, temporal validity dates).
- **Decision:** Use PostgreSQL with the `pgvector` extension.
- **Consequences:** Eliminates dual-write consistency problems between relational database and external vector DB; enables atomic transactions, simplifies backups, and avoids extra hosting costs on Render.

---

## ADR-003: AI Provider Layer — Adapter Pattern with Multi-Provider Support
- **Context:** Relying solely on a single AI provider (e.g. OpenAI) introduces vendor lock-in, price volatility, and breaks tests when API keys are absent.
- **Decision:** Implement abstract base classes (`LLMProvider`, `EmbeddingProvider`) with concrete implementations for OpenAI, Anthropic, Google Gemini, Ollama, and a deterministic `MockProvider` for testing and disconnected local states.
- **Consequences:** Application runs and passes tests locally even without live API keys, while allowing production switching via simple environment variables.

---

## ADR-004: Password Security — Argon2id over Bcrypt
- **Context:** Passwords require resistance against GPU/ASIC-based cracking attacks.
- **Decision:** Use Argon2id via `pwdlib[argon2]` or `passlib[argon2]`.
- **Consequences:** Industry-standard password hashing algorithm winner of the Password Hashing Competition (PHC), providing memory-hardness and time-cost trade-offs.

---

## ADR-005: Background Task Queue — Celery + Redis
- **Context:** Heavy document extraction (PDF, DOCX, OCR), bulk embedding generation, and summary generation take seconds or minutes and must not block HTTP request threads.
- **Decision:** Use Celery with Redis (or Render Key Value in production).
- **Consequences:** Reliable task execution with automatic retry policies, dead-letter state tracking, and independent worker horizontal scaling.

---

## ADR-006: Frontend Technology — Next.js App Router + TypeScript + Tailwind CSS
- **Context:** A modern, accessible, dark-themed AI workspace interface is needed with SEO-ready landing pages and streaming chat capabilities.
- **Decision:** Next.js 14+ App Router with TypeScript, Tailwind CSS, and shadcn/ui.
- **Consequences:** Fast server rendering for public marketing pages, responsive client components for interactive graph and streaming chat, type-safe API communication.

---

## ADR-007: Object Storage — S3-Compatible Storage Adapter
- **Context:** Web applications running on Render possess ephemeral filesystems. File uploads cannot be saved to the local disk in production.
- **Decision:** Implement an S3-compatible storage adapter with presigned upload/download URLs (compatible with AWS S3, Cloudflare R2, MinIO, or local disk fallback for tests).
- **Consequences:** Zero risk of data loss on container restarts; direct client uploads reduce load on API servers.
