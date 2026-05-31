"""Export / Import router for memory layer."""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse

from open_webui.memory_layer.models.conflict import MemoryConflict
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory
from open_webui.memory_layer.models.tag import MemoryTag
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel
from open_webui.internal.db import get_async_db
from sqlalchemy import select

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/export")
async def export_memory(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Export the user's memory layer data as JSON."""
    async with get_async_db() as db:
        # Profile
        profile = await db.get(UserProfile, user.id)
        profile_data = None
        if profile:
            profile_data = {
                "user_id": profile.user_id,
                "executive_summary": profile.executive_summary,
                "full_profile_json": profile.full_profile_json,
                "last_updated": profile.last_updated,
                "last_full_regen": profile.last_full_regen,
                "memories_since_regen": profile.memories_since_regen,
            }

        # Profile history
        stmt = select(UserProfileHistory).where(UserProfileHistory.user_id == user.id)
        result = await db.execute(stmt)
        profile_history = [
            {
                "id": h.id,
                "user_id": h.user_id,
                "executive_summary": h.executive_summary,
                "full_profile_json": h.full_profile_json,
                "created_at": h.created_at,
                "trigger": h.trigger,
            }
            for h in result.scalars().all()
        ]

        # Memory items
        stmt = select(MemoryItem).where(MemoryItem.user_id == user.id)
        result = await db.execute(stmt)
        memory_items = [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
                "sensitivity": m.sensitivity,
                "speaker": m.speaker,
                "timestamp_event": m.timestamp_event,
                "timestamp_created": m.timestamp_created,
                "pinned": m.pinned,
                "archived": m.archived,
                "related_to": m.related_to,
                "meta": m.meta,
            }
            for m in result.scalars().all()
        ]

        # Conflicts
        stmt = select(MemoryConflict).where(MemoryConflict.user_id == user.id)
        result = await db.execute(stmt)
        conflicts = [
            {
                "id": c.id,
                "memory_a_id": c.memory_a_id,
                "memory_b_id": c.memory_b_id,
                "similarity_score": c.similarity_score,
                "status": c.status,
                "detected_at": c.detected_at,
            }
            for c in result.scalars().all()
        ]

        # Tags
        stmt = select(MemoryTag).where(MemoryTag.user_id == user.id)
        result = await db.execute(stmt)
        tags = [
            {"id": t.id, "name": t.name, "color": t.color}
            for t in result.scalars().all()
        ]

    export_data = {
        "version": "1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_id": user.id,
        "profile": profile_data,
        "profile_history": profile_history,
        "memory_items": memory_items,
        "conflicts": conflicts,
        "tags": tags,
    }

    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": "attachment; filename=memory_export.json"},
    )


@router.post("/import")
async def import_memory(
    request: Request,
    file: UploadFile = File(...),
    user: UserModel = Depends(get_verified_user),
):
    """Import memory layer data from JSON. Dedup by content hash, re-embed via Ollama."""
    import hashlib

    from open_webui.memory_layer.embeddings.ollama_embed import embed_text
    from open_webui.memory_layer.retrieval.chroma_client import add_memory

    try:
        contents = await file.read()
        data = json.loads(contents.decode("utf-8"))

        imported = 0
        skipped = 0

        async with get_async_db() as db:
            # Import memory items
            for item in data.get("memory_items", []):
                content = item.get("content", "")
                if not content:
                    continue

                # Dedup by content hash
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                stmt = select(MemoryItem).where(MemoryItem.user_id == user.id)
                result = await db.execute(stmt)
                existing = result.scalars().all()
                dup = any(
                    hashlib.sha256(e.content.encode()).hexdigest() == content_hash for e in existing
                )
                if dup:
                    skipped += 1
                    continue

                now = int(time.time())
                mem = MemoryItem(
                    user_id=user.id,
                    content=content,
                    category=item.get("category", "fact"),
                    importance=item.get("importance", 0.5),
                    sensitivity=item.get("sensitivity", 0.0),
                    speaker=item.get("speaker"),
                    timestamp_event=item.get("timestamp_event"),
                    timestamp_created=now,
                    pinned=item.get("pinned", False),
                    archived=item.get("archived", False),
                    related_to=item.get("related_to"),
                    meta=item.get("meta"),
                )
                db.add(mem)
                await db.commit()
                await db.refresh(mem)

                # Re-embed
                try:
                    embedding = await embed_text(content)
                    chroma_id = f"import-{mem.id}"
                    chroma_meta = {
                        "user_id": user.id,
                        "category": mem.category,
                        "importance": mem.importance,
                        "sensitivity": mem.sensitivity,
                        "timestamp_event": mem.timestamp_event if mem.timestamp_event else "",
                        "memory_item_id": mem.id,
                        "pinned": mem.pinned,
                        "archived": mem.archived,
                    }
                    add_memory(embedding, content, chroma_meta, chroma_id)
                    mem.chroma_id = chroma_id
                    await db.commit()
                except Exception as e:
                    log.warning(f"Failed to embed imported memory: {e}")

                imported += 1

        return {"ok": True, "imported": imported, "skipped": skipped}

    except Exception as e:
        log.error(f"Import failed: {e}")
        return {"ok": False, "error": str(e)}
