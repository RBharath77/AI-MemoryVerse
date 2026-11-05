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
