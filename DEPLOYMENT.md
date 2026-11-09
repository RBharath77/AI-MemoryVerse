# AI-MemoryVerse — Deployment Guide

This guide details how to run AI-MemoryVerse locally and deploy it to production on **Render** using Render Blueprints (`render.yaml`).

---

## 1. Local Development Setup

### Prerequisites
- Python 3.11+ / 3.14
- Node.js 18+ (Node 20+ recommended)
- PostgreSQL with `pgvector` extension OR Docker

### Option A: Local Native Execution (Optimized for Apple Silicon)
1. **Database & Redis:**
   ```bash
   docker compose up -d postgres redis
   ```
2. **Backend Setup:**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp ../.env.example .env
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```
3. **Background Worker:**
   ```bash
   cd backend
   source .venv/bin/activate
   celery -A app.workers.celery_app worker --loglevel=info
   ```
4. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Access application at `http://localhost:3000`.

### Option B: Full Containerized Stack with HTTPS Load Balancer
Run the complete commercial-grade architecture locally behind an Nginx HTTPS load balancer with TLS termination, rate limiting, and health-checked upstream routing:

1. **Generate Local TLS/SSL Certificates:**
   ```bash
   bash scripts/generate_ssl_certs.sh
   ```
2. **Start All Services with Load Balancer:**
   ```bash
   docker compose up -d --build
   ```
3. **Access via Secure HTTPS:**
   - **HTTPS Web Interface & API:** `https://localhost` (or `https://127.0.0.1`)
   - **HTTP Automatic Redirect:** `http://localhost` (Permanently redirects to `https://localhost`)
   - **API Documentation:** `https://localhost/docs`

---

## 2. Production Deployment on Render

Render deploys the application using a declarative infrastructure specification via `render.yaml`.

### Render Service Architecture

| Service Name | Type | Runtime | Root Dir | Build Command | Start Command |
|---|---|---|---|---|---|
| `memoryverse-web` | Web Service | Node | `frontend` | `npm ci && npm run build` | `npm start` |
| `memoryverse-api` | Web Service | Python | `backend` | `pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `memoryverse-worker` | Background Worker | Python | `backend` | `pip install -r requirements.txt` | `celery -A app.workers.celery_app worker --loglevel=info` |
| `memoryverse-db` | PostgreSQL | Postgres 16 (with pgvector) | - | - | Managed Render Database |
| `memoryverse-queue` | Key Value | Redis-compatible | - | - | Managed Render Key Value |

### Deployment Steps
1. Push source code to a GitHub repository.
2. In the Render Dashboard, select **New -> Blueprint**.
3. Connect your GitHub repository and point to `render.yaml`.
4. Configure required secret environment variables:
   - `SECRET_KEY` (generate with `openssl rand -hex 32`)
   - `LLM_API_KEY` (OpenAI, Gemini, or Anthropic API key)
   - `STORAGE_ACCESS_KEY` & `STORAGE_SECRET_KEY` (S3 or Cloudflare R2 credentials)
5. Trigger initial deployment. Render will automatically provision PostgreSQL, Redis, compile the Next.js app, start FastAPI, run Alembic migrations, and spin up Celery.

---

## 3. Production Verification & Smoke Testing
After deployment completes, run the automated smoke test suite:

```bash
python scripts/smoke_test.py --base-url https://memoryverse-api.onrender.com
```

The script verifies:
1. `GET /health` returns `{"status": "healthy"}`.
2. `GET /ready` returns `{"status": "ready", "database": "connected"}`.
3. User registration and authentication token issuance at `/api/v1/auth/register`.
4. Memory creation, vector embedding, and status approval at `/api/v1/memories`.
5. Hybrid search retrieval engine at `/api/v1/search/hybrid`.
6. Knowledge graph entity & relationship extraction at `/api/v1/graph/extract`.
7. Real-time quota metering and plan checks at `/api/v1/billing/usage`.
8. Controlled agent registered tool suite inspection at `/api/v1/agents/tools`.


