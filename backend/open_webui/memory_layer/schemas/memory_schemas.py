"""Pydantic schemas for memory items."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MemoryItemCreate(BaseModel):
    content: str
    source_message_id: Optional[str] = None
    source_chat_id: Optional[str] = None
    source_document_id: Optional[str] = None
    workspace_id: Optional[str] = None
    timestamp_event: Optional[int] = None
    speaker: Optional[str] = None
    category: Optional[str] = None
    importance: float = 0.5
    sensitivity: float = 0.0
    pinned: bool = False
    archived: bool = False
    related_to: Optional[list] = None
    meta: Optional[dict] = None


class MemoryItemUpdate(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None
    sensitivity: Optional[float] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    related_to: Optional[list] = None
    meta: Optional[dict] = None


class MemoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
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


class OnboardingAnswer(BaseModel):
    question: str
    answer: str
    category: str = "fact"


class OnboardingPayload(BaseModel):
    answers: list[OnboardingAnswer]
    skip_questionnaire: bool = False
