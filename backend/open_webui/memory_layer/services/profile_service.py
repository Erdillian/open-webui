"""User profile service: get, update, snapshot, regenerate."""
import json
import logging
import time
from typing import Optional

from sqlalchemy import select

from open_webui.internal.db import get_async_db
from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory

log = logging.getLogger(__name__)


async def get_profile(user_id: str) -> Optional[UserProfile]:
    """Get a user's profile."""
    async with get_async_db() as db:
        return await db.get(UserProfile, user_id)


async def get_or_create_profile(user_id: str) -> UserProfile:
    """Get or create a default profile for a user."""
    profile = await get_profile(user_id)
    if profile:
        return profile

    now = int(time.time())
    profile = UserProfile(
        user_id=user_id,
        executive_summary="Profil non encore généré.",
        full_profile_json={},
        last_updated=now,
        memories_since_regen=0,
    )
    async with get_async_db() as db:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def update_profile(
    user_id: str,
    executive_summary: Optional[str] = None,
    full_profile_json: Optional[dict] = None,
) -> Optional[UserProfile]:
    """Update a user's profile (manual edit)."""
    async with get_async_db() as db:
        profile = await db.get(UserProfile, user_id)
        if not profile:
            return None

        if executive_summary is not None:
            profile.executive_summary = executive_summary
        if full_profile_json is not None:
            profile.full_profile_json = full_profile_json
        profile.last_updated = int(time.time())

        await db.commit()
        await db.refresh(profile)
        return profile


async def snapshot_profile_history(user_id: str, trigger: str = "manual") -> None:
    """Create a history snapshot of the current profile."""
    profile = await get_profile(user_id)
    if not profile:
        return

    now = int(time.time())
    history = UserProfileHistory(
        user_id=user_id,
        executive_summary=profile.executive_summary,
        full_profile_json=profile.full_profile_json,
        created_at=now,
        trigger=trigger,
    )
    async with get_async_db() as db:
        db.add(history)
        await db.commit()


async def increment_memories_since_regen(user_id: str) -> None:
    """Increment the counter of new memories since last full regen."""
    async with get_async_db() as db:
        profile = await db.get(UserProfile, user_id)
        if profile:
            profile.memories_since_regen = (profile.memories_since_regen or 0) + 1
            await db.commit()


async def reset_memories_since_regen(user_id: str) -> None:
    """Reset the counter after a full regen."""
    async with get_async_db() as db:
        profile = await db.get(UserProfile, user_id)
        if profile:
            profile.memories_since_regen = 0
            profile.last_full_regen = int(time.time())
            await db.commit()
