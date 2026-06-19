#!/usr/bin/env python3
"""
Seed Open WebUI memory_layer with any extracted profile + memories JSON.

Usage:
    cd backend
    .venv\Scripts\python ..\seed_import_memory.py [<user_id>] <path_to_profile.json>

If user_id is omitted, a default admin user is created if it does not exist.

This script:
1. Ensures DB schema exists.
2. Creates a user if it does not exist (when no user_id is provided).
3. Inserts/updates the executive profile.
4. Inserts memories into SQLite + ChromaDB with embeddings.
5. Marks onboarding as done.
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from open_webui.internal.db import Base, engine, get_async_db
# Import native models first to register their tables in Base.metadata
from open_webui.models.chats import Chat
from open_webui.models.users import User
from open_webui.models.auths import Auth, Auths
from open_webui.utils.auth import get_password_hash
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.models.profile import UserProfile
from open_webui.memory_layer.retrieval.chroma_client import add_memory
from open_webui.memory_layer.embeddings.ollama_embed import embed_text


import os

USER_EMAIL = os.getenv("SEED_USER_EMAIL", "admin@local.dev")
USER_PASSWORD = os.getenv("SEED_USER_PASSWORD", "admin123")
USER_NAME = os.getenv("SEED_USER_NAME", "Admin")
USER_ROLE = os.getenv("SEED_USER_ROLE", "admin")


def parse_date(date_str: str | None) -> int | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return int(dt.timestamp())
        except Exception:
            continue
    return None


async def ensure_user(user_id: str | None) -> str:
    """Return a valid user_id, creating an admin user if necessary."""
    # Ensure schema exists using the synchronous engine
    Base.metadata.create_all(engine)

    if user_id:
        async with get_async_db() as db:
            user = await db.get(User, user_id)
            if user:
                print(f"Using existing user_id: {user_id}")
                return user_id
            else:
                print(f"Warning: user_id {user_id} not found, will create it.")

    async with get_async_db() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == USER_EMAIL))
        existing = result.scalars().first()
        if existing:
            print(f"Found existing user {existing.id} with email {USER_EMAIL}")
            return existing.id

    print(f"Creating new admin user: {USER_EMAIL}")
    hashed = get_password_hash(USER_PASSWORD)
    user = await Auths.insert_new_auth(
        email=USER_EMAIL,
        password=hashed,
        name=USER_NAME,
        role=USER_ROLE,
    )
    if not user:
        raise RuntimeError("Failed to create admin user")
    print(f"Created user_id: {user.id}")
    return user.id


async def seed_profile(user_id: str, data: dict):
    """Insert or update the user profile."""
    async with get_async_db() as db:
        existing = await db.get(UserProfile, user_id)
        if existing:
            print(f"Profile already exists for {user_id}, updating.")
            existing.executive_summary = data["executive_summary"]
            existing.full_profile_json = data["profile_json"]
            existing.last_updated = int(time.time() * 1000)
            existing.memories_since_regen = len(data.get("memories", []))
        else:
            profile = UserProfile(
                user_id=user_id,
                executive_summary=data["executive_summary"],
                full_profile_json=data["profile_json"],
                last_updated=int(time.time() * 1000),
                last_full_regen=int(time.time() * 1000),
                memories_since_regen=len(data.get("memories", [])),
                onboarding_done=True,
            )
            db.add(profile)

        await db.commit()
        print("Profile seeded.")


async def seed_memories(user_id: str, memories: list[dict]):
    """Insert memories into SQLite + ChromaDB."""
    success = 0
    skipped = 0
    for mem in memories:
        content = mem["content"]
        try:
            embedding = await embed_text(content)
        except Exception as e:
            print(f"Embedding failed for '{content[:40]}...': {e}")
            skipped += 1
            continue

        async with get_async_db() as db:
            timestamp_event = parse_date(mem.get("date"))
            timestamp_created = int(time.time())
            item = MemoryItem(
                user_id=user_id,
                content=content,
                category=mem.get("category", "fact"),
                importance=float(mem.get("importance", 0.5)),
                sensitivity=float(mem.get("sensitivity", 0.0)),
                timestamp_event=timestamp_event,
                timestamp_created=timestamp_created,
            )
            db.add(item)
            await db.commit()
            await db.refresh(item)

            metadata = {
                "user_id": user_id,
                "category": item.category,
                "importance": item.importance,
                "sensitivity": item.sensitivity,
                "pinned": item.pinned,
                "archived": item.archived,
                "timestamp_event": str(timestamp_event) if timestamp_event else "",
            }
            chroma_id = add_memory(embedding=embedding, content=content, metadata=metadata)

            item.chroma_id = chroma_id
            await db.commit()
            success += 1
            print(f"  [{success}] {content[:80]}...")

    print(f"\nSeeded {success} memories, skipped {skipped}.")


async def main():
    if len(sys.argv) < 2:
        print("Usage: seed_import_memory.py [<user_id>] <path_to_profile.json>")
        print("If user_id is omitted, a default admin user is created if needed.")
        sys.exit(1)

    # Distinguish user_id from file path: if last arg is a file, treat first arg as user_id only if two args provided
    if len(sys.argv) == 2:
        user_id = None
        data_file = Path(sys.argv[1])
    else:
        user_id = sys.argv[1]
        data_file = Path(sys.argv[2])

    if not data_file.exists():
        print(f"File not found: {data_file}")
        sys.exit(1)

    print(f"Loading {data_file}...")
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate expected structure
    for key in ("executive_summary", "profile_json", "memories"):
        if key not in data:
            print(f"Missing key in input JSON: {key}")
            sys.exit(1)

    user_id = await ensure_user(user_id)
    print(f"Using user_id: {user_id}")
    await seed_profile(user_id, data)
    await seed_memories(user_id, data.get("memories", []))

    print("\n✅ Seeding complete.")
    print(f"Memories: {len(data.get('memories', []))}")


if __name__ == "__main__":
    asyncio.run(main())
