"""Memory tag models."""
from typing import Optional

from open_webui.internal.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
)


class MemoryTag(Base):
    __tablename__ = "mem_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id"),
        {"sqlite_autoincrement": True},
    )


class MemoryItemTag(Base):
    __tablename__ = "mem_item_tags"

    memory_item_id = Column(
        Integer, ForeignKey("mem_items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = Column(
        Integer, ForeignKey("mem_tags.id", ondelete="CASCADE"), primary_key=True
    )


class MemoryTagModel(BaseModel):
    id: Optional[int] = None
    user_id: str
    name: str
    color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryItemTagModel(BaseModel):
    memory_item_id: int
    tag_id: int

    model_config = ConfigDict(from_attributes=True)
