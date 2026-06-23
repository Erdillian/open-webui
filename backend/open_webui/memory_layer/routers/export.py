"""Export / Import router for memory layer."""
import hashlib
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from open_webui.memory_layer.models.conflict import MemoryConflict
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.models.profile import UserProfile, UserProfileHistory
from open_webui.memory_layer.models.tag import MemoryTag, MemoryItemTag
from open_webui.memory_layer.retrieval.chroma_client import add_memory, update_memory
from open_webui.memory_layer.embeddings.ollama_embed import embed_text
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel
from open_webui.internal.db import get_async_db

log = logging.getLogger(__name__)
router = APIRouter()

MAX_IMPORT_BYTES = 10 * 1024 * 1024


# ── Pydantic models for symmetric import/export ───────────────────────────────


class _ImportProfile(BaseModel):
    user_id: str
    executive_summary: str
    full_profile_json: dict
    last_updated: Optional[int] = None
    last_full_regen: Optional[int] = None
    memories_since_regen: int = 0
    onboarding_done: bool = False


class _ImportProfileHistory(BaseModel):
    id: Optional[int] = None
    user_id: str
    executive_summary: str
    full_profile_json: dict
    created_at: Optional[int] = None
    trigger: Optional[str] = None


class _ImportMemoryItem(BaseModel):
    id: Optional[int] = None
    user_id: str
    content: str
    source_message_id: Optional[str] = None
    source_chat_id: Optional[str] = None
    source_document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    timestamp_created: Optional[int] = None
    timestamp_event: Optional[int] = None
    speaker: Optional[str] = None
    category: Optional[str] = None
    importance: float = 0.5
    sensitivity: float = 0.0
    pinned: bool = False
    archived: bool = False
    superseded_by: Optional[int] = None
    related_to: Optional[list] = None
    chroma_id: Optional[str] = None
    meta: Optional[dict] = None


class _ImportConflict(BaseModel):
    id: Optional[int] = None
    user_id: str
    memory_a_id: Optional[int] = None
    memory_b_id: Optional[int] = None
    similarity_score: Optional[float] = None
    status: str = "pending"
    detected_at: Optional[int] = None
    resolution_memory_id: Optional[int] = None
    meta: Optional[dict] = None


class _ImportTag(BaseModel):
    id: Optional[int] = None
    user_id: str
    name: str
    color: Optional[str] = None


class _ImportMemoryItemTag(BaseModel):
    memory_item_id: int
    tag_id: int


class ImportPayload(BaseModel):
    version: Optional[str] = None
    exported_at: Optional[str] = None
    user_id: str
    profile: Optional[_ImportProfile] = None
    profile_history: list[_ImportProfileHistory] = []
    memory_items: list[_ImportMemoryItem] = []
    conflicts: list[_ImportConflict] = []
    tags: list[_ImportTag] = []
    mem_item_tags: list[_ImportMemoryItemTag] = []


