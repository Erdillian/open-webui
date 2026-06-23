"""Quick integration test for memory layer models."""
import asyncio
import time

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from open_webui.internal.db import Base
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.models.conflict import MemoryConflict
from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory
from open_webui.memory_layer.models.tag import MemoryTag, MemoryItemTag


@pytest.mark.anyio
async def test_models():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as db:
        now = int(time.time())

        # Insert MemoryItem
        mem = MemoryItem(
            user_id="user_1",
            content="L'utilisateur préfère le café au thé.",
            category="preference",
            importance=0.7,
            timestamp_created=now,
        )
        db.add(mem)
        await db.commit()
        await db.refresh(mem)
        assert mem.id is not None
        print(f"MemoryItem created: id={mem.id}")

        # Insert MemoryConflict
        conflict = MemoryConflict(
            user_id="user_1",
            memory_a_id=mem.id,
            memory_b_id=mem.id,
            similarity_score=0.85,
            status="pending",
            detected_at=now,
        )
        db.add(conflict)
        await db.commit()
        await db.refresh(conflict)
        assert conflict.id is not None
        print(f"MemoryConflict created: id={conflict.id}")

        # Insert UserProfile
        profile = UserProfile(
            user_id="user_1",
            executive_summary="Utilisateur tech, aime le café.",
            full_profile_json={"work": "dev", "personal": "café"},
            last_updated=now,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        assert profile.user_id == "user_1"
        print(f"UserProfile created: user_id={profile.user_id}")

        # Insert UserProfileHistory
        prof_hist = UserProfileHistory(
            user_id="user_1",
            executive_summary="Ancien profil",
            full_profile_json={},
            created_at=now,
            trigger="manual",
        )
        db.add(prof_hist)
        await db.commit()
        await db.refresh(prof_hist)
        assert prof_hist.id is not None
        print(f"UserProfileHistory created: id={prof_hist.id}")

        # Insert MemoryTag
        tag = MemoryTag(user_id="user_1", name="préférences", color="#FF0000")
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        assert tag.id is not None
        print(f"MemoryTag created: id={tag.id}")

        # Insert MemoryItemTag
        item_tag = MemoryItemTag(memory_item_id=mem.id, tag_id=tag.id)
        db.add(item_tag)
        await db.commit()
        print(f"MemoryItemTag created: item={item_tag.memory_item_id}, tag={item_tag.tag_id}")

    await engine.dispose()
    print("All model tests passed!")


if __name__ == "__main__":
    asyncio.run(test_models())
