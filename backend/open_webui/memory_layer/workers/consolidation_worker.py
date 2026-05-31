"""Consolidation worker: weekly job to detect patterns and create synthesis memories."""
import asyncio
import json
import logging
import time
from typing import Optional

from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.embeddings.ollama_embed import embed_text
from open_webui.memory_layer.retrieval.chroma_client import add_memory
from open_webui.internal.db import get_async_db
from sqlalchemy import select

log = logging.getLogger(__name__)

_running = False


async def _call_llm(prompt: str, model: Optional[str] = None, timeout: float = 60.0) -> str:
    """Call Ollama LLM with a prompt."""
    config = get_config()
    if model is None:
        model = config.MEM_EXTRACTOR_MODEL

    import os
    import aiohttp

    url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Consolidation LLM error {resp.status}: {text}")
            data = await resp.json()
            return data.get("response", "")


async def _cluster_memories(user_id: str) -> list[list[MemoryItem]]:
    """Cluster unconsolidated memories by semantic similarity.

    Returns clusters of size >= 3.
    """
    from open_webui.memory_layer.retrieval.chroma_client import query_memories

    async with get_async_db() as db:
        week_ago = int(time.time()) - 7 * 86400
        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id)
            .where(MemoryItem.archived == False)
            .where(MemoryItem.category.in_(["event", "fact", "preference"]))
            .where(MemoryItem.timestamp_created >= week_ago)
            .order_by(MemoryItem.timestamp_created.desc())
        )
        result = await db.execute(stmt)
        memories = result.scalars().all()

    if len(memories) < 3:
        return []

    # Simple clustering: for each memory, find close neighbors
    clusters = []
    used = set()
    threshold = 0.85  # cosine similarity threshold

    for mem in memories:
        if mem.id in used:
            continue
        if not mem.chroma_id:
            continue

        try:
            # Embed the memory content
            embedding = await embed_text(mem.content)
            results = query_memories(
                embedding=embedding,
                filter_dict={"$and": [{"user_id": user_id}, {"archived": False}]},
                k=20,
            )
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]

            cluster = [mem]
            used.add(mem.id)

            for i, chroma_id in enumerate(ids):
                if chroma_id == mem.chroma_id:
                    continue
                distance = distances[i] if i < len(distances) else 1.0
                similarity = 1.0 - distance
                if similarity >= threshold:
                    # Find the memory item with this chroma_id
                    for other in memories:
                        if other.id not in used and other.chroma_id == chroma_id:
                            cluster.append(other)
                            used.add(other.id)
                            break

            if len(cluster) >= 3:
                clusters.append(cluster)
        except Exception as e:
            log.warning(f"Clustering error for memory {mem.id}: {e}")
            continue

    return clusters


async def _consolidate_cluster(user_id: str, cluster: list[MemoryItem]) -> Optional[MemoryItem]:
    """Create a consolidation memory from a cluster."""
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "consolidation_v1.txt"
    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    memory_lines = []
    for m in cluster:
        ts_str = time.strftime("%Y-%m-%d", time.localtime(m.timestamp_created)) if m.timestamp_created else "?"
        memory_lines.append(f"[{ts_str}] [{m.category}] {m.content}")
    cluster_text = "\n".join(memory_lines)

    prompt = template.replace("{cluster_memories_text}", cluster_text)
    response = await _call_llm(prompt)

    try:
        data = json.loads(response)
        content = data.get("content", "").strip()
        if not content:
            return None
        importance = float(data.get("importance", 0.6))
        entities = data.get("involves_entities", [])

        now = int(time.time())
        consolidated = MemoryItem(
            user_id=user_id,
            content=content,
            category="consolidation",
            importance=importance,
            timestamp_created=now,
            related_to=[m.id for m in cluster],
        )

        async with get_async_db() as db:
            db.add(consolidated)
            await db.commit()
            await db.refresh(consolidated)

        # Embed and add to ChromaDB
        embedding = await embed_text(content)
        chroma_id = f"consolidation-{consolidated.id}"
        chroma_meta = {
            "user_id": user_id,
            "category": "consolidation",
            "importance": importance,
            "sensitivity": 0.0,
            "timestamp_event": "",
            "memory_item_id": consolidated.id,
            "pinned": False,
            "archived": False,
        }
        add_memory(embedding, content, chroma_meta, chroma_id)

        consolidated.chroma_id = chroma_id
        async with get_async_db() as db:
            db.add(consolidated)
            await db.commit()

        # Archive source memories
        for m in cluster:
            m.archived = True
            async with get_async_db() as db:
                db.add(m)
                await db.commit()

        log.info(f"Created consolidation memory {consolidated.id} from {len(cluster)} sources")
        return consolidated

    except Exception as e:
        log.error(f"Failed to consolidate cluster: {e}")
        return None


async def run_consolidation(user_id: str) -> list[int]:
    """Run consolidation for a user. Returns list of created consolidation IDs."""
    clusters = await _cluster_memories(user_id)
    created = []
    for cluster in clusters:
        consolidated = await _consolidate_cluster(user_id, cluster)
        if consolidated:
            created.append(consolidated.id)
    return created


async def consolidation_worker_loop() -> None:
    """Main loop for the consolidation worker.

    Runs weekly (configurable via cron-like sleep).
    """
    global _running
    _running = True
    log.info("Consolidation worker started.")

    while _running:
        try:
            # Check all users with memories
            async with get_async_db() as db:
                from sqlalchemy import select, distinct
                stmt = select(distinct(MemoryItem.user_id))
                result = await db.execute(stmt)
                user_ids = result.scalars().all()

            for user_id in user_ids:
                try:
                    created = await run_consolidation(user_id)
                    if created:
                        log.info(f"Consolidation: created {len(created)} synthesis memories for user {user_id}")
                except Exception as e:
                    log.error(f"Consolidation error for user {user_id}: {e}")

            # Sleep for a week (or until cancelled)
            await asyncio.sleep(7 * 24 * 3600)

        except asyncio.CancelledError:
            log.info("Consolidation worker cancelled.")
            break
        except Exception as e:
            log.error(f"Consolidation worker error: {e}")
            await asyncio.sleep(3600)

    _running = False
    log.info("Consolidation worker stopped.")


def stop_worker() -> None:
    global _running
    _running = False
