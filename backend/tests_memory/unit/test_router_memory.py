"""Unit tests for memory_layer memory router."""
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure memory_layer tables are registered in Base.metadata before create_all
from open_webui.memory_layer.models.memory import MemoryItem  # noqa: F401
from open_webui.memory_layer.routers import memory as memory_router
from open_webui.memory_layer.schemas.memory_schemas import (
    MemoryItemCreate,
    MemoryItemUpdate,
    OnboardingPayload,
    OnboardingAnswer,
)
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
    app.include_router(memory_router.router, prefix="/api/mem/memory")
    app.dependency_overrides[get_verified_user] = lambda: mock_user
    return app


@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_get_async_db(db_session):
    @asynccontextmanager
    async def _mock():
        yield db_session

    return _mock


class TestListMemories:
    @pytest.mark.anyio
    async def test_list_memories_empty(self, async_client, mock_get_async_db, monkeypatch):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        response = await async_client.get("/api/mem/memory/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.anyio
    async def test_list_memories_with_items(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        item1 = MemoryItem(
            user_id="test-user-1",
            content="Hello world",
            category="fact",
            importance=0.5,
            sensitivity=0.0,
            timestamp_created=1000,
        )
        item2 = MemoryItem(
            user_id="test-user-1",
            content="Another memory",
            category="preference",
            importance=0.8,
            sensitivity=0.0,
            timestamp_created=2000,
        )
        item3 = MemoryItem(
            user_id="other-user",
            content="Not mine",
            category="fact",
            importance=0.5,
            sensitivity=0.0,
            timestamp_created=1500,
        )
        db_session.add_all([item1, item2, item3])
        await db_session.commit()

        response = await async_client.get("/api/mem/memory/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["content"] == "Another memory"
        assert data[1]["content"] == "Hello world"

    @pytest.mark.anyio
    async def test_list_memories_filtered_by_category(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        item1 = MemoryItem(
            user_id="test-user-1",
            content="Hello world",
            category="fact",
            importance=0.5,
            sensitivity=0.0,
            timestamp_created=1000,
        )
        item2 = MemoryItem(
            user_id="test-user-1",
            content="Another memory",
            category="preference",
            importance=0.8,
            sensitivity=0.0,
            timestamp_created=2000,
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        response = await async_client.get("/api/mem/memory/?category=fact")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Hello world"

    @pytest.mark.anyio
    async def test_list_memories_excludes_archived(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        item1 = MemoryItem(
            user_id="test-user-1",
            content="Active",
            archived=False,
            importance=0.5,
            sensitivity=0.0,
            timestamp_created=1000,
        )
        item2 = MemoryItem(
            user_id="test-user-1",
            content="Archived",
            archived=True,
            importance=0.5,
            sensitivity=0.0,
            timestamp_created=2000,
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        response = await async_client.get("/api/mem/memory/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Active"

        response = await async_client.get("/api/mem/memory/?include_archived=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestCreateMemory:
    @pytest.mark.anyio
    async def test_create_memory(self, async_client, mock_get_async_db, monkeypatch, db_session):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        monkeypatch.setattr(
            "open_webui.memory_layer.embeddings.ollama_embed.embed_text",
            lambda text: [0.1] * 384,
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.add_memory",
            lambda emb, content, meta, cid: cid or "chroma-123",
        )

        payload = MemoryItemCreate(content="New memory", category="fact", importance=0.7).model_dump()
        response = await async_client.post("/api/mem/memory/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "New memory"
        assert data["category"] == "fact"
        assert data["importance"] == 0.7
        assert data["user_id"] == "test-user-1"
        assert data["id"] is not None


class TestUpdateMemory:
    @pytest.mark.anyio
    async def test_update_memory(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        item = MemoryItem(
            user_id="test-user-1",
            content="Old content",
            importance=0.5,
            sensitivity=0.0,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        payload = MemoryItemUpdate(content="Updated content", importance=0.9).model_dump(
            exclude_unset=True
        )
        response = await async_client.patch(f"/api/mem/memory/{item.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content"
        assert data["importance"] == 0.9

    @pytest.mark.anyio
    async def test_update_memory_not_found(self, async_client, mock_get_async_db, monkeypatch):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        payload = MemoryItemUpdate(content="Updated content").model_dump(exclude_unset=True)
        response = await async_client.patch("/api/mem/memory/9999", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Memory not found"

    @pytest.mark.anyio
    async def test_update_memory_wrong_user(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        item = MemoryItem(
            user_id="other-user",
            content="Not mine",
            importance=0.5,
            sensitivity=0.0,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        payload = MemoryItemUpdate(content="Updated content").model_dump(exclude_unset=True)
        response = await async_client.patch(f"/api/mem/memory/{item.id}", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Memory not found"


class TestDeleteMemory:
    @pytest.mark.anyio
    async def test_delete_memory(
        self, db_session, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.delete_memory", lambda cid: None
        )

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        item = MemoryItem(
            user_id="test-user-1",
            content="Delete me",
            chroma_id="chroma-abc",
            importance=0.5,
            sensitivity=0.0,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = await async_client.delete(f"/api/mem/memory/{item.id}")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @pytest.mark.anyio
    async def test_delete_memory_not_found(self, async_client, mock_get_async_db, monkeypatch):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.delete_memory", lambda cid: None
        )

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        response = await async_client.delete("/api/mem/memory/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Memory not found"


class TestReExtract:
    @pytest.mark.anyio
    async def test_re_extract(self, async_client):
        response = await async_client.post("/api/mem/memory/re-extract", params={"chat_id": "chat-123"})
        assert response.status_code == 200
        assert response.json() == {"ok": True, "message": "Re-extraction queued"}


class TestOnboarding:
    @pytest.mark.anyio
    async def test_onboarding_create_memories(
        self, async_client, mock_get_async_db, monkeypatch
    ):
        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)
        monkeypatch.setattr(
            "open_webui.memory_layer.embeddings.ollama_embed.embed_text",
            lambda text: [0.1] * 384,
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.retrieval.chroma_client.add_memory",
            lambda emb, content, meta, cid: cid or "chroma-123",
        )

        async def mock_do_full_regen(user_id):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.workers.profile_worker._do_full_regen", mock_do_full_regen
        )

        async def mock_trace_event(**kwargs):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.services.audit_service.trace_event", mock_trace_event
        )

        payload = OnboardingPayload(
            answers=[
                OnboardingAnswer(question="What is your name?", answer="Alice", category="identity"),
                OnboardingAnswer(question="What do you like?", answer="Coffee", category="preference"),
            ]
        ).model_dump()

        response = await async_client.post("/api/mem/memory/onboarding", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["created"] == 2
        assert len(data["memory_ids"]) == 2
