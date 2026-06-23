"""Schemas for audit log endpoints."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    id: int
    timestamp: int
    user_id: str
    event_type: str
    payload: Optional[dict] = None
    summary: Optional[str] = None
    chat_id: Optional[str] = None
    memory_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
