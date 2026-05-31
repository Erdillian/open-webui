"""Memory extraction logic: LLM call, JSON parsing, dedup, conflict detection."""
import json
import logging
import time
import uuid
from typing import Optional

from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.embeddings.ollama_embed import embed_text, embed_texts
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.retrieval.chroma_client import add_memory, query_memories

log = logging.getLogger(__name__)


async def _call_extractor_llm(exchange_text: str, message_timestamp: int) -> list[dict]:
    """Call the extractor LLM to get memory items from an exchange.

    Returns a list of parsed memory dicts.
    """
    config = get_config()
    model = config.MEM_EXTRACTOR_MODEL

    # Load prompt template
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "memory_extractor_v1.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    if not prompt_template:
        log.error("memory_extractor_v1.txt not found")
        return []

    # Format prompt
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message_timestamp))
    prompt = prompt_template.replace("{exchange_text}", exchange_text).replace(
        "{message_timestamp}", ts_str
    )

    # Call Ollama
    import aiohttp
    import os

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{ollama_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Extractor LLM error {resp.status}: {text}")
                data = await resp.json()
                raw_response = data.get("response", "")
                # Parse JSON array from response
                # The LLM may wrap it in markdown code blocks
                raw_response = raw_response.strip()
                if raw_response.startswith("```"):
                    raw_response = raw_response.strip("`")
                    if raw_response.startswith("json"):
                        raw_response = raw_response[4:].strip()

                items = json.loads(raw_response)
                if isinstance(items, dict):
                    items = [items]
                if not isinstance(items, list):
                    log.warning(f"Extractor returned non-list: {type(items)}")
                    return []
                return items
    except Exception as e:
        log.error(f"Extractor LLM call failed: {e}")
        return []


async def _detect_duplicates(
    new_embedding: list[float],
    user_id: str,
    threshold: float = 0.92,
) -> Optional[dict]:
    """Check if a semantically identical memory already exists.

    Returns the existing memory meta if duplicate found, else None.
    """
    results = query_memories(
        embedding=new_embedding,
        filter_dict={"user_id": user_id},
        k=5,
    )
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, chroma_id in enumerate(ids):
        if not chroma_id:
            continue
        distance = distances[i] if i < len(distances) else 1.0
        similarity = 1.0 - distance
        if similarity >= threshold:
            metas = results.get("metas", [[]])[0]
            meta = metas[i] if i < len(metas) else {}
            return {"chroma_id": chroma_id, "meta": meta, "similarity": similarity}
    return None


async def _detect_conflicts(
    new_embedding: list[float],
    new_content: str,
    user_id: str,
    low_threshold: float = 0.75,
    high_threshold: float = 0.92,
) -> list[dict]:
    """Detect potentially conflicting memories.

    Returns a list of existing memories that are semantically close but not identical.
    """
    results = query_memories(
        embedding=new_embedding,
        filter_dict={"user_id": user_id},
        k=10,
    )
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metas = results.get("metas", [[]])[0]

    conflicts = []
    for i, chroma_id in enumerate(ids):
        if not chroma_id:
            continue
        distance = distances[i] if i < len(distances) else 1.0
        similarity = 1.0 - distance
        if low_threshold <= similarity < high_threshold:
            meta = metas[i] if i < len(metas) else {}
            conflicts.append(
                {
                    "chroma_id": chroma_id,
                    "content": documents[i] if i < len(documents) else "",
                    "meta": meta,
                    "similarity": similarity,
                }
            )
    return conflicts


async def extract_memories_from_exchange(
    user_id: str,
    messages: list[dict],
    chat_id: Optional[str] = None,
) -> list[int]:
    """Extract memories from a user-assistant exchange.

    Args:
        user_id: The user ID.
        messages: The exchange messages (usually [user_msg, assistant_msg]).
        chat_id: Optional chat ID.

    Returns:
        List of created memory item IDs.
    """
    config = get_config()
    if not messages:
        return []

    # Build exchange text
    exchange_lines = []
    msg_ts = None
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp")
        if ts and msg_ts is None:
            msg_ts = ts
        exchange_lines.append(f"{role.upper()}: {content}")
    exchange_text = "\n".join(exchange_lines)

    if msg_ts is None:
        msg_ts = int(time.time())

    # Call extractor LLM
    raw_items = await _call_extractor_llm(exchange_text, msg_ts)
    if not raw_items:
        return []

    created_ids = []
    from open_webui.internal.db import get_async_db

    async with get_async_db() as db:
        for item in raw_items:
            try:
                content = item.get("content", "").strip()
                if not content:
                    continue

                category = item.get("category", "fact")
                importance = float(item.get("importance", 0.5))
                sensitivity = float(item.get("sensitivity", 0.0))
                timestamp_event_str = item.get("timestamp_event")
                timestamp_event = None
                if timestamp_event_str:
                    try:
                        from datetime import datetime

                        dt = datetime.fromisoformat(timestamp_event_str.replace("Z", "+00:00"))
                        timestamp_event = int(dt.timestamp())
                    except Exception:
                        pass
                speaker = item.get("speaker", "user")
                involves_entities = item.get("involves_entities", [])

                # Embed the memory content
                embedding = await embed_text(content)

                # Check for duplicates
                duplicate = await _detect_duplicates(embedding, user_id, threshold=config.MEM_CONFLICT_SIMILARITY_HIGH)
                if duplicate:
                    log.debug(f"Duplicate detected for memory: {content[:50]}...")
                    # TODO: Update existing memory with new reference
                    continue

                # Check for conflicts
                conflicts = await _detect_conflicts(
                    embedding,
                    content,
                    user_id,
                    low_threshold=config.MEM_CONFLICT_SIMILARITY_LOW,
                    high_threshold=config.MEM_CONFLICT_SIMILARITY_HIGH,
                )

                # Insert into DB
                now = int(time.time())
                memory_item = MemoryItem(
                    user_id=user_id,
                    content=content,
                    source_chat_id=chat_id,
                    timestamp_created=now,
                    timestamp_event=timestamp_event,
                    speaker=speaker,
                    category=category,
                    importance=importance,
                    sensitivity=sensitivity,
                )
                db.add(memory_item)
                await db.commit()
                await db.refresh(memory_item)

                # Insert into ChromaDB
                chroma_id = str(uuid.uuid4())
                chroma_meta = {
                    "user_id": user_id,
                    "category": category,
                    "importance": importance,
                    "sensitivity": sensitivity,
                    "timestamp_event": timestamp_event if timestamp_event else "",
                    "memory_item_id": memory_item.id,
                    "pinned": False,
                    "archived": False,
                }
                add_memory(embedding, content, chroma_meta, chroma_id)

                # Update memory item with chroma_id
                memory_item.chroma_id = chroma_id
                await db.commit()

                created_ids.append(memory_item.id)

                # Trace memory creation
                try:
                    from open_webui.memory_layer.services.audit_service import trace_event
                    await trace_event(
                        user_id=user_id,
                        event_type="extraction_created",
                        payload={
                            "content": content,
                            "category": category,
                            "importance": importance,
                            "sensitivity": sensitivity,
                            "speaker": speaker,
                            "conflicts_count": len(conflicts),
                        },
                        summary=f"Extracted memory [{category}]: {content[:100]}...",
                        chat_id=chat_id,
                        memory_id=memory_item.id,
                    )
                except Exception:
                    pass

                # Create conflict entries if any
                for conflict in conflicts:
                    from open_webui.memory_layer.models.conflict import MemoryConflict

                    conflict_entry = MemoryConflict(
                        user_id=user_id,
                        memory_a_id=memory_item.id,
                        memory_b_id=memory_item.id,
                        similarity_score=conflict["similarity"],
                        status="pending",
                        detected_at=now,
                    )
                    db.add(conflict_entry)

                    # Trace conflict
                    try:
                        from open_webui.memory_layer.services.audit_service import trace_event
                        await trace_event(
                            user_id=user_id,
                            event_type="conflict_detected",
                            payload={
                                "new_memory_id": memory_item.id,
                                "existing_chroma_id": conflict.get("chroma_id"),
                                "existing_content_preview": conflict.get("content", "")[:100],
                                "similarity": conflict["similarity"],
                            },
                            summary=f"Conflict detected: new memory similar ({conflict['similarity']:.2f}) to existing",
                            chat_id=chat_id,
                            memory_id=memory_item.id,
                        )
                    except Exception:
                        pass

                await db.commit()

            except Exception as e:
                log.error(f"Error processing extracted memory item: {e}")
                continue

    return created_ids
