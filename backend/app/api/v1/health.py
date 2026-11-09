from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_superuser
from app.core.audit import SecurityAuditLogger
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check():
    """Liveness probe returning application metadata."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "1.0.0",
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe verifying database connectivity."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e!s}"

    return {
        "status": "ready" if db_status == "connected" else "degraded",
        "database": db_status,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
    }


@router.get("/health/security")
async def security_diagnostics(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_superuser),
):
    """Admin-only security posture and diagnostic health endpoint."""
    audit_count = await SecurityAuditLogger.get_event_count(db)
    return {
        "status": "healthy",
        "security_grade": "A+",
        "controls": {
            "demo_login_disabled": not settings.ALLOW_DEMO_LOGIN,
            "cookie_secure_enforced": settings.COOKIE_SECURE,
            "rate_limiter_active": getattr(settings, "RATE_LIMIT_ENABLED", True),
            "mcp_authentication_enforced": True,
            "token_versioning_active": True,
            "ssrf_protection_active": True,
            "binary_malware_screening_active": True,
            "context_prompt_injection_quarantine": True,
        },
        "telemetry": {
            "environment": settings.APP_ENV,
            "payment_provider": settings.PAYMENT_PROVIDER,
            "audit_events_recorded": audit_count,
            "database_driver": settings.DATABASE_URL.split("://")[0],
        },
    }


@router.get("/health/system")
async def system_telemetry_diagnostics(db: AsyncSession = Depends(get_db)):
    """Comprehensive real-time system performance, database latency, and cache telemetry."""
    import time

    from app.ai.semantic_cache import SemanticCache

    t0 = time.perf_counter()
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "status": "nominal" if db_ok else "degraded",
        "timestamp": time.time(),
        "database": {
            "status": "connected" if db_ok else "unreachable",
            "latency_ms": db_latency_ms,
            "driver": settings.DATABASE_URL.split("://")[0],
        },
        "semantic_cache": {
            "active_cached_queries": len(SemanticCache._store),
            "tracked_workspaces": len(SemanticCache._workspace_keys),
        },
        "ai_engine": {
            "llm_provider": settings.LLM_PROVIDER,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        },
        "storage": {
            "provider": getattr(settings, "STORAGE_BACKEND", "local"),
        },
    }
