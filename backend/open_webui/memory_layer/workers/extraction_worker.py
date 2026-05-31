"""Async worker that processes the memory extraction queue."""
import asyncio
import logging

from open_webui.memory_layer.services.extractor import extract_memories_from_exchange
from open_webui.memory_layer.workers.extraction_queue import dequeue

log = logging.getLogger(__name__)

# Worker control flag
_running = False


async def extraction_worker_loop() -> None:
    """Main loop for the extraction worker.

    Continuously dequeues extraction tasks and processes them.
    """
    global _running
    _running = True
    log.info("Memory extraction worker started.")

    while _running:
        try:
            task = await dequeue(timeout=5.0)
            if task is None:
                # No task available, continue polling
                await asyncio.sleep(0.5)
                continue

            user_id = task.get("user_id", "")
            messages = task.get("messages", [])
            chat_id = task.get("chat_id")

            if not user_id or not messages:
                continue

            log.debug(f"Processing extraction task for user {user_id}")
            created_ids = await extract_memories_from_exchange(
                user_id=user_id,
                messages=messages,
                chat_id=chat_id,
            )
            if created_ids:
                log.info(f"Extracted {len(created_ids)} memories for user {user_id}")

        except asyncio.CancelledError:
            log.info("Memory extraction worker cancelled.")
            break
        except Exception as e:
            log.error(f"Extraction worker error: {e}")
            await asyncio.sleep(1.0)

    _running = False
    log.info("Memory extraction worker stopped.")


def stop_worker() -> None:
    """Signal the worker to stop."""
    global _running
    _running = False
