"""Pydantic schemas for memory tags."""
from typing import Optional

from pydantic import BaseModel


class MemoryTagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class MemoryTagResponse(BaseModel):
    id: int
    user_id: str
    name: str
    color: Optional[str] = None
