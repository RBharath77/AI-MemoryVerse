# AI-MemoryVerse — Testing Strategy & Evaluation Framework

## 1. Testing Pyramid Overview

AI-MemoryVerse employs an automated testing strategy ensuring every core layer is validated before production deployment:

```
           / \
          / E2E \        Playwright / Automated E2E Workflows (12 Scenarios)
         /-------\
        /  Integ  \      FastAPI TestClient + PostgreSQL Integration Tests
       /-----------\
      / AI / RAG Eval\   Groundedness, Citation Accuracy, Precision@K
     /-----------------\
    /     Unit Tests    \ Pytest (Backend services/models) & Vitest (Frontend components)
   /---------------------\
```

---

## 2. 12 Mandatory End-to-End Scenarios

| Scenario | Objective | Validation Check |
|---|---|---|
| **Scenario 1** | Register, log in, create a workspace and add a memory. | User profile created, workspace membership set as Owner, memory saved with status `APPROVED`. |
| **Scenario 2** | Restart the application and verify memory persistence. | Querying the database returns the exact memory with timestamp and metadata intact. |
| **Scenario 3** | Start a new conversation and retrieve a saved fact. | AI chat invokes retrieval and incorporates the saved memory into the prompt. |
| **Scenario 4** | Upload multiple documents and query information across them. | Worker chunks documents; hybrid search retrieves relevant chunks from across both files. |
| **Scenario 5** | Check that answers cite the correct document sources. | Response returns verifiable citation tags matching chunk IDs and page references. |
| **Scenario 6** | Edit a memory and inspect version history. | Old version archived in `memory_versions`; current memory points to updated text. |
| **Scenario 7** | Create a contradictory memory and verify conflict handling. | Conflict detector flags candidate memory with `CONTRADICTION` warning before approval. |
| **Scenario 8** | Explore project relationships in the knowledge graph. | Entities extracted from memories and documents form nodes and edges in `/api/v1/graph`. |
| **Scenario 9** | Verify another user cannot access private information. | User B querying User A's workspace receives HTTP 403 / 404 with zero data leakage. |
| **Scenario 10** | Delete a source and verify dependent data handling. | Deleting a document cascades chunk and embedding deletions cleanly. |
| **Scenario 11** | Process a document through a background worker. | Celery job transitions status from `PENDING` -> `PROCESSING` -> `COMPLETED`. |
| **Scenario 12** | Verify the deployed application and database work together. | Health check endpoint reports database and queue readiness. |

---

## 3. AI Evaluation Metrics
- **Retrieval Precision@K & Recall@K**: Validates whether the top $K$ retrieved chunks contain the ground-truth answers.
- **Answer Groundedness**: Verifies that every assertion made by the LLM is directly supported by retrieved context.
- **Citation Precision**: Ensures every citation tag links to an actually retrieved and relevant chunk.

---

## 4. Automated Pytest Test Suite Matrix (84 Tests, 100% Passing)

### 4.1 Authentication & Workspace Tenancy (`tests/test_auth.py`, `tests/test_workspaces.py`) — 16 Tests
- User registration with unique email constraints & password complexity enforcement.
- Argon2id password hashing and secure verification.
- JWT access token generation and refresh token rotation with fingerprinting.
- Multi-session management and explicit revocation (`/logout`).
- Password reset token generation, expiration, and password update lifecycle.
- Email verification token workflows.
- User profile updates and soft/hard account deletion.
- Workspace creation, role assignment (`owner`, `admin`, `member`), member addition, and cross-workspace data isolation.

### 4.2 Core Memory Engine & Lifecycle (`tests/test_memories.py`, `tests/test_memory_engine.py`) — 12 Tests
- Memory creation, retrieval, filtering by category (`episodic`, `semantic`, `project`, `preference`), and search.
- Sensitive PII & credential guardrail (stripping passwords, API keys, and sensitive tokens).
- Jaccard token overlap duplicate detection ($>0.75$ similarity).
- Contradiction and antonym conflict detection (flags candidates into Review Inbox).
- Review inbox human-in-the-loop workflows (approve, reject, correct).
- Version history tracking and one-click historical restoration (`/restore`).
- Memory consolidation with automatic supersession chaining.
- Temporal validity (`valid_from`, `valid_until`) and chronological timeline filtering.
- Graph links and thumbs up/down user feedback tracking.
- Idempotent JSON/CSV memory bulk import and export.

### 4.3 Document Intelligence Pipeline (`tests/test_document_intelligence.py`) — 8 Tests
- Multi-format document parser (PDF, DOCX, TXT, MD, CSV, JSON, HTML).
- Chunking strategies: fixed-size with token overlap, paragraph chunking, and markdown semantic header-aware chunking.
- Document upload, size validation, and mime-type restriction checks.
- Document status transitions (`pending` -> `processing` -> `completed` / `failed`).
- Failure recovery and task retry mechanism (`/retry`).
- Chunk inspector endpoint (`/chunks`) and secure download presigned URL generator.
- Strict multi-tenant document isolation.

