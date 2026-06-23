"""User profile models."""
from typing import Optional

from open_webui.internal.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Integer, JSON, String, Text


class UserProfile(Base):
    __tablename__ = "mem_profile"

    user_id = Column(String, primary_key=True)
    executive_summary = Column(Text, nullable=False)
    full_profile_json = Column(JSON, nullable=False)
    last_updated = Column(BigInteger, nullable=True)
    last_full_regen = Column(BigInteger, nullable=True)
    memories_since_regen = Column(Integer, default=0)
    onboarding_done = Column(Boolean, default=False)


class UserProfileHistory(Base):
    __tablename__ = "mem_profile_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    executive_summary = Column(Text, nullable=False)
    full_profile_json = Column(JSON, nullable=False)
    created_at = Column(BigInteger, nullable=True)
    trigger = Column(String, nullable=True)


class UserProfileModel(BaseModel):
    user_id: str
    executive_summary: str
    full_profile_json: dict
    last_updated: Optional[int] = None
    last_full_regen: Optional[int] = None
    memories_since_regen: int = 0
    onboarding_done: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserProfileHistoryModel(BaseModel):
    id: Optional[int] = None
    user_id: str
    executive_summary: str
    full_profile_json: dict
    created_at: Optional[int] = None
    trigger: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
