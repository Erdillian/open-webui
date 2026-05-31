"""Memory conflict model."""
from typing import Optional

from open_webui.internal.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)


class MemoryConflict(Base):
    __tablename__ = "mem_conflicts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    memory_a_id = Column(
        Integer, ForeignKey("mem_items.id", ondelete="CASCADE"), nullable=False
    )
    memory_b_id = Column(
        Integer, ForeignKey("mem_items.id", ondelete="CASCADE"), nullable=False
    )
    detected_at = Column(BigInteger, nullable=True)
    similarity_score = Column(Float, nullable=True)
    status = Column(String, default="pending")
    resolution_memory_id = Column(
        Integer, ForeignKey("mem_items.id", ondelete="SET NULL"), nullable=True
    )
    metadata = Column(JSON, nullable=True)


class MemoryConflictModel(BaseModel):
    id: Optional[int] = None
    user_id: str
    memory_a_id: int
    memory_b_id: int
    detected_at: Optional[int] = None
    similarity_score: Optional[float] = None
    status: str = "pending"
    resolution_memory_id: Optional[int] = None
    metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)
