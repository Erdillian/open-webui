"""Common pytest fixtures for memory layer tests."""
import asyncio
import hashlib
import json
import os
import pytest
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Ensure backend is on path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from open_webui.internal.db import Base

# Ensure native tables are registered in Base.metadata before create_all
from open_webui.models.chats import Chat  # noqa: F401
from open_webui.models.users import User  # noqa: F401


@pytest.fixture(scope="session")
def event_loop():
    """Create a fresh event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def _shared_test_db_path():
    """Create a temporary DB file that persists across the test session.

    Using a file-based SQLite allows get_async_db() (which creates its own
    connections) to see the same data as the test session.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@pytest.fixture
async def db_session(_shared_test_db_path):
    """Yield an async SQLAlchemy session backed by a file-based SQLite DB.

    Tables are created from the existing Base metadata (includes native Open WebUI
    tables + memory_layer tables).
    """
    url = f"sqlite+aiosqlite:///{_shared_test_db_path}"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, autocommit=False, autoflush=False
    )
    async with AsyncSessionLocal() as db:
        yield db
    await engine.dispose()


@pytest.fixture
def mock_embedding():
    """Return a deterministic 384-dim embedding based on text hash.

    Mimics nomic-embed-text dimensions (384) for consistency.
    """
    def _embed(text: str) -> list[float]:
        vec = [0.0] * 384
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        for i, byte in enumerate(digest):
            vec[i % 384] = (byte / 255.0) * 2 - 1
        # Normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec
    return _embed


@pytest.fixture
def mock_embeddings():
    """Return a batch version of mock_embedding."""
    def _embed(texts: list[str]) -> list[list[float]]:
        vec = [0.0] * 384
        results = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            for i, byte in enumerate(digest):
                vec[i % 384] = (byte / 255.0) * 2 - 1
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            results.append(vec[:])
        return results
    return _embed


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def user_facts(fixtures_dir: Path) -> dict[str, Any]:
    """Load user_facts.json fixture."""
    path = fixtures_dir / "user_facts.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_scenarios(fixtures_dir: Path) -> dict[str, Any]:
    """Load test_scenarios.json fixture."""
    path = fixtures_dir / "test_scenarios.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def patch_env():
    """Set safe environment defaults for tests."""
    old = os.environ.get("OLLAMA_BASE_URL")
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    yield
    if old is None:
        os.environ.pop("OLLAMA_BASE_URL", None)
    else:
        os.environ["OLLAMA_BASE_URL"] = old