### 4.4 Full RAG & Conversation Engine (`tests/test_rag_and_chat.py`) — 5 Tests
- Vector embedding generation using `pgvector` HNSW index with dual-dialect SQLite testing fallback.
- Hybrid Search fusing BM25 lexical keyword matching and dense vector cosine similarity with Reciprocal Rank Fusion (RRF, $k=60$).
- Multi-signal reranking with pinned memory and importance weighting.
- Budget-aware context assembler generating grounded inline source citations (`[1]`, `[2]`).
- Persistent conversation session lifecycle and automatic conversational titling.
- Server-Sent Events (SSE) token-by-token streaming response endpoint.
- Cross-workspace conversation isolation.

### 4.5 Knowledge Graph Engine (`tests/test_knowledge_graph.py`) — 5 Tests
- Entity & relationship extraction pipeline (`GraphExtractor`) extracting technologies, projects, and people.
- Entity CRUD lifecycle and mention count increments.
- Relationship creation with validation against self-referential loops.
- Ego-network neighborhood retrieval (`/api/v1/graph/neighborhood/{entity_id}`) with depth filtering.
- Full workspace knowledge graph export and degree-based centrality analytics.
- Multi-tenant entity and relationship isolation.

### 4.6 Personal AI & Voice Features (`tests/test_personal_ai.py`) — 6 Tests
- Speech-to-Text audio transcription with file size and format validation.
- Text-to-Speech audio synthesis generating valid PCM WAV byte streams.
- Full-duplex Voice Chat RAG query returning grounded assistant text and base64 audio response.
- Multi-document research report generation (`topic_research`, `daily_digest`, `weekly_summary`).
- Smart Knowledge Insights scanner (stale knowledge detection, contradiction alerts, knowledge gaps, and trending hubs).
- Multi-tenant research report and insight isolation.

### 4.7 Controlled Agents & Integrations (`tests/test_agents_and_integrations.py`) — 7 Tests
- SSRF protection guardrails blocking loopback, AWS metadata, and private RFC 1918 addresses.
- Sanitized HTML web crawler and text cleaner stripping scripts and styles.
- Multi-step autonomous task planning and tool execution.
- Human-in-the-loop approval checkpoint pausing execution on high-consequence tools.
- Human-in-the-loop rejection checkpoint halting tasks and preventing unauthorized modifications.
- SHA-256 hashed API token generation, prefix masking, and permission scope enforcement.
- Cross-tenant agent task and token isolation.

### 4.8 SaaS Billing & System Admin (`tests/test_billing_and_admin.py`) — 9 Tests
- Plan catalog retrieval and quota limit definitions across all 4 tiers (Free, Personal, Pro, Team).
- Real-time resource quota utilization tracking for memories, documents, storage, and AI queries.
- Subscription lifecycle and automated paid invoice generation.
- Sandbox payment checkout session simulator.
- 1-click self-serve plan upgrades and quota expansions.
- Subscription cancellation scheduling at period end.
- System telemetry and live health probes for PostgreSQL, Redis, and Celery workers.
- Compliance and operational audit log stream.
- Cross-tenant subscription and billing isolation.

### 4.9 12 E2E User Journeys & OWASP Security Defenses (`tests/test_e2e_scenarios_and_security.py`) — 14 Tests
- Scenario 1: User registration, private workspace creation, and memory lifecycle.
- Scenario 2: Memory state persistence verification across application reloads.
- Scenario 3: Cross-session conversation context with grounded memory retrieval.
- Scenario 4 & 5: Multi-document upload, parsing, chunking, and grounded inline citations.
- Scenario 6: Memory editing, immutable revision history, and one-click rollback.
- Scenario 7: Contradiction and semantic conflict detection with review inbox triage.
- Scenario 8: Knowledge graph entity extraction and relationship graph exploration.
- Scenario 9: Multi-tenant zero-data-leakage IDOR defense on all read/write operations.
- Scenario 10: Cascade deletion of documents, chunks, and vector index references.
- Scenario 11 & 12: Background worker queue processing, health checks, and database readiness.
- OWASP A03: SQL injection immunity against parameterized queries.
- OWASP A10: Comprehensive SSRF target blocklist validation.
- Sensitive credential leakage guardrail (passwords and API keys blocked from memory extraction).
- OWASP A01: Broken Access Control defense rejecting unauthenticated requests with HTTP 401.

### 4.10 System Health Probes (`tests/test_health.py`) — 2 Tests
- Liveness check (`/health`) confirming process health and API responsiveness.
- Readiness check (`/ready`) verifying database connectivity and connection pool readiness.


