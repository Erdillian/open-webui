"""Audit log model for memory layer tracing."""
from typing import Optional

from open_webui.internal.db import Base
from sqlalchemy import BigInteger, Column, Integer, JSON, String, Text


class AuditLog(Base):
    __tablename__ = "mem_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    # Structured payload depending on event_type
    payload = Column(JSON, nullable=True)
    # Human-readable summary
    summary = Column(Text, nullable=True)
    # Chat or memory reference
    chat_id = Column(String, nullable=True, index=True)
    memory_id = Column(Integer, nullable=True, index=True)


class AuditLogModel:
    id: Optional[int] = None
    timestamp: int
    user_id: str
    event_type: str
    payload: Optional[dict] = None
    summary: Optional[str] = None
    chat_id: Optional[str] = None
    memory_id: Optional[int] = None
