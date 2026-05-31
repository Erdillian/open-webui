"""User profile router."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.memory_layer.models.profile import UserProfileHistory
from open_webui.memory_layer.schemas.profile_schemas import (
    UserProfileResponse,
    UserProfileUpdate,
    UserProfileHistoryResponse,
)
from open_webui.memory_layer.services.profile_service import (
    get_or_create_profile,
    snapshot_profile_history,
    update_profile,
)
from open_webui.memory_layer.workers.profile_worker import _do_full_regen
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=UserProfileResponse)
async def get_user_profile(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Get the current user's profile."""
    profile = await get_or_create_profile(user.id)
    # Coerce None onboarding_done → False for legacy rows
    if getattr(profile, "onboarding_done", None) is None:
        profile.onboarding_done = False
    return UserProfileResponse.model_validate(profile)


@router.patch("/", response_model=UserProfileResponse)
async def patch_user_profile(
    request: Request,
    data: UserProfileUpdate,
    user: UserModel = Depends(get_verified_user),
):
    """Edit the current user's profile manually."""
    await snapshot_profile_history(user.id, trigger="manual")
    updated = await update_profile(
        user_id=user.id,
        executive_summary=data.executive_summary,
        full_profile_json=data.full_profile_json,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    if getattr(updated, "onboarding_done", None) is None:
        updated.onboarding_done = False
    return UserProfileResponse.model_validate(updated)


@router.post("/regenerate")
async def regenerate_profile(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Force a full profile regeneration."""
    # Run in background to avoid blocking
    import asyncio

    asyncio.create_task(_do_full_regen(user.id))
    return {"ok": True, "message": "Profile regeneration started"}


@router.get("/history", response_model=list[UserProfileHistoryResponse])
async def get_profile_history(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Get profile history snapshots."""
    from open_webui.internal.db import get_async_db
    from sqlalchemy import select

    async with get_async_db() as db:
        stmt = (
            select(UserProfileHistory)
            .where(UserProfileHistory.user_id == user.id)
            .order_by(UserProfileHistory.created_at.desc())
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        return [UserProfileHistoryResponse.model_validate(i) for i in items]
