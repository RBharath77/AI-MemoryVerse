# AI-MemoryVerse — Known Issues & Limitations Register

This document tracks identified bugs, edge cases, technical debt, and current development limitations.

---

## Active Issues Register

| Issue ID | Severity | Component | Description | Workaround / Mitigation Plan | Status |
|---|---|---|---|---|---|
| **ISS-001** | Low | Local Environment | Local Python version is 3.14.6; certain compiled C-extensions (like older psutil or legacy wheels) may require source compilation. | Specify modern, compatible dependency versions in `requirements.txt` with wheels supporting Python 3.11-3.14. | Mitigating |
| **ISS-002** | Medium | Docker on macOS | Docker daemon warning on `.docker/config.json` permissions on macOS. | Verified Docker CLI 29.7 is responsive; build steps can run natively or via docker compose. | Documented |
| **ISS-003** | Low | AI Providers | External provider API keys may not be initially provided in local `.env`. | Handled gracefully with `MockProvider` fallback and UI disconnected states. | Designed |

---

## Resolution History
- *No resolved issues yet (Project initialization phase).*