# ── Helpers ───────────────────────────────────────────────────────────────────


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload content, raising 413 if it exceeds max_bytes."""
    read = 0
    chunks = []
    chunk = await file.read(65536)
    while chunk:
        read += len(chunk)
        if read > max_bytes:
            raise HTTPException(status_code=413, detail="Import file too large")
        chunks.append(chunk)
        chunk = await file.read(65536)
    return b"".join(chunks)


def _model_to_dict(obj) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ── Export endpoint ─────────────────────────────────────────────────────────


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
            profile_data = _model_to_dict(profile)

        # Profile history
        stmt = select(UserProfileHistory).where(UserProfileHistory.user_id == user.id)
        result = await db.execute(stmt)
        profile_history = [_model_to_dict(h) for h in result.scalars().all()]

        # Memory items
        stmt = select(MemoryItem).where(MemoryItem.user_id == user.id)
        result = await db.execute(stmt)
        memory_items = [_model_to_dict(m) for m in result.scalars().all()]

        # Conflicts (scoped to this user's memories)
        stmt = select(MemoryConflict).where(MemoryConflict.user_id == user.id)
        result = await db.execute(stmt)
        conflicts = [_model_to_dict(c) for c in result.scalars().all()]

        # Tags
        stmt = select(MemoryTag).where(MemoryTag.user_id == user.id)
        result = await db.execute(stmt)
        tags = [_model_to_dict(t) for t in result.scalars().all()]

        # Memory/tag associations for this user's memories
        stmt = (
            select(MemoryItemTag)
            .join(MemoryItem, MemoryItemTag.memory_item_id == MemoryItem.id)
            .where(MemoryItem.user_id == user.id)
        )
        result = await db.execute(stmt)
        mem_item_tags = [
            {"memory_item_id": mt.memory_item_id, "tag_id": mt.tag_id}
            for mt in result.scalars().all()
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
        "mem_item_tags": mem_item_tags,
    }

    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": "attachment; filename=memory_export.json"},
    )


# ── Import endpoint ───────────────────────────────────────────────────────────


@router.post("/import")
async def import_memory(
    request: Request,
    file: UploadFile = File(...),
    user: UserModel = Depends(get_verified_user),
):
    """Import memory layer data from JSON.

    Performs an idempotent merge:
      - profile is upserted by user_id
      - tags are merged by name
      - memory items are merged by id (when owned by the user) or content hash
      - conflicts and memory/tag associations are recreated using the new ids
    """
    try:
        contents = await _read_upload_limited(file, MAX_IMPORT_BYTES)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to read import file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read import file") from e

    try:
        raw = json.loads(contents.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    try:
        payload = ImportPayload.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors()) from e

    if payload.user_id != user.id:
        raise HTTPException(
            status_code=400,
            detail="Export user_id does not match authenticated user",
        )

    try:
        imported = {"memories": 0, "tags": 0, "conflicts": 0, "profile": False}
        skipped = {"memories": 0, "tags": 0, "conflicts": 0}

        async with get_async_db() as db:
            # ── Profile ─────────────────────────────────────────────────────
            if payload.profile:
                profile = await db.get(UserProfile, user.id)
                if profile:
                    profile.executive_summary = payload.profile.executive_summary
                    profile.full_profile_json = payload.profile.full_profile_json
                    profile.last_updated = payload.profile.last_updated or int(time.time())
                    if payload.profile.last_full_regen is not None:
                        profile.last_full_regen = payload.profile.last_full_regen
                    if payload.profile.memories_since_regen is not None:
                        profile.memories_since_regen = payload.profile.memories_since_regen
                    profile.onboarding_done = payload.profile.onboarding_done
                else:
                    profile = UserProfile(
                        user_id=user.id,
                        executive_summary=payload.profile.executive_summary,
                        full_profile_json=payload.profile.full_profile_json,
                        last_updated=payload.profile.last_updated or int(time.time()),
                        last_full_regen=payload.profile.last_full_regen,
                        memories_since_regen=payload.profile.memories_since_regen,
                        onboarding_done=payload.profile.onboarding_done,
                    )
                    db.add(profile)
                await db.flush()
                imported["profile"] = True

            # ── Profile history ─────────────────────────────────────────────
            for hist in payload.profile_history:
                if hist.id:
                    existing = await db.get(UserProfileHistory, hist.id)
                    if existing and existing.user_id == user.id:
                        # Idempotent: keep existing snapshot
                        continue
                new_hist = UserProfileHistory(
                    user_id=user.id,
                    executive_summary=hist.executive_summary,
                    full_profile_json=hist.full_profile_json,
                    created_at=hist.created_at or int(time.time()),
                    trigger=hist.trigger,
                )
                db.add(new_hist)
            await db.flush()

            # ── Tags (merge by name) ─────────────────────────────────────────
            tag_id_map: dict[int, int] = {}
            for tag in payload.tags:
                stmt = select(MemoryTag).where(
                    MemoryTag.user_id == user.id, MemoryTag.name == tag.name
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    tag_id_map[tag.id] = existing.id
                    if tag.color is not None:
                        existing.color = tag.color
                    skipped["tags"] += 1
                else:
                    new_tag = MemoryTag(
                        user_id=user.id,
                        name=tag.name,
                        color=tag.color,
                    )
                    db.add(new_tag)
                    await db.flush()
                    tag_id_map[tag.id] = new_tag.id
                    imported["tags"] += 1

            # ── Memory items (merge by id or content hash) ───────────────────
            memory_id_map: dict[int, int] = {}
            memory_content_hashes: dict[str, MemoryItem] = {}

            # Pre-load existing memories for hash-based dedup
            stmt = select(MemoryItem).where(MemoryItem.user_id == user.id)
            result = await db.execute(stmt)
            existing_memories = result.scalars().all()
            for mem in existing_memories:
                memory_content_hashes[_content_hash(mem.content)] = mem

            for item in payload.memory_items:
                if not item.content:
                    skipped["memories"] += 1
                    continue

                existing = None
                if item.id:
                    existing = await db.get(MemoryItem, item.id)
                    if existing and existing.user_id != user.id:
                        existing = None

                content_hash = _content_hash(item.content)
                if existing is None:
                    existing = memory_content_hashes.get(content_hash)

                now = int(time.time())
                if existing:
                    memory_id_map[item.id] = existing.id
                    existing.content = item.content
                    existing.source_message_id = item.source_message_id
                    existing.source_chat_id = item.source_chat_id
                    existing.source_document_id = item.source_document_id
                    existing.workspace_id = item.workspace_id
                    existing.timestamp_event = item.timestamp_event
                    existing.speaker = item.speaker
                    existing.category = item.category
                    existing.importance = item.importance
                    existing.sensitivity = item.sensitivity
                    existing.pinned = item.pinned
                    existing.archived = item.archived
                    existing.related_to = item.related_to
                    existing.meta = item.meta
                    memory_content_hashes[content_hash] = existing
                    skipped["memories"] += 1
                else:
                    new_mem = MemoryItem(
                        user_id=user.id,
                        content=item.content,
                        source_message_id=item.source_message_id,
                        source_chat_id=item.source_chat_id,
                        source_document_id=item.source_document_id,
                        workspace_id=item.workspace_id,
                        timestamp_created=item.timestamp_created or now,
                        timestamp_event=item.timestamp_event,
                        speaker=item.speaker,
                        category=item.category,
                        importance=item.importance,
                        sensitivity=item.sensitivity,
                        pinned=item.pinned,
                        archived=item.archived,
                        related_to=item.related_to,
                        meta=item.meta,
                    )
                    db.add(new_mem)
                    await db.flush()
                    memory_id_map[item.id] = new_mem.id
                    memory_content_hashes[content_hash] = new_mem
                    imported["memories"] += 1

            await db.flush()

            # ── Memory/tag associations ───────────────────────────────────────
            for mit in payload.mem_item_tags:
                new_mem_id = memory_id_map.get(mit.memory_item_id)
                new_tag_id = tag_id_map.get(mit.tag_id)
                if not new_mem_id or not new_tag_id:
                    continue
                existing_mit = await db.get(MemoryItemTag, (new_mem_id, new_tag_id))
                if not existing_mit:
                    db.add(MemoryItemTag(memory_item_id=new_mem_id, tag_id=new_tag_id))
            await db.flush()

            # ── Conflicts ─────────────────────────────────────────────────────
            seen_conflicts: set[tuple[int, int]] = set()
            for conflict in payload.conflicts:
                memory_a_id = memory_id_map.get(conflict.memory_a_id) if conflict.memory_a_id else None
                memory_b_id = memory_id_map.get(conflict.memory_b_id) if conflict.memory_b_id else None
                if not memory_a_id or not memory_b_id or memory_a_id == memory_b_id:
                    continue

                key = (memory_a_id, memory_b_id)
                if key in seen_conflicts:
                    skipped["conflicts"] += 1
                    continue
                seen_conflicts.add(key)

                stmt = select(MemoryConflict).where(
                    MemoryConflict.user_id == user.id,
                    MemoryConflict.memory_a_id == memory_a_id,
                    MemoryConflict.memory_b_id == memory_b_id,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    existing.similarity_score = conflict.similarity_score
                    existing.status = conflict.status
                    existing.resolution_memory_id = conflict.resolution_memory_id
                    existing.meta = conflict.meta
                    skipped["conflicts"] += 1
                else:
                    db.add(
                        MemoryConflict(
                            user_id=user.id,
                            memory_a_id=memory_a_id,
                            memory_b_id=memory_b_id,
                            similarity_score=conflict.similarity_score,
                            status=conflict.status,
                            detected_at=conflict.detected_at or int(time.time()),
                            resolution_memory_id=conflict.resolution_memory_id,
                            meta=conflict.meta,
                        )
                    )
                    imported["conflicts"] += 1

            await db.commit()

            # ── Re-embed memories into ChromaDB ─────────────────────────────
            for item in payload.memory_items:
                mem_id = memory_id_map.get(item.id)
                if not mem_id:
                    continue
                mem = await db.get(MemoryItem, mem_id)
                if not mem:
                    continue
                try:
                    embedding = await embed_text(mem.content)
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
                    if mem.chroma_id:
                        update_memory(
                            chroma_id=mem.chroma_id,
                            content=mem.content,
                            metadata=chroma_meta,
                            embedding=embedding,
                        )
                    else:
                        chroma_id = str(uuid.uuid4())
                        add_memory(embedding, mem.content, chroma_meta, chroma_id)
                        mem.chroma_id = chroma_id
                        await db.commit()
                except Exception as e:
                    log.warning(f"Failed to embed imported memory {mem_id}: {e}")

        return {
            "ok": True,
            "imported": imported,
            "skipped": skipped,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {e}") from e
