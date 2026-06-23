"""Memory item model."""
from typing import Optional

from open_webui.internal.db import Base, JSONField
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)


class MemoryItem(Base):
    __tablename__ = "mem_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_message_id = Column(String, nullable=True)
    source_chat_id = Column(
        String, ForeignKey("chat.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id = Column(String, nullable=True)
    workspace_id = Column(String, nullable=True)
    timestamp_created = Column(BigInteger, nullable=True)
    timestamp_event = Column(BigInteger, nullable=True)
    speaker = Column(String, nullable=True)
    category = Column(String, nullable=True)
    importance = Column(Float, default=0.5)
    sensitivity = Column(Float, default=0.0)
    pinned = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)
    superseded_by = Column(
        Integer, ForeignKey("mem_items.id", ondelete="SET NULL"), nullable=True
    )
    related_to = Column(JSON, nullable=True)
    chroma_id = Column(String, nullable=True)
    meta = Column(JSON, nullable=True)


class MemoryItemModel(BaseModel):
    id: Optional[int] = None
    user_id: str
    content: str
    source_message_id: Optional[str] = None
    source_chat_id: Optional[str] = None
    source_document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    timestamp_created: Optional[int] = None
    timestamp_event: Optional[int] = None
    speaker: Optional[str] = None
    category: Optional[str] = None
    importance: float = 0.5
    sensitivity: float = 0.0
    pinned: bool = False
    archived: bool = False
    superseded_by: Optional[int] = None
    related_to: Optional[list] = None
    chroma_id: Optional[str] = None
    meta: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)
