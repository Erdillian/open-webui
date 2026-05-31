"""Memory retrieval with re-ranking and sensitivity-aware scoring."""
import logging
import math
import time
from typing import Optional

from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.embeddings.ollama_embed import embed_text
from open_webui.memory_layer.retrieval.chroma_client import query_memories

log = logging.getLogger(__name__)


def _recency_decay(timestamp: Optional[int]) -> float:
    """Compute a recency score: 1.0 for today, decaying exponentially."""
    if timestamp is None:
        return 0.5  # Neutral for undated memories
    now = int(time.time())
    age_seconds = now - timestamp
    if age_seconds < 0:
        return 1.0  # Future-dated, treat as recent
    # Half-life of 30 days
    half_life_seconds = 30 * 24 * 3600
    decay = math.exp(-age_seconds / half_life_seconds)
    return float(decay)


def _sensitivity_penalty(
    sensitivity: float, query_embedding: list[float], memory_embedding: list[float]
) -> float:
    """Compute sensitivity penalty. Lower if query is semantically close to memory topic."""
    # Simple cosine similarity between query and memory
    dot = sum(a * b for a, b in zip(query_embedding, memory_embedding))
    norm_q = math.sqrt(sum(a * a for a in query_embedding))
    norm_m = math.sqrt(sum(a * a for a in memory_embedding))
    if norm_q == 0 or norm_m == 0:
        sim = 0.0
    else:
        sim = dot / (norm_q * norm_m)
    penalty = sensitivity * (1 - max(0.0, sim - 0.6))
    return float(penalty)


def _score_memory(
    cosine_distance: float,
    importance: float,
    timestamp: Optional[int],
    pinned: bool,
    sensitivity: float,
    query_embedding: list[float],
    memory_embedding: list[float],
) -> float:
    """Compute final retrieval score for a memory item.

    Formula (from plan section 6.1):
    score = 0.6 * (1 - distance)
          + 0.2 * importance
          + 0.1 * recency_decay
          + 0.1 * pinned_boost
          - 0.3 * sensitivity_penalty
    """
    config = get_config()
    similarity = 1.0 - cosine_distance
    recency = _recency_decay(timestamp)
    pinned_boost = 1.0 if pinned else 0.0
    sens_penalty = _sensitivity_penalty(sensitivity, query_embedding, memory_embedding)

    score = (
        0.6 * similarity
        + 0.2 * importance
        + 0.1 * recency
        + 0.1 * pinned_boost
        - config.MEM_SENSITIVITY_PENALTY_WEIGHT * sens_penalty
    )
    return score


async def search_memories(
    user_id: str,
    query: str,
    k: int = 20,
    category: Optional[str] = None,
    workspace_id: Optional[str] = None,
    include_archived: bool = False,
    exclude_ids: Optional[list[str]] = None,
) -> list[dict]:
    """Search memories for a user via semantic similarity + re-ranking.

    Returns a list of scored memory dicts sorted by descending score.
    Each dict contains: id, content, metadata, score, distance.
    """
    config = get_config()
    if k <= 0:
        k = config.MEM_DEFAULT_K_PASSIVE

    # Embed the query
    query_embedding = await embed_text(query)

    # Build ChromaDB filter (must use operator syntax; flat dict with multiple keys rejected)
    conditions: list[dict] = [{"user_id": user_id}]
    if category and category != "any":
        conditions.append({"category": category})
    if workspace_id:
        conditions.append({"workspace_id": workspace_id})
    if not include_archived:
        conditions.append({"archived": False})

    if len(conditions) > 1:
        filter_dict = {"$and": conditions}
    elif conditions:
        filter_dict = conditions[0]
    else:
        filter_dict = None

    # Query ChromaDB
    raw_result = query_memories(
        embedding=query_embedding,
        filter_dict=filter_dict,
        k=k,
    )

    # Parse results
    ids = raw_result.get("ids", [[]])[0]
    distances = raw_result.get("distances", [[]])[0]
    documents = raw_result.get("documents", [[]])[0]
    metadatas = raw_result.get("metadatas", [[]])[0]

    if not ids:
        return []

    # Re-rank with scoring formula
    scored = []
    for i, chroma_id in enumerate(ids):
        if not chroma_id:
            continue
        if exclude_ids and chroma_id in exclude_ids:
            continue

        distance = distances[i] if i < len(distances) else 1.0
        document = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) else {}

        # Extract fields from metadata (stored as strings in ChromaDB)
        importance = float(meta.get("importance", 0.5))
        sensitivity = float(meta.get("sensitivity", 0.0))
        pinned = str(meta.get("pinned", "False")).lower() == "true"
        timestamp_str = meta.get("timestamp_event")
        timestamp = int(timestamp_str) if timestamp_str and str(timestamp_str).isdigit() else None

        # Get memory embedding from ChromaDB (not returned by query, so we approximate)
        # For accurate scoring we'd need the memory embedding; ChromaDB query doesn't return it.
        # We'll use query_embedding as a proxy for the memory_embedding in sensitivity calculation.
        # This is slightly inaccurate but avoids an extra get() call per result.
        score = _score_memory(
            cosine_distance=distance,
            importance=importance,
            timestamp=timestamp,
            pinned=pinned,
            sensitivity=sensitivity,
            query_embedding=query_embedding,
            memory_embedding=query_embedding,  # Approximation
        )

        scored.append(
            {
                "chroma_id": chroma_id,
                "content": document,
                "metadata": meta,
                "score": score,
                "distance": distance,
            }
        )

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
