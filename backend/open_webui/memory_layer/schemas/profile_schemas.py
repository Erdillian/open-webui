"""Pydantic schemas for user profile."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserProfileUpdate(BaseModel):
    executive_summary: Optional[str] = None
    full_profile_json: Optional[dict] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    executive_summary: str
    full_profile_json: dict
    last_updated: Optional[int] = None
    last_full_regen: Optional[int] = None
    memories_since_regen: int = 0
    onboarding_done: Optional[bool] = False


class UserProfileHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    executive_summary: str
    full_profile_json: dict
    created_at: Optional[int] = None
    trigger: Optional[str] = None
