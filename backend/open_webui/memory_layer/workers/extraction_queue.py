"""Asyncio queue for memory extraction tasks.

This is a placeholder that will be fully implemented in Phase 4.
For now, it provides the enqueue() API so Phase 3's memory_filter.outlet can import it.
"""
import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Global queue instance
_extraction_queue: Optional[asyncio.Queue] = None


def get_queue() -> asyncio.Queue:
    """Get or create the global extraction queue."""
    global _extraction_queue
    if _extraction_queue is None:
        _extraction_queue = asyncio.Queue()
    return _extraction_queue


async def enqueue(
    user_id: str,
    messages: list[dict],
    chat_id: Optional[str] = None,
) -> None:
    """Enqueue an exchange for memory extraction.

    Args:
        user_id: The user ID.
        messages: The exchange messages (usually [user_msg, assistant_msg]).
        chat_id: Optional chat ID for context.
    """
    queue = get_queue()
    task = {
        "user_id": user_id,
        "messages": messages,
        "chat_id": chat_id,
    }
    await queue.put(task)
    log.debug(f"Enqueued extraction task for user {user_id}, queue size {queue.qsize()}")


async def dequeue(timeout: Optional[float] = None) -> Optional[dict]:
    """Dequeue the next extraction task.

    Args:
        timeout: Max seconds to wait for an item.

    Returns:
        The task dict or None if timed out.
    """
    queue = get_queue()
    try:
        if timeout is not None:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        return await queue.get()
    except asyncio.TimeoutError:
        return None
