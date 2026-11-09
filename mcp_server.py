#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""AI-MemoryVerse Model Context Protocol (MCP) Server Entrypoint.

Can be run directly by Claude Desktop, Cursor, Antigravity, or any MCP client:
  python mcp_server.py
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

# If invoked using system python, auto-switch to the project virtualenv if present
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(VENV_PYTHON)):
    if os.environ.get("_MV_MCP_REEXEC") != "1":
        os.environ["_MV_MCP_REEXEC"] = "1"
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# Ensure backend package is in python path
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_env_fallback(file_path: Path) -> None:
    """Pure-Python .env file parser fallback when python-dotenv is not installed."""
    if not file_path.is_file():
        return
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, _, v = stripped.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Load .env file from root or backend
env_root = ROOT_DIR / ".env"
env_backend = BACKEND_DIR / ".env"
try:
    from dotenv import load_dotenv  # type: ignore[missing-import]

    if env_root.exists():
        load_dotenv(env_root)
    elif env_backend.exists():
        load_dotenv(env_backend)
except ImportError:
    if env_root.exists():
        _load_env_fallback(env_root)
    elif env_backend.exists():
        _load_env_fallback(env_backend)

# Normalize SQLite database path to absolute backend path if relative
db_url = os.getenv("DATABASE_URL", "")
if "sqlite" in db_url and "./" in db_url:
    target_db = (BACKEND_DIR / "memoryverse.db").resolve()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{target_db}"

try:
    import app.models  # noqa: F401
    from app.core.database import Base, async_engine  # type: ignore[missing-import]
    from app.mcp.server import MCPServer  # type: ignore[missing-import]
except ImportError:
    import backend.app.models  # noqa: F401
    from backend.app.core.database import Base, async_engine  # type: ignore[missing-import]
    from backend.app.mcp.server import MCPServer  # type: ignore[missing-import]


async def _run() -> None:
    # Ensure tables exist and schema is aligned
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if "sqlite" in async_engine.url.drivername:
                from sqlalchemy import text
                res = await conn.execute(text("PRAGMA table_info(users)"))
                cols = {row[1] for row in res.fetchall()}
                if cols and "token_version" not in cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1"))
                if cols and "password_changed_at" not in cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP"))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            f"[ai-memoryverse] Warning during DB table verification: {e}\n"
        )

    server = MCPServer(
        default_workspace_id=os.getenv("MEMORYVERSE_WORKSPACE_ID"),
        default_user_id=os.getenv("MEMORYVERSE_USER_ID"),
    )
    await server.run_stdio()


def main() -> None:
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write("[ai-memoryverse] MCP server stopped.\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[ai-memoryverse] MCP server fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
