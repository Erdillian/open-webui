"""Memory item CRUD and operations router."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.schemas.memory_schemas import (
    MemoryItemCreate,
    MemoryItemResponse,
    MemoryItemUpdate,
    OnboardingPayload,
)
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[MemoryItemResponse])
async def list_memories(
    request: Request,
    query: Optional[str] = None,
    category: Optional[str] = None,
    include_archived: bool = False,
    user: UserModel = Depends(get_verified_user),
):
    """List memory items for the current user."""
    from open_webui.internal.db import get_async_db
    from sqlalchemy import select

    async with get_async_db() as db:
        stmt = select(MemoryItem).where(MemoryItem.user_id == user.id)
        if category:
            stmt = stmt.where(MemoryItem.category == category)
        if not include_archived:
            stmt = stmt.where(MemoryItem.archived == False)
        stmt = stmt.order_by(MemoryItem.timestamp_created.desc())
        result = await db.execute(stmt)
        items = result.scalars().all()
        return [MemoryItemResponse.model_validate(i) for i in items]


@router.post("/", response_model=MemoryItemResponse)
async def create_memory(
    request: Request,
    data: MemoryItemCreate,
    user: UserModel = Depends(get_verified_user),
):
    """Manually add a memory item."""
    import time
    import uuid

    from open_webui.internal.db import get_async_db
    from open_webui.memory_layer.embeddings.ollama_embed import embed_text
    from open_webui.memory_layer.retrieval.chroma_client import add_memory

    async with get_async_db() as db:
        now = int(time.time())
        item = MemoryItem(
            user_id=user.id,
            content=data.content,
            source_chat_id=data.source_chat_id,
            timestamp_created=now,
            timestamp_event=data.timestamp_event,
            speaker=data.speaker,
            category=data.category or "fact",
            importance=data.importance,
            sensitivity=data.sensitivity,
            pinned=data.pinned,
            archived=data.archived,
            related_to=data.related_to,
            meta=data.meta,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)

        # Embed and add to ChromaDB
        try:
            embedding = await embed_text(data.content)
            chroma_id = str(uuid.uuid4())
            chroma_meta = {
                "user_id": user.id,
                "category": item.category,
                "importance": item.importance,
                "sensitivity": item.sensitivity,
                "timestamp_event": item.timestamp_event if item.timestamp_event else "",
                "memory_item_id": item.id,
                "pinned": item.pinned,
                "archived": item.archived,
            }
            add_memory(embedding, data.content, chroma_meta, chroma_id)
            item.chroma_id = chroma_id
            await db.commit()
        except Exception as e:
            log.warning(f"Failed to embed new memory: {e}")

        return MemoryItemResponse.model_validate(item)


@router.patch("/{memory_id}", response_model=MemoryItemResponse)
async def update_memory(
    request: Request,
    memory_id: int,
    data: MemoryItemUpdate,
    user: UserModel = Depends(get_verified_user),
):
    """Edit a memory item and keep the ChromaDB copy in sync."""
    from open_webui.internal.db import get_async_db
    from open_webui.memory_layer.retrieval.chroma_client import update_memory as update_chroma_memory
    from open_webui.memory_layer.embeddings.ollama_embed import embed_text

    async with get_async_db() as db:
        item = await db.get(MemoryItem, memory_id)
        if not item or item.user_id != user.id:
            raise HTTPException(status_code=404, detail="Memory not found")

        changed = data.model_dump(exclude_unset=True)
        content_changed = data.content is not None

        if data.content is not None:
            item.content = data.content
        if data.importance is not None:
            item.importance = data.importance
        if data.sensitivity is not None:
            item.sensitivity = data.sensitivity
        if data.pinned is not None:
            item.pinned = data.pinned
        if data.archived is not None:
            item.archived = data.archived
        if data.related_to is not None:
            item.related_to = data.related_to
        if data.meta is not None:
            item.meta = data.meta

        await db.commit()
        await db.refresh(item)

        # Synchronize ChromaDB copy if content or indexed metadata changed
        if item.chroma_id and (content_changed or any(k in changed for k in (
            "importance", "sensitivity", "pinned", "archived", "category", "timestamp_event"
        ))):
            try:
                chroma_meta = {
                    "user_id": user.id,
                    "category": item.category,
                    "importance": item.importance,
                    "sensitivity": item.sensitivity,
                    "timestamp_event": item.timestamp_event if item.timestamp_event else "",
                    "memory_item_id": item.id,
                    "pinned": item.pinned,
                    "archived": item.archived,
                }
                if content_changed:
                    embedding = await embed_text(item.content)
                    update_chroma_memory(
                        chroma_id=item.chroma_id,
                        content=item.content,
                        metadata=chroma_meta,
                        embedding=embedding,
                    )
                else:
                    update_chroma_memory(
                        chroma_id=item.chroma_id,
                        metadata=chroma_meta,
                    )
            except Exception as e:
                log.warning(f"Failed to update memory in ChromaDB: {e}")

        # Trace update
        try:
            from open_webui.memory_layer.services.audit_service import trace_event
            await trace_event(
                user_id=user.id,
                event_type="memory_updated",
                payload={
                    "changes": changed,
                    "content_preview": item.content[:100],
                },
                summary=f"Memory #{memory_id} updated",
                memory_id=memory_id,
            )
        except Exception:
            pass

        return MemoryItemResponse.model_validate(item)


@router.delete("/{memory_id}")
async def delete_memory(
    request: Request,
    memory_id: int,
    user: UserModel = Depends(get_verified_user),
):
    """Delete a memory item."""
    from open_webui.internal.db import get_async_db
    from open_webui.memory_layer.retrieval.chroma_client import delete_memory

    async with get_async_db() as db:
        item = await db.get(MemoryItem, memory_id)
        if not item or item.user_id != user.id:
            raise HTTPException(status_code=404, detail="Memory not found")

        content_preview = item.content[:100]

        # Delete from ChromaDB
        if item.chroma_id:
            try:
                delete_memory(item.chroma_id)
            except Exception as e:
                log.warning(f"Failed to delete memory from ChromaDB: {e}")

        await db.delete(item)
        await db.commit()

        # Trace delete
        try:
            from open_webui.memory_layer.services.audit_service import trace_event
            await trace_event(
                user_id=user.id,
                event_type="memory_deleted",
                payload={"content_preview": content_preview},
                summary=f"Memory #{memory_id} deleted: {content_preview}...",
                memory_id=memory_id,
            )
        except Exception:
            pass

        return {"ok": True}


@router.post("/re-extract")
async def re_extract(
    request: Request,
    chat_id: str,
    user: UserModel = Depends(get_verified_user),
):
    """Re-run extraction on an existing chat."""
    # TODO: Implement re-extraction from chat history
    return {"ok": True, "message": "Re-extraction queued"}


@router.post("/onboarding")
async def onboarding_create_memories(
    request: Request,
    payload: OnboardingPayload,
    user: UserModel = Depends(get_verified_user),
):
    """Create initial memories from onboarding questionnaire answers."""
    import time
    import uuid as uuid_module

    from open_webui.internal.db import get_async_db
    from open_webui.memory_layer.embeddings.ollama_embed import embed_text
    from open_webui.memory_layer.retrieval.chroma_client import add_memory
    from open_webui.memory_layer.models.profile import UserProfile

    created_ids = []
    now = int(time.time())

    async with get_async_db() as db:
        for ans in payload.answers:
            item = MemoryItem(
                user_id=user.id,
                content=ans.answer,
                timestamp_created=now,
                category=ans.category or "fact",
                importance=0.8,
                sensitivity=0.0,
                speaker="user",
                meta={"source": "onboarding", "question": ans.question},
            )
            db.add(item)
            await db.commit()
            await db.refresh(item)
            created_ids.append(item.id)

            try:
                embedding = await embed_text(ans.answer)
                chroma_id = str(uuid_module.uuid4())
                chroma_meta = {
                    "user_id": user.id,
                    "category": item.category,
                    "importance": item.importance,
                    "sensitivity": item.sensitivity,
                    "timestamp_event": now,
                    "memory_item_id": item.id,
                    "pinned": False,
                    "archived": False,
                }
                add_memory(embedding, ans.answer, chroma_meta, chroma_id)
                item.chroma_id = chroma_id
                await db.commit()
            except Exception as e:
                log.warning(f"Failed to embed onboarding memory: {e}")

        # Mark onboarding as done
        profile = await db.get(UserProfile, user.id)
        if profile:
            profile.onboarding_done = True
            profile.last_updated = now
        else:
            profile = UserProfile(
                user_id=user.id,
                executive_summary="",
                full_profile_json={},
                last_updated=now,
                onboarding_done=True,
            )
            db.add(profile)
        await db.commit()

    import asyncio
    from open_webui.memory_layer.workers.profile_worker import _do_full_regen
    asyncio.create_task(_do_full_regen(user.id))

    # Trace onboarding
    try:
        from open_webui.memory_layer.services.audit_service import trace_event
        await trace_event(
            user_id=user.id,
            event_type="onboarding_completed",
            payload={
                "answers_count": len(payload.answers),
                "categories": list({a.category for a in payload.answers}),
                "created_memory_ids": created_ids,
            },
            summary=f"Onboarding completed: {len(payload.answers)} answers saved as memories",
        )
    except Exception:
        pass

    return {"ok": True, "created": len(created_ids), "memory_ids": created_ids}
