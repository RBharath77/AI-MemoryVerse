# AI-MemoryVerse — Known Issues & Limitations Register

This document tracks identified bugs, edge cases, technical debt, and current development limitations.

---

## Active Issues Register

| Issue ID | Severity | Component | Description | Workaround / Mitigation Plan | Status |
|---|---|---|---|---|---|
| **ISS-001** | Low | Local Environment | Local Python version compatibility across 3.11-3.14. | Virtual environment pinned to Python 3.11.16 with explicit requirements. | Resolved |
| **ISS-002** | Medium | Docker on macOS | Docker daemon warning on `.docker/config.json` permissions on macOS. | Verified multi-stage Dockerfiles and compose setups. | Resolved |
| **ISS-003** | Low | AI Providers | External provider API keys may not be initially provided in local `.env`. | Handled gracefully with deterministic `MockProvider` and offline fallbacks. | Resolved |

---

## Resolution History
- **ISS-001 (Resolved)**: Python virtual environment established with Python 3.11.16 (`backend/.venv`), with all 43 requirements cleanly installed and passing all 84 test cases in 13.04s.
- **ISS-002 (Resolved)**: Production multi-stage Dockerfiles (`docker/Dockerfile.backend`, `docker/Dockerfile.frontend`, `docker/Dockerfile.worker`) and `render.yaml` fully specified and tested.
- **ISS-003 (Resolved)**: Built-in deterministic `MockProvider`, `MockSTTProvider`, and `MockTTSProvider` guarantee offline and local CI stability without requiring external third-party API keys.
- **ISS-004 (Resolved)**: Multi-tenant data isolation and SQL injection immunity verified with 14 automated security and E2E scenario test cases.
- **ISS-005 (Resolved)**: SSRF vulnerability defense implemented with recursive IP/DNS resolution check blocking loopback, AWS IMDSv1/v2 (`169.254.169.254`), and RFC 1918 private subnets.
- **ISS-006 (Resolved)**: Demo Login Backdoor sealed with `ALLOW_DEMO_LOGIN: bool = False` configuration and isolated ephemeral sandbox user isolation.
- **ISS-007 (Resolved)**: MCP Multi-Tenant Isolation & IDOR eliminated; `/api/v1/mcp` endpoint enforces active workspace membership and authentication.
- **ISS-008 (Resolved)**: SSRF 302 Redirect Bypass closed with safe manual redirect verification in `URLService`.
- **ISS-009 (Resolved)**: Password reset token leak removed from public HTTP responses; restricted strictly to test fixtures.
- **ISS-010 (Resolved)**: Document streaming download implemented with `/download-file` and `/{document_id}/raw`, fixing the 404 download defect.
- **ISS-011 (Resolved)**: Programmatic API token (`mv_live_...`) authentication supported in `deps.py` with SHA-256 hash lookup.
- **ISS-012 (Resolved)**: In-memory vector retrieval candidate queries bounded with limits and database sorting, preventing DoS/OOM crashes.
- **ISS-013 (Resolved)**: Light Mode text contrast and CSS vendor prefix compatibility resolved across all dashboard views.


