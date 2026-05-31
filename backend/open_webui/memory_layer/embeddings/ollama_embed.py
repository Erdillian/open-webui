"""Ollama embeddings wrapper for the memory layer."""
import logging
import os
from typing import Optional

import aiohttp

from open_webui.memory_layer.config import get_config

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


async def embed_text(
    text: str,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> list[float]:
    """Embed a single text string using Ollama's /api/embed endpoint.

    Returns a list of floats (the embedding vector).
    """
    config = get_config()
    if model is None:
        model = config.MEM_EMBEDDINGS_MODEL

    url = f"{OLLAMA_BASE_URL}/api/embed"
    payload = {
        "model": model,
        "input": [text],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status != 200:
                    text_body = await response.text()
                    raise RuntimeError(
                        f"Ollama embed failed: {response.status} - {text_body}"
                    )
                data = await response.json()
                # Ollama /api/embed returns { embeddings: [[...]] }
                embeddings = data.get("embeddings", [])
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                raise RuntimeError("Ollama embed returned empty embeddings")
    except Exception as e:
        log.error(f"Error embedding text with Ollama: {e}")
        raise


async def embed_texts(
    texts: list[str],
    model: Optional[str] = None,
    timeout: float = 60.0,
) -> list[list[float]]:
    """Embed multiple texts in a single batch call.

    Returns a list of embedding vectors.
    """
    config = get_config()
    if model is None:
        model = config.MEM_EMBEDDINGS_MODEL

    url = f"{OLLAMA_BASE_URL}/api/embed"
    payload = {
        "model": model,
        "input": texts,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status != 200:
                    text_body = await response.text()
                    raise RuntimeError(
                        f"Ollama embed batch failed: {response.status} - {text_body}"
                    )
                data = await response.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings
                raise RuntimeError("Ollama embed returned empty embeddings")
    except Exception as e:
        log.error(f"Error batch embedding texts with Ollama: {e}")
        raise
