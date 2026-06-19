"""Unit tests for memory_layer conflicts router."""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure memory_layer tables are registered in Base.metadata before create_all
from open_webui.memory_layer.models.conflict import MemoryConflict  # noqa: F401
from open_webui.memory_layer.routers import conflicts as conflicts_router
from open_webui.memory_layer.schemas.conflict_schemas import MemoryConflictUpdate
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
    app.include_router(conflicts_router.router, prefix="/api/mem/conflicts")
    app.dependency_overrides[get_verified_user] = lambda: mock_user
    return app


@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestGetConflicts:
    @pytest.mark.anyio
    async def test_get_conflicts(self, async_client, monkeypatch):
        conflict1 = MemoryConflict(
            id=1,
            user_id="test-user-1",
            memory_a_id=10,
            memory_b_id=20,
            detected_at=1000,
            similarity_score=0.85,
            status="pending",
        )
        conflict2 = MemoryConflict(
            id=2,
            user_id="test-user-1",
            memory_a_id=30,
            memory_b_id=40,
            detected_at=2000,
            similarity_score=0.90,
            status="resolved",
        )

        async def mock_list_conflicts(user_id, status=None, limit=100, offset=0):
            result = [conflict1, conflict2]
            if status:
                result = [c for c in result if c.status == status]
            return result

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.list_conflicts",
            mock_list_conflicts,
        )

        response = await async_client.get("/api/mem/conflicts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_conflicts_filtered_by_status(self, async_client, monkeypatch):
        conflict = MemoryConflict(
            id=1,
            user_id="test-user-1",
            memory_a_id=10,
            memory_b_id=20,
            detected_at=1000,
            similarity_score=0.85,
            status="pending",
        )

        async def mock_list_conflicts(user_id, status=None, limit=100, offset=0):
            result = [conflict]
            if status:
                result = [c for c in result if c.status == status]
            return result

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.list_conflicts",
            mock_list_conflicts,
        )

        response = await async_client.get("/api/mem/conflicts/?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_conflicts_empty(self, async_client, monkeypatch):
        async def mock_list_conflicts(user_id, status=None, limit=100, offset=0):
            return []

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.list_conflicts",
            mock_list_conflicts,
        )

        response = await async_client.get("/api/mem/conflicts/")
        assert response.status_code == 200
        assert response.json() == []


class TestPatchConflict:
    @pytest.mark.anyio
    async def test_patch_conflict(self, async_client, monkeypatch):
        conflict = MemoryConflict(
            id=1,
            user_id="test-user-1",
            memory_a_id=10,
            memory_b_id=20,
            detected_at=1000,
            similarity_score=0.85,
            status="resolved",
            resolution_memory_id=50,
        )

        async def mock_update_conflict_status(
            conflict_id, new_status, resolution_memory_id=None, user_id=None
        ):
            assert conflict_id == 1
            assert new_status == "resolved"
            assert resolution_memory_id == 50
            assert user_id == "test-user-1"
            return conflict

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.update_conflict_status",
            mock_update_conflict_status,
        )

        payload = MemoryConflictUpdate(status="resolved", resolution_memory_id=50).model_dump()
        response = await async_client.patch("/api/mem/conflicts/1", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolution_memory_id"] == 50

    @pytest.mark.anyio
    async def test_patch_conflict_not_found(self, async_client, monkeypatch):
        async def mock_update_conflict_status(
            conflict_id, new_status, resolution_memory_id=None, user_id=None
        ):
            assert user_id == "test-user-1"
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.update_conflict_status",
            mock_update_conflict_status,
        )

        payload = MemoryConflictUpdate(status="resolved").model_dump()
        response = await async_client.patch("/api/mem/conflicts/9999", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Conflict not found"

    @pytest.mark.anyio
    async def test_patch_conflict_without_resolution_id(self, async_client, monkeypatch):
        conflict = MemoryConflict(
            id=2,
            user_id="test-user-1",
            memory_a_id=11,
            memory_b_id=22,
            detected_at=2000,
            similarity_score=0.80,
            status="dismissed",
            resolution_memory_id=None,
        )

        async def mock_update_conflict_status(
            conflict_id, new_status, resolution_memory_id=None, user_id=None
        ):
            assert conflict_id == 2
            assert new_status == "dismissed"
            assert resolution_memory_id is None
            assert user_id == "test-user-1"
            return conflict

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.conflicts.update_conflict_status",
            mock_update_conflict_status,
        )

        payload = MemoryConflictUpdate(status="dismissed").model_dump()
        response = await async_client.patch("/api/mem/conflicts/2", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dismissed"
        assert data["resolution_memory_id"] is None
