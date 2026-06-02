"""Unit tests for memory_layer profile router."""
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure memory_layer tables are registered in Base.metadata before create_all
from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory  # noqa: F401
from open_webui.memory_layer.routers import profile as profile_router
from open_webui.memory_layer.schemas.profile_schemas import UserProfileUpdate
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
    app.include_router(profile_router.router, prefix="/api/mem/profile")
    app.dependency_overrides[get_verified_user] = lambda: mock_user
    return app


@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestGetUserProfile:
    @pytest.mark.anyio
    async def test_get_user_profile(self, async_client, monkeypatch):
        profile = UserProfile(
            user_id="test-user-1",
            executive_summary="Test summary",
            full_profile_json={"name": "Test"},
            last_updated=1234567890,
            onboarding_done=True,
            memories_since_regen=0,
        )

        async def mock_get_or_create_profile(user_id):
            return profile

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.get_or_create_profile",
            mock_get_or_create_profile,
        )

        response = await async_client.get("/api/mem/profile/")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-1"
        assert data["executive_summary"] == "Test summary"
        assert data["onboarding_done"] is True

    @pytest.mark.anyio
    async def test_get_user_profile_legacy_none_onboarding(self, async_client, monkeypatch):
        profile = UserProfile(
            user_id="test-user-1",
            executive_summary="Test summary",
            full_profile_json={},
            last_updated=1234567890,
            onboarding_done=None,
            memories_since_regen=0,
        )

        async def mock_get_or_create_profile(user_id):
            return profile

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.get_or_create_profile",
            mock_get_or_create_profile,
        )

        response = await async_client.get("/api/mem/profile/")
        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_done"] is False


class TestPatchUserProfile:
    @pytest.mark.anyio
    async def test_patch_user_profile(self, async_client, monkeypatch):
        updated_profile = UserProfile(
            user_id="test-user-1",
            executive_summary="Updated summary",
            full_profile_json={"updated": True},
            last_updated=1234567890,
            onboarding_done=False,
            memories_since_regen=0,
        )

        async def mock_snapshot_profile_history(user_id, trigger):
            return None

        async def mock_update_profile(user_id, executive_summary=None, full_profile_json=None):
            return updated_profile

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.snapshot_profile_history",
            mock_snapshot_profile_history,
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.update_profile",
            mock_update_profile,
        )

        payload = UserProfileUpdate(
            executive_summary="Updated summary", full_profile_json={"updated": True}
        ).model_dump()
        response = await async_client.patch("/api/mem/profile/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["executive_summary"] == "Updated summary"
        assert data["full_profile_json"] == {"updated": True}

    @pytest.mark.anyio
    async def test_patch_user_profile_not_found(self, async_client, monkeypatch):
        async def mock_snapshot_profile_history(user_id, trigger):
            return None

        async def mock_update_profile(user_id, executive_summary=None, full_profile_json=None):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.snapshot_profile_history",
            mock_snapshot_profile_history,
        )
        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile.update_profile",
            mock_update_profile,
        )

        payload = UserProfileUpdate(executive_summary="Updated summary").model_dump()
        response = await async_client.patch("/api/mem/profile/", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Profile not found"


class TestRegenerateProfile:
    @pytest.mark.anyio
    async def test_regenerate_profile(self, async_client, monkeypatch):
        async def mock_do_full_regen(user_id):
            return None

        monkeypatch.setattr(
            "open_webui.memory_layer.routers.profile._do_full_regen",
            mock_do_full_regen,
        )

        response = await async_client.post("/api/mem/profile/regenerate")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "message": "Profile regeneration started"}


class TestGetProfileHistory:
    @pytest.mark.anyio
    async def test_get_profile_history(self, db_session, async_client, monkeypatch):
        @asynccontextmanager
        async def mock_get_async_db():
            yield db_session

        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)

        history1 = UserProfileHistory(
            user_id="test-user-1",
            executive_summary="Old summary",
            full_profile_json={"version": 1},
            created_at=1000,
            trigger="manual",
        )
        history2 = UserProfileHistory(
            user_id="test-user-1",
            executive_summary="Newer summary",
            full_profile_json={"version": 2},
            created_at=2000,
            trigger="auto",
        )
        history3 = UserProfileHistory(
            user_id="other-user",
            executive_summary="Other summary",
            full_profile_json={"version": 1},
            created_at=1500,
            trigger="manual",
        )
        db_session.add_all([history1, history2, history3])
        await db_session.commit()

        response = await async_client.get("/api/mem/profile/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["created_at"] == 2000
        assert data[1]["created_at"] == 1000
        assert data[0]["trigger"] == "auto"

    @pytest.mark.anyio
    async def test_get_profile_history_empty(self, db_session, async_client, monkeypatch):
        @asynccontextmanager
        async def mock_get_async_db():
            yield db_session

        monkeypatch.setattr("open_webui.internal.db.get_async_db", mock_get_async_db)

        response = await async_client.get("/api/mem/profile/history")
        assert response.status_code == 200
        assert response.json() == []
