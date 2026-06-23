"""Document ingestion to memory worker.

Hooks into document upload events to create a memory summary.
"""
import logging
import time
import uuid
from typing import Optional

from open_webui.memory_layer.embeddings.ollama_embed import embed_text
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.retrieval.chroma_client import add_memory

log = logging.getLogger(__name__)


async def summarize_document(document_text: str, document_name: str, timeout: float = 60.0) -> str:
    """Summarize a document using the LLM."""
    import os
    import aiohttp

    from open_webui.memory_layer.config import get_config

    config = get_config()
    model = config.MEM_EXTRACTOR_MODEL

    # Load prompt
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "document_summarizer_v1.txt"
    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    # Truncate very long documents
    max_chars = 15000
    text = document_text[:max_chars]

    prompt = template.replace("{document_text}", text)

    url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                text_body = await resp.text()
                raise RuntimeError(f"Document summarizer error {resp.status}: {text_body}")
            data = await resp.json()
            return data.get("response", "").strip()


async def create_memory_from_document(
    user_id: str,
    document_id: str,
    document_name: str,
    document_text: str,
) -> Optional[int]:
    """Create a memory item from an uploaded document.

    Returns the created memory item ID.
    """
    try:
        summary = await summarize_document(document_text, document_name)
        if not summary:
            return None

        now = int(time.time())
        content = f"Document '{document_name}' ingéré : {summary}"

        # Insert into DB
        from open_webui.internal.db import get_async_db

        async with get_async_db() as db:
            item = MemoryItem(
                user_id=user_id,
                content=content,
                source_document_id=document_id,
                category="consolidation",
                importance=0.6,
                timestamp_created=now,
            )
            db.add(item)
            await db.commit()
            await db.refresh(item)

            # Embed and add to ChromaDB
            embedding = await embed_text(content)
            chroma_id = str(uuid.uuid4())
            chroma_meta = {
                "user_id": user_id,
                "category": "consolidation",
                "importance": 0.6,
                "sensitivity": 0.0,
                "timestamp_event": "",
                "memory_item_id": item.id,
                "pinned": False,
                "archived": False,
            }
            add_memory(embedding, content, chroma_meta, chroma_id)

            item.chroma_id = chroma_id
            await db.commit()

        log.info(f"Created memory from document {document_id} for user {user_id}")
        return item.id

    except Exception as e:
        log.error(f"Failed to create memory from document: {e}")
        return None
