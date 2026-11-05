import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.graph import router as graph_router
from app.api.v1.health import router as health_router
from app.api.v1.memories import router as memories_router
from app.api.v1.memory_reviews import router as memory_reviews_router
from app.api.v1.research import router as research_router
from app.api.v1.search import router as search_router
from app.api.v1.users import router as users_router
from app.api.v1.voice import router as voice_router
from app.api.v1.workspaces import router as workspaces_router
from app.core.config import settings
from app.core.database import Base, async_engine
from app.schemas.common import APIResponse, ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: attempt database table initialization gracefully
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Database connection deferred on startup: {e}")
    yield
    # Shutdown: dispose database connection pool safely
    try:
        await async_engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="Personal AI Memory and Knowledge Intelligence Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID & Latency Middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse(
            success=False,
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            ),
        ).model_dump(),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=APIResponse(
            success=False,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Input validation failed for request payload.",
                details=exc.errors(),
            ),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=APIResponse(
            success=False,
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
            ),
        ).model_dump(),
    )


# System Health Endpoints
app.include_router(health_router)

# API v1 Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(memories_router, prefix="/api/v1")
app.include_router(memory_reviews_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "tagline": "Remember. Connect. Understand. Retrieve.",
        "version": "1.0.0",
        "docs": "/docs",
        "api_v1": "/api/v1",
    }
