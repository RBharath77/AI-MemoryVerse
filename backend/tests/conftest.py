import asyncio
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import app.models  # noqa: F401
from app.core import database as core_db
from app.core.database import Base, get_db
from app.main import app

# Create in-memory SQLite async engine with StaticPool
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

core_db.async_session_factory = TestSessionLocal
core_db.AsyncSessionLocal = TestSessionLocal


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """Create all tables before each test and drop after test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Fixture that registers a test user and returns Authorization headers."""
    register_payload = {
        "email": "testuser@memoryverse.ai",
        "password": "Password123!",
        "full_name": "Test User",
        "workspace_name": "Test Workspace",
    }
    resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    token = data["tokens"]["access_token"]
    workspace_id = data["workspace"]["id"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient):
    """Fixture that registers a superuser and returns Authorization headers."""
    register_payload = {
        "email": "admin@memoryverse.ai",
        "password": "Password123!",
        "full_name": "Super Admin",
        "workspace_name": "Admin Workspace",
    }
    resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    token = data["tokens"]["access_token"]
    workspace_id = data["workspace"]["id"]
    user_id = data["user"]["id"]

    from app.models.user import User

    async with TestSessionLocal() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_superuser = True
            await session.commit()

    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }
