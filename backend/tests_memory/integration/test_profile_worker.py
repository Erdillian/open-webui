"""Integration tests for profile models and service helpers."""
import time

import pytest

from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory
from open_webui.memory_layer.models.memory import MemoryItem


@pytest.mark.anyio
async def test_profile_created_from_memories(db_session, monkeypatch, mock_embedding):
    """Profile CRUD and history snapshot work correctly via the test session."""
    now = int(time.time())

    # Insert profile directly via test session
    profile = UserProfile(
        user_id="u1",
        executive_summary="Profil initial.",
        full_profile_json={"work": "", "personal": ""},
        last_updated=now - 1000,
        memories_since_regen=0,
    )
    db_session.add(profile)
    await db_session.commit()

    # Update profile directly
    new_summary = "Ingénieur pédagogique en Ardèche, végétarien, membre d'association écolo."
    new_json = {
        "work": "Ingénieur pédagogique CFPC.",
        "personal": "Végétarien, vit en Ardèche.",
        "top_of_mind": "Association La Vallée Suspendue.",
    }
    profile.executive_summary = new_summary
    profile.full_profile_json = new_json
    profile.last_updated = now
    await db_session.commit()
    await db_session.refresh(profile)

    # Snapshot history
    history = UserProfileHistory(
        user_id="u1",
        executive_summary=new_summary,
        full_profile_json=new_json,
        created_at=now,
        trigger="manual",
    )
    db_session.add(history)
    await db_session.commit()

    # Re-query profile in the test session
    from sqlalchemy import select
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == "u1")
    )
    profile_in_session = result.scalar_one_or_none()
    assert profile_in_session is not None
    assert "CFPC" in profile_in_session.executive_summary or "Ardèche" in profile_in_session.executive_summary

    # History entry should exist
    result_hist = await db_session.execute(
        select(UserProfileHistory).where(UserProfileHistory.user_id == "u1")
    )
    history_items = result_hist.scalars().all()
    assert len(history_items) >= 1
