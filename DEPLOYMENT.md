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
After deployment completes, verify:
1. `GET https://<api-url>/health` returns `{"status": "healthy"}`.
2. `GET https://<api-url>/ready` returns `{"database": "connected", "redis": "connected"}`.
3. User registration and login flow works at `https://<web-url>/register`.
4. Create a test memory and verify instant retrieval in the Memory Vault.
5. Upload a document (PDF or Markdown) and confirm worker extracts chunks and creates embeddings.

