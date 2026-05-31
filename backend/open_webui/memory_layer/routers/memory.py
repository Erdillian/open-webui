"""Memory item CRUD and operations router."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.schemas.memory_schemas import (
    MemoryItemCreate,
    MemoryItemResponse,
    MemoryItemUpdate,
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
            metadata=data.metadata,
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
    """Edit a memory item."""
    from open_webui.internal.db import get_async_db

    async with get_async_db() as db:
        item = await db.get(MemoryItem, memory_id)
        if not item or item.user_id != user.id:
            raise HTTPException(status_code=404, detail="Memory not found")

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
        if data.metadata is not None:
            item.metadata = data.metadata

        await db.commit()
        await db.refresh(item)
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

        # Delete from ChromaDB
        if item.chroma_id:
            try:
                delete_memory(item.chroma_id)
            except Exception as e:
                log.warning(f"Failed to delete memory from ChromaDB: {e}")

        await db.delete(item)
        await db.commit()
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
