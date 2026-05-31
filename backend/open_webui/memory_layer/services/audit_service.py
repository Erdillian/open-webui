"""Audit service: structured tracing for the memory layer."""
import logging
import time
from typing import Optional

from open_webui.internal.db import get_async_db
from open_webui.memory_layer.models.audit_log import AuditLog

log = logging.getLogger(__name__)


async def trace_event(
    user_id: str,
    event_type: str,
    payload: Optional[dict] = None,
    summary: Optional[str] = None,
    chat_id: Optional[str] = None,
    memory_id: Optional[int] = None,
) -> None:
    """Write a structured audit log entry.

    Event types:
    - inlet_injected : system prompt enriched with memories
    - outlet_enqueued : exchange queued for extraction
    - extraction_created : new memory extracted from chat
    - retrieval_query : vector search performed
    - profile_regen : full profile regenerated
    - profile_patched : incremental profile update
    - conflict_detected : potential conflict found
    - consolidation_created : synthesis memory created
    - onboarding_completed : onboarding answers saved
    - memory_updated : manual memory edit
    - memory_deleted : memory removed
    """
    try:
        async with get_async_db() as db:
            entry = AuditLog(
                timestamp=int(time.time()),
                user_id=user_id,
                event_type=event_type,
                payload=payload or {},
                summary=summary or "",
                chat_id=chat_id,
                memory_id=memory_id,
            )
            db.add(entry)
            await db.commit()
    except Exception as e:
        # Audit logging must never break the main flow
        log.warning(f"Failed to write audit log: {e}")


async def list_audit_logs(
    user_id: str,
    event_type: Optional[str] = None,
    chat_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """List audit logs for a user, newest first."""
    from sqlalchemy import select

    async with get_async_db() as db:
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if chat_id:
            stmt = stmt.where(AuditLog.chat_id == chat_id)
        stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())
