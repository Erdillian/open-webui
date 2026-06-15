"""Unit tests for memory_layer export/import router."""
import json
from io import BytesIO

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from open_webui.memory_layer.models.memory import MemoryItem  # noqa: F401
from open_webui.memory_layer.routers import export as export_router
from open_webui.memory_layer.models.profile import UserProfile
from open_webui.memory_layer.models.tag import MemoryTag, MemoryItemTag
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel


@pytest.fixture
def mock_user():
    return UserModel(
        id="test-user-1",
        email="test@example.com",
        name="Test User",
        role="user",
        last_active_at=0,
        updated_at=0,
        created_at=0,
    )


@pytest.fixture
def app(mock_user):
    app = FastAPI()
    app.include_router(export_router.router, prefix="/api/mem/export")
    app.dependency_overrides[get_verified_user] = lambda: mock_user
    return app


@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestExportMemory:
    @pytest.mark.anyio
    async def test_export_memory(
        self, db_session, async_client, monkeypatch
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _mock_db():
            yield db_session

        monkeypatch.setattr("open_webui.internal.db.get_async_db", _mock_db)

        profile = UserProfile(
            user_id="test-user-1",
            executive_summary="Test summary",
            full_profile_json={"key": "value"},
        )
        item = MemoryItem(
            user_id="test-user-1",
            content="Test memory",
            category="fact",
            importance=0.7,
            sensitivity=0.0,
        )
        tag = MemoryTag(user_id="test-user-1", name="test-tag", color="#fff")
        db_session.add_all([profile, item, tag])
        await db_session.commit()
        await db_session.refresh(item)
        await db_session.refresh(tag)
        db_session.add(MemoryItemTag(memory_item_id=item.id, tag_id=tag.id))
        await db_session.commit()

        response = await async_client.get("/api/mem/export/export")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-1"
        assert data["profile"]["executive_summary"] == "Test summary"
        assert len(data["memory_items"]) == 1
        assert data["memory_items"][0]["content"] == "Test memory"
        assert len(data["tags"]) == 1
        assert len(data["mem_item_tags"]) == 1


class TestImportMemory:
    @pytest.mark.anyio
    async def test_import_memory_idempotent(
        self, db_session, async_client, monkeypatch
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _mock_db():
            yield db_session

        monkeypatch.setattr("open_webui.internal.db.get_async_db", _mock_db)
        monkeypatch.setattr(
            "open_webui.memory_layer.embeddings.ollama_embed.embed_text",
            lambda text: [0.1] * 384,
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.add_memory",
            lambda emb, content, meta, cid=None: cid or "chroma-123",
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.update_memory",
            lambda chroma_id, content=None, metadata=None, embedding=None: None,
        )

        payload = {
            "version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "user_id": "test-user-1",
            "profile": {
                "user_id": "test-user-1",
                "executive_summary": "Imported summary",
                "full_profile_json": {"imported": True},
            },
            "memory_items": [
                {
                    "id": 12345,
                    "user_id": "test-user-1",
                    "content": "Imported memory",
                    "category": "fact",
                    "importance": 0.8,
                    "sensitivity": 0.1,
                }
            ],
            "tags": [
                {"id": 999, "user_id": "test-user-1", "name": "imported-tag", "color": "#000"}
            ],
            "mem_item_tags": [],
            "conflicts": [],
        }

        response = await async_client.post(
            "/api/mem/export/import",
            files={"file": ("memory_export.json", BytesIO(json.dumps(payload).encode()), "application/json")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["imported"]["memories"] == 1
        assert data["imported"]["tags"] == 1
        assert data["imported"]["profile"] is True

        # Second import with same payload should merge (skip duplicate by hash)
        response2 = await async_client.post(
            "/api/mem/export/import",
            files={"file": ("memory_export.json", BytesIO(json.dumps(payload).encode()), "application/json")},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["imported"]["memories"] == 0
        assert data2["skipped"]["memories"] == 1

    @pytest.mark.anyio
    async def test_import_wrong_user_id(self, async_client):
        payload = {
            "version": "1.0",
            "user_id": "other-user",
            "memory_items": [],
            "tags": [],
            "mem_item_tags": [],
            "conflicts": [],
        }
        response = await async_client.post(
            "/api/mem/export/import",
            files={"file": ("memory_export.json", BytesIO(json.dumps(payload).encode()), "application/json")},
        )
        assert response.status_code == 400
        assert "user_id" in response.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_import_invalid_json(self, async_client):
        response = await async_client.post(
            "/api/mem/export/import",
            files={"file": ("memory_export.json", BytesIO(b"not json"), "application/json")},
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_import_payload_too_large(self, async_client, monkeypatch):
        from open_webui.memory_layer.routers import export as export_mod

        monkeypatch.setattr(export_mod, "MAX_IMPORT_BYTES", 16)
        payload = {"a": "x" * 100}
        response = await async_client.post(
            "/api/mem/export/import",
            files={"file": ("memory_export.json", BytesIO(json.dumps(payload).encode()), "application/json")},
        )
        assert response.status_code == 413
