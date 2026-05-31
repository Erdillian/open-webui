"""Configuration for the memory layer."""
import os
from functools import lru_cache


class MemoryLayerConfig:
    """Centralized configuration loaded from environment variables."""

    # Embeddings
    MEM_EMBEDDINGS_MODEL: str = os.getenv("MEM_EMBEDDINGS_MODEL", "nomic-embed-text")

    # Extractor
    MEM_EXTRACTOR_MODEL: str = os.getenv("MEM_EXTRACTOR_MODEL", "qwen3:32b-cloud")

    # Profile
    MEM_PROFILE_MODEL: str = os.getenv("MEM_PROFILE_MODEL", "qwen3:32b-cloud")

    # Retrieval
    MEM_DEFAULT_K_PASSIVE: int = int(os.getenv("MEM_DEFAULT_K_PASSIVE", "8"))

    # Conflict detection thresholds
    MEM_CONFLICT_SIMILARITY_LOW: float = float(os.getenv("MEM_CONFLICT_SIMILARITY_LOW", "0.75"))
    MEM_CONFLICT_SIMILARITY_HIGH: float = float(os.getenv("MEM_CONFLICT_SIMILARITY_HIGH", "0.92"))

    # Profile worker triggers
    MEM_PROFILE_REGEN_THRESHOLD: int = int(os.getenv("MEM_PROFILE_REGEN_THRESHOLD", "50"))
    MEM_PROFILE_REGEN_DAYS: int = int(os.getenv("MEM_PROFILE_REGEN_DAYS", "7"))

    # Consolidation cron (default: Sunday 3am)
    MEM_CONSOLIDATION_CRON: str = os.getenv("MEM_CONSOLIDATION_CRON", "0 3 * * 0")

    # Opening prompt inactivity threshold (hours)
    MEM_OPENING_INACTIVITY_HOURS: float = float(os.getenv("MEM_OPENING_INACTIVITY_HOURS", "12"))

    # ChromaDB
    MEM_CHROMA_COLLECTION: str = os.getenv("MEM_CHROMA_COLLECTION", "memory_items")

    # Sensitivity penalty weight in retrieval scoring
    MEM_SENSITIVITY_PENALTY_WEIGHT: float = float(os.getenv("MEM_SENSITIVITY_PENALTY_WEIGHT", "0.3"))

    # Sycophancy block toggle
    MEM_ANTI_SYCOPHANCY_ENABLED: bool = os.getenv("MEM_ANTI_SYCOPHANCY_ENABLED", "true").lower() in ("1", "true", "yes")


@lru_cache()
def get_config() -> MemoryLayerConfig:
    return MemoryLayerConfig()
