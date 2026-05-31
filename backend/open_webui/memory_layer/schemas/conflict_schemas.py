"""Pydantic schemas for memory conflicts."""
from typing import Optional

from pydantic import BaseModel


class MemoryConflictUpdate(BaseModel):
    status: Optional[str] = None
    resolution_memory_id: Optional[int] = None
    metadata: Optional[dict] = None


class MemoryConflictResponse(BaseModel):
    id: int
    user_id: str
    memory_a_id: int
    memory_b_id: int
    detected_at: Optional[int] = None
    similarity_score: Optional[float] = None
    status: str = "pending"
    resolution_memory_id: Optional[int] = None
    metadata: Optional[dict] = None
