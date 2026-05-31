"""Conflict resolution service."""
import logging
import time
from typing import Optional

from sqlalchemy import select

from open_webui.internal.db import get_async_db
from open_webui.memory_layer.models.conflict import MemoryConflict

log = logging.getLogger(__name__)


async def list_conflicts(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryConflict]:
    """List conflicts for a user, optionally filtered by status."""
    async with get_async_db() as db:
        stmt = select(MemoryConflict).where(MemoryConflict.user_id == user_id)
        if status:
            stmt = stmt.where(MemoryConflict.status == status)
        stmt = stmt.order_by(MemoryConflict.detected_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return result.scalars().all()


async def update_conflict_status(
    conflict_id: int,
    new_status: str,
    resolution_memory_id: Optional[int] = None,
) -> Optional[MemoryConflict]:
    """Update the status of a conflict."""
    async with get_async_db() as db:
        conflict = await db.get(MemoryConflict, conflict_id)
        if not conflict:
            return None
        conflict.status = new_status
        if resolution_memory_id:
            conflict.resolution_memory_id = resolution_memory_id
        await db.commit()
        await db.refresh(conflict)
        return conflict


async def get_pending_conflicts_for_user(user_id: str, limit: int = 3) -> list[dict]:
    """Get pending conflicts formatted for injection into system prompt.

    Returns a list of dicts with memory_a_content, memory_b_content, etc.
    """
    conflicts = await list_conflicts(user_id, status="pending", limit=limit)
    result = []
    for conflict in conflicts:
        # Load associated memories
        from open_webui.memory_layer.models.memory import MemoryItem

        async with get_async_db() as db:
            mem_a = await db.get(MemoryItem, conflict.memory_a_id)
            mem_b = await db.get(MemoryItem, conflict.memory_b_id)

        if mem_a and mem_b:
            result.append(
                {
                    "id": conflict.id,
                    "memory_a_content": mem_a.content,
                    "memory_b_content": mem_b.content,
                    "memory_a_date": _format_date(mem_a.timestamp_created),
                    "memory_b_date": _format_date(mem_b.timestamp_created),
                }
            )

            # Mark as challenged
            conflict.status = "challenged"
            async with get_async_db() as db:
                db.add(conflict)
                await db.commit()
    return result


def _format_date(timestamp: Optional[int]) -> str:
    if not timestamp:
        return "date inconnue"
    now = int(time.time())
    delta = now - timestamp
    if delta < 86400:
        return "aujourd'hui"
    if delta < 172800:
        return "hier"
    if delta < 604800:
        return "cette semaine"
    if delta < 2592000:
        return "ce mois-ci"
    if delta < 31536000:
        return "il y a quelques mois"
    return "il y a plus d'un an"
