"""Conflict router."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.memory_layer.schemas.conflict_schemas import (
    MemoryConflictResponse,
    MemoryConflictUpdate,
)
from open_webui.memory_layer.services.conflict_service import (
    list_conflicts,
    update_conflict_status,
)
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[MemoryConflictResponse])
async def get_conflicts(
    request: Request,
    status: Optional[str] = None,
    user: UserModel = Depends(get_verified_user),
):
    """List memory conflicts for the current user."""
    items = await list_conflicts(user.id, status=status)
    return [MemoryConflictResponse.model_validate(i) for i in items]


@router.patch("/{conflict_id}", response_model=MemoryConflictResponse)
async def patch_conflict(
    request: Request,
    conflict_id: int,
    data: MemoryConflictUpdate,
    user: UserModel = Depends(get_verified_user),
):
    """Update a conflict status."""
    updated = await update_conflict_status(
        conflict_id=conflict_id,
        new_status=data.status,
        resolution_memory_id=data.resolution_memory_id,
        user_id=user.id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return MemoryConflictResponse.model_validate(updated)
