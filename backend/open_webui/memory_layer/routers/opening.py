"""Opening prompt router."""
import logging

from fastapi import APIRouter, Depends, Request

from open_webui.memory_layer.services.opening_service import generate_opening_prompt
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_opening_prompt(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Get a personalized opening prompt for the current user.

    Returns an empty string if conditions are not met.
    """
    prompt = await generate_opening_prompt(user.id)
    return {"prompt": prompt}
