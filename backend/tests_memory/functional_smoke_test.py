#!/usr/bin/env python3
"""Functional smoke test for the memory_layer feature in Open WebUI.

This script imports the full FastAPI app from open_webui.main, mocks network
calls, and hits the memory_layer endpoints via httpx.AsyncClient + ASGITransport
without launching uvicorn.
"""

import asyncio
import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

# ── Environment hardening (set BEFORE any imports) ────────────────────────────
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ENABLE_BASE_MODELS_CACHE", "false")
os.environ.setdefault("ENABLE_OLLAMA_API", "false")
os.environ.setdefault("ENABLE_OPENAI_API", "false")
os.environ.setdefault("OFFLINE_MODE", "true")
os.environ.setdefault("WEBUI_ADMIN_EMAIL", "")
os.environ.setdefault("WEBUI_ADMIN_PASSWORD", "")
os.environ.setdefault("LICENSE_KEY", "")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("TOOL_SERVER_CONNECTIONS", "[]")
os.environ.setdefault("TERMINAL_SERVER_CONNECTIONS", "[]")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Use a temporary SQLite DB so we don't pollute data/webui.db
_TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TEST_DB_FD)
# Use a file-based DB (not :memory:) because get_async_db() opens new connections
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Reduce import-time noise
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger("smoke_test")

# ── Delayed imports (engine / tables created after DATABASE_URL is set) ───────
try:
    log.info("Importing open_webui.main …")
    import open_webui.main as main_module
    from open_webui.main import app
    from open_webui.internal.db import Base, engine
    from open_webui.utils.auth import get_verified_user
    from open_webui.models.users import UserModel
except Exception as exc:
    print("CRITICAL: Failed to import open_webui.main")
    print(traceback.format_exc())
    sys.exit(1)

# ── Build remaining tables (memory_layer models are registered in Base.metadata
#    because open_webui.main imported the routers which imported the models) ──
try:
    log.info("Creating SQLAlchemy tables …")
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    print("CRITICAL: Base.metadata.create_all failed")
    print(traceback.format_exc())
    sys.exit(1)

# ── Mock auth ─────────────────────────────────────────────────────────────────
mock_user = UserModel(
    id="smoke-test-user",
    email="smoke@test.com",
    name="Smoke Test",
    role="user",
    last_active_at=0,
    updated_at=0,
    created_at=0,
)
app.dependency_overrides[get_verified_user] = lambda: mock_user

# ── Mock Ollama embedding to avoid any network call ──────────────────────────
import open_webui.memory_layer.embeddings.ollama_embed as _ollama_embed  # noqa: E402


async def _mock_embed_text(text: str) -> list[float]:
    return [0.1] * 384


async def _mock_embed_texts(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 384 for _ in texts]


_ollama_embed.embed_text = _mock_embed_text
_ollama_embed.embed_texts = _mock_embed_texts

# ── Mock ChromaDB add/delete so we never need a real embedding service ─────────
import open_webui.memory_layer.retrieval.chroma_client as _chroma_client  # noqa: E402

_chroma_client.add_memory = lambda emb, content, meta, cid=None: cid or "chroma-smoke-123"
_chroma_client.delete_memory = lambda cid: None

# ── Test runner ───────────────────────────────────────────────────────────────
async def run_checks() -> list[tuple[str, bool, str | None]]:
    results: list[tuple[str, bool, str | None]] = []

    # 1. App imported successfully
    results.append(("Import main FastAPI app", True, f"{app.title}"))

    # 2. memory_filter exists
    try:
        assert hasattr(main_module, "_memory_filter"), "_memory_filter missing"
        mf = main_module._memory_filter
        results.append(
            ("memory_filter accessible", True, f"type={type(mf).__name__}")
        )
    except Exception as exc:
        results.append(("memory_filter accessible", False, str(exc)))

    # 3. ChromaDB collection check
    try:
        from open_webui.memory_layer.retrieval import chroma_client  # noqa: E402

        collection = chroma_client.get_memory_collection()
        results.append(
            ("ChromaDB collection exists", True, f"name={collection.name}")
        )
    except Exception as exc:
        results.append(("ChromaDB collection exists", False, str(exc)))

    # 4. Endpoint tests via AsyncClient (lifespan is skipped automatically)
    from httpx import ASGITransport, AsyncClient  # noqa: E402

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    # --- GET /api/mem/health --------------------------------------------------
    try:
        r = await client.get("/api/mem/health")
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert body.get("ok") is True, f"unexpected body: {body}"
        results.append(("GET /api/mem/health", True, None))
    except Exception as exc:
        results.append(("GET /api/mem/health", False, str(exc)))

    # --- GET /api/mem/memory/ -------------------------------------------------
    try:
        r = await client.get("/api/mem/memory/")
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert isinstance(body, list), f"expected list, got {type(body)}"
        results.append(("GET /api/mem/memory/", True, f"count={len(body)}"))
    except Exception as exc:
        results.append(("GET /api/mem/memory/", False, str(exc)))

    # --- POST /api/mem/memory/ ------------------------------------------------
    try:
        payload = {
            "content": "Smoke test memory created by functional smoke test",
            "category": "fact",
            "importance": 0.5,
            "sensitivity": 0.0,
        }
        r = await client.post("/api/mem/memory/", json=payload)
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert body.get("content") == payload["content"]
        assert body.get("user_id") == mock_user.id
        assert body.get("id") is not None
        results.append(("POST /api/mem/memory/", True, f"id={body['id']}"))
    except Exception as exc:
        results.append(("POST /api/mem/memory/", False, str(exc)))

    # --- GET /api/mem/profile/ ------------------------------------------------
    try:
        r = await client.get("/api/mem/profile/")
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert body.get("user_id") == mock_user.id
        results.append(("GET /api/mem/profile/", True, None))
    except Exception as exc:
        results.append(("GET /api/mem/profile/", False, str(exc)))

    # --- GET /api/mem/conflicts/ -----------------------------------------------
    try:
        r = await client.get("/api/mem/conflicts/")
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert isinstance(body, list), f"expected list, got {type(body)}"
        results.append(("GET /api/mem/conflicts/", True, f"count={len(body)}"))
    except Exception as exc:
        results.append(("GET /api/mem/conflicts/", False, str(exc)))

    await client.aclose()
    return results


def print_results(results: list[tuple[str, bool, str | None]]) -> None:
    print("\n" + "=" * 72)
    print(" MEMORY LAYER FUNCTIONAL SMOKE TEST RESULTS")
    print("=" * 72)
    passed = failed = 0
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        line = f"  [{status}] {name}"
        if detail:
            line += f"  ({detail})"
        print(line)
    print("-" * 72)
    print(f"  Summary: {passed} passed, {failed} failed")
    print("=" * 72)
    if failed == 0:
        print("  OVERALL: memory_layer is FUNCTIONALLY OPERATIONAL")
    else:
        print("  OVERALL: memory_layer has FAILURES")
    print("=" * 72)


def main() -> int:
    try:
        results = asyncio.run(run_checks())
    except Exception as exc:
        print("CRITICAL: asyncio.run() raised an unhandled exception")
        print(traceback.format_exc())
        results = []
    finally:
        # Clean up temp database (ignore Windows lock errors)
        try:
            os.remove(TEST_DB_PATH)
        except (FileNotFoundError, PermissionError, OSError):
            pass

    print_results(results)
    return 0 if results and all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
