"""
CivicPulse AI — Notification API Routes (Phase 5)
Handles user notifications retrieval and read state updates.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.core.database import get_db
from backend.core.deps import get_optional_current_user, verify_user_access
from backend.schemas.notification import NotificationRead, NotificationListResponse
from backend.services import notification_service
from backend.models.user import User
from backend.models.notification import Notification
from backend.models.enums import UserRole

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)


@router.get(
    "/user/{user_id}",
    response_model=NotificationListResponse,
    summary="Retrieve notifications for a user",
)
def get_user_notifications(
    user_id: int,
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    verify_user_access(user_id, current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )
    result = notification_service.get_user_notifications(db, user_id=user_id, unread_only=unread_only)
    return NotificationListResponse(
        items=[NotificationRead.model_validate(n) for n in result["items"]],
        unread_count=result["unread_count"],
        total=result["total"],
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a specific notification as read",
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with id={notification_id} not found.",
        )
    if current_user and current_user.role == UserRole.CITIZEN.value:
        if notif.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot modify another user's notification.",
            )
    notification = notification_service.mark_as_read(db, notification_id=notification_id)
    return notification


@router.post(
    "/user/{user_id}/read-all",
    summary="Mark all notifications for a user as read",
)
def mark_all_notifications_read(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    verify_user_access(user_id, current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )
    updated_count = notification_service.mark_all_as_read(db, user_id=user_id)
    return {"updated": updated_count}

