"""ChromaDB client wrapper for memory items collection."""
import logging
import uuid
from typing import Optional

from open_webui.config import (
    CHROMA_DATA_PATH,
    CHROMA_HTTP_HOST,
    CHROMA_HTTP_PORT,
    CHROMA_HTTP_HEADERS,
    CHROMA_HTTP_SSL,
    CHROMA_TENANT,
    CHROMA_DATABASE,
    CHROMA_CLIENT_AUTH_PROVIDER,
    CHROMA_CLIENT_AUTH_CREDENTIALS,
)
from open_webui.memory_layer.config import get_config

log = logging.getLogger(__name__)

_chroma_client = None
_memory_collection = None


def _get_chroma_client():
    """Lazy-initialize the ChromaDB client using Open WebUI's config."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        from chromadb import Settings

        settings_dict = {
            "allow_reset": True,
            "anonymized_telemetry": False,
        }
        if CHROMA_CLIENT_AUTH_PROVIDER is not None:
            settings_dict["chroma_client_auth_provider"] = CHROMA_CLIENT_AUTH_PROVIDER
        if CHROMA_CLIENT_AUTH_CREDENTIALS is not None:
            settings_dict["chroma_client_auth_credentials"] = CHROMA_CLIENT_AUTH_CREDENTIALS

        if CHROMA_HTTP_HOST != "":
            _chroma_client = chromadb.HttpClient(
                host=CHROMA_HTTP_HOST,
                port=CHROMA_HTTP_PORT,
                headers=CHROMA_HTTP_HEADERS,
                ssl=CHROMA_HTTP_SSL,
                tenant=CHROMA_TENANT,
                database=CHROMA_DATABASE,
                settings=Settings(**settings_dict),
            )
        else:
            _chroma_client = chromadb.PersistentClient(
                path=CHROMA_DATA_PATH,
                settings=Settings(**settings_dict),
                tenant=CHROMA_TENANT,
                database=CHROMA_DATABASE,
            )
    return _chroma_client


def get_memory_collection():
    """Get or create the memory_items ChromaDB collection."""
    global _memory_collection
    if _memory_collection is None:
        client = _get_chroma_client()
        config = get_config()
        _memory_collection = client.get_or_create_collection(
            name=config.MEM_CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"ChromaDB collection '{config.MEM_CHROMA_COLLECTION}' ready.")
    return _memory_collection


def reset_memory_collection():
    """Reset the memory collection (useful for testing)."""
    global _memory_collection
    _memory_collection = None


def add_memory(
    embedding: list[float],
    content: str,
    metadata: dict,
    chroma_id: Optional[str] = None,
) -> str:
    """Add a memory item to the ChromaDB collection.

    Returns the chroma_id used.
    """
    collection = get_memory_collection()
    if chroma_id is None:
        chroma_id = str(uuid.uuid4())

    # ChromaDB metadata must be serializable (no nested dicts/lists)
    flat_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            flat_metadata[key] = value
        else:
            flat_metadata[key] = str(value)

    collection.add(
        ids=[chroma_id],
        embeddings=[embedding],
        documents=[content],
        metadatas=[flat_metadata],
    )
    return chroma_id


def get_memory(chroma_id: str) -> Optional[dict]:
    """Fetch a single memory item by chroma_id.

    Returns a dict with keys: id, embedding, document, metadata, or None.
    """
    collection = get_memory_collection()
    try:
        result = collection.get(
            ids=[chroma_id],
            include=["embeddings", "documents", "metadatas"],
        )
        if not result.get("ids") or not result["ids"]:
            return None
        return {
            "id": result["ids"][0],
            "embedding": result.get("embeddings", [[]])[0],
            "document": result.get("documents", [""])[0],
            "metadata": result.get("metadatas", [{}])[0],
        }
    except Exception as e:
        log.warning(f"Failed to get memory {chroma_id}: {e}")
        return None


def update_memory(
    chroma_id: str,
    content: Optional[str] = None,
    metadata: Optional[dict] = None,
    embedding: Optional[list[float]] = None,
) -> None:
    """Update a memory item in ChromaDB by chroma_id.

    Only provided fields are updated. Metadata values are flattened for
    ChromaDB serialization.
    """
    collection = get_memory_collection()
    try:
        kwargs: dict = {"ids": [chroma_id]}
        if content is not None:
            kwargs["documents"] = [content]
        if embedding is not None:
            kwargs["embeddings"] = [embedding]
        if metadata is not None:
            flat_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    flat_metadata[key] = value
                else:
                    flat_metadata[key] = str(value)
            kwargs["metadatas"] = [flat_metadata]
        collection.update(**kwargs)
    except Exception as e:
        log.warning(f"Failed to update memory {chroma_id}: {e}")


def delete_memory(chroma_id: str) -> None:
    """Delete a memory item by chroma_id."""
    collection = get_memory_collection()
    try:
        collection.delete(ids=[chroma_id])
    except Exception as e:
        log.warning(f"Failed to delete memory {chroma_id}: {e}")


def query_memories(
    embedding: list[float],
    filter_dict: Optional[dict] = None,
    k: int = 20,
    include_embeddings: bool = True,
) -> dict:
    """Query the memory collection for nearest neighbors.

    Returns raw ChromaDB result dict with keys: ids, distances, documents,
    metadatas, and embeddings (when include_embeddings is True).
    """
    collection = get_memory_collection()
    include = ["distances", "documents", "metadatas"]
    if include_embeddings:
        include.append("embeddings")
    result = collection.query(
        query_embeddings=[embedding],
        n_results=k,
        where=filter_dict,
        include=include,
    )
    return result
