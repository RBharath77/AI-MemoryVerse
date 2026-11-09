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

### 3.4 Strict Password Complexity Policy
Account creation and credential updates strictly enforce multi-factor character entropy:
- **Minimum Length**: 8 characters (maximum 128 characters).
- **Uppercase Character**: At least one uppercase English letter (`[A-Z]`).
- **Lowercase Character**: At least one lowercase English letter (`[a-z]`).
- **Numeric Digit**: At least one numeric digit (`[0-9]`).
- **Special Symbol**: At least one punctuation or special symbol (`[!@#$%^&*()_+-=[]{};':"|,.<>/?`~]`).
- **Dual Verification**: Enforced client-side via live interactive checklist UI and server-side via Pydantic v2 `@field_validator` in `RegisterRequest` and `ResetPasswordRequest`.

### 3.5 Enterprise HTTPS Load Balancer & Edge Security Posture
All inbound client traffic is proxied through an edge Nginx load balancing reverse proxy:
- **TLS Termination**: Full TLSv1.2 and TLSv1.3 support with forward-secrecy cipher suites (`ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES128-GCM-SHA256`, etc.).
- **Automatic HTTPS Enforcement**: Catch-all HTTP (port 80) server permanently redirects all plain requests to HTTPS (port 443) with HTTP 301.
- **Load Balancing Algorithm**: Uses `least_conn` to distribute incoming queries to backend instances with the fewest active connections, with automated failover (`max_fails=3 fail_timeout=10s`) and persistent HTTP/1.1 connection keepalive pools (`keepalive 32`).
- **Dual-Tier Rate Limiting**:
  - `api_general`: 30 requests/sec per client IP with a burst cushion of 50.
  - `api_auth`: Dedicated 5 requests/sec zone with a burst cap of 10 on `/api/v1/auth/` to prevent brute-force attacks and credential stuffing.
- **OWASP Defense-in-Depth Headers**:
  - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
  - `X-Frame-Options: SAMEORIGIN` (Clickjacking defense)
  - `X-Content-Type-Options: nosniff` (MIME sniffing defense)
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=*, geolocation=(), payment=()`
  - `Content-Security-Policy: default-src 'self' ...`
- **WAF Rule Shielding**: Drops hidden dotfiles (`.git`, `.env`, `.htaccess`) and probes attempting execution of remote script extensions (`.php`, `.asp`, `.jsp`, `.cgi`).

### 3.6 Model Context Protocol (MCP) Multi-Tenant Security Boundary
- **Mandatory Authentication**: All incoming MCP requests via HTTP (`POST /api/v1/mcp`) enforce active user authentication via `get_current_active_user`.
- **Tenancy Isolation & IDOR Immunity**: Workspace IDs provided via `X-Workspace-ID` headers must correspond to verified `WorkspaceMember` records for the requesting user in PostgreSQL. Unauthorized cross-tenant queries receive HTTP `403 Forbidden`.
- **Demo Backdoor Deactivation**: Sandbox demo logins are disabled by default (`ALLOW_DEMO_LOGIN=False`). When enabled in isolated test environments, credentials map exclusively to ephemeral sandbox accounts.
- **SSRF Redirect Verification**: The web crawler disables automatic redirects, re-running IP and CIDR validation on every intermediate redirection hop (`Location` header) to prevent SSRF bypasses via external 302 redirects.
- **Path Traversal Defense**: File downloads strictly resolve storage keys against canonical base directories, rejecting relative path traversal characters (`../`).



