# AI-MemoryVerse — Security Architecture & Threat Model

## 1. Security Philosophy & Principles
AI-MemoryVerse is built on zero-trust principles:
- **Tenant Isolation**: No user or workspace may ever query, retrieve, or mutate another tenant's records.
- **Untrusted Ingestion**: All user-uploaded documents, transcripts, notes, and external URLs are considered untrusted data and potential attack vectors.
- **Least Privilege**: The AI engine and background workers operate with strictly bounded permissions. Unrestricted OS execution, shell invocation, or raw database manipulation is strictly forbidden.

---

## 2. Threat Model Analysis (STRIDE)

| Threat Category | Potential Attack Vector | Implemented Mitigation |
|---|---|---|
| **Spoofing** | Forged JWT access tokens, session hijacking. | Argon2id password hashing, cryptographically random JWT signing keys, short-lived access tokens (15m), refresh tokens stored as HttpOnly/SameSite/Secure cookies, session revocation tracking in PostgreSQL. |
| **Tampering** | Parameter manipulation to alter memory history or falsify citations. | Immutable `memory_versions` audit log, cryptographically generated citation verification hashes, server-side validation using Pydantic. |
| **Repudiation** | User performing destructive action without audit trail. | Centralized `audit_logs` recording action, entity ID, actor user ID, client IP, and timestamp. |
| **Information Disclosure** | Cross-tenant document retrieval via vector similarity; prompt leakage. | Mandatory `workspace_id` filtering enforced at query construction in SQLAlchemy and pgvector queries; system prompt hardening; redaction of sensitive credentials. |
| **Denial of Service** | Archive decompression bombs, oversized PDF uploads, vector search flooding. | Strict file-size caps (max 25MB), file decompression ratio validation, rate limiting per IP and user account via Redis token bucket. |
| **Elevation of Privilege** | Normal user elevating to workspace Owner or System Admin. | Role-Based Access Control (RBAC) middleware verifying workspace membership roles (`Owner`, `Admin`, `Member`, `Viewer`). |

---

## 3. Defense Implementations

### 3.1 Prompt Injection Defense
- System prompts are clearly demarcated using boundary tags (e.g. `<system_context>`, `<user_input>`, `<retrieved_document_chunk>`).
- Instructions embedded within uploaded documents are treated purely as passive data; the LLM prompt instructions explicitly stipulate that data within document chunks cannot alter system behavioral rules.

### 3.2 Server-Side Request Forgery (SSRF) Prevention
- URL import services validate target URLs against private/reserved IP blocks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.169.254` Cloud metadata endpoints).
- Only standard HTTP/HTTPS schemes are allowed; DNS resolution is verified prior to request execution.

### 3.3 Storage Security
- Presigned upload and download URLs have short expiration windows (max 15 minutes).
- Sensitive fields in the database (such as integration OAuth tokens) are encrypted at rest using AES-GCM (via `cryptography.fernet`).

