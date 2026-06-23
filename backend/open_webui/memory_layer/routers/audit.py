"""Audit log router for memory layer observability."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from open_webui.memory_layer.schemas.audit_schemas import AuditLogListResponse, AuditLogEntry
from open_webui.memory_layer.services.audit_service import list_audit_logs
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=AuditLogListResponse)
async def get_audit_logs(
    request: Request,
    event_type: Optional[str] = None,
    chat_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: UserModel = Depends(get_verified_user),
):
    """Get audit logs for the current user."""
    items = await list_audit_logs(
        user_id=user.id,
        event_type=event_type,
        chat_id=chat_id,
        limit=min(limit, 500),
        offset=offset,
    )
    total = len(items)  # Simplified; in production use count query
    return AuditLogListResponse(
        items=[AuditLogEntry.model_validate(i) for i in items],
        total=total,
    )
