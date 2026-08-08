"""
CivicPulse AI — Notification Service Layer (Phase 5)
Handles creation, listing, marking read, and event notifications.
"""
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from backend.models.notification import Notification
from backend.models.enums import NotificationType

import logging

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    *,
    user_id: int,
    complaint_id: int,
    notification_type: str,
    title: str,
    message: str,
) -> Notification:
    """
    Create and persist a notification event for a user regarding a complaint.
    """
    notification = Notification(
        user_id=user_id,
        complaint_id=complaint_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    # Note: caller will commit transaction, or if standalone, caller handles db.commit()
    logger.info(
        "Created notification type=%s for user_id=%s complaint_id=%s",
        notification_type,
        user_id,
        complaint_id,
    )
    return notification


def get_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
) -> Dict:
    """
    Retrieve notifications for a given user, ordered newest first.
    Returns dict with items, unread_count, and total.
    """
    query = db.query(Notification).filter(Notification.user_id == user_id)
    
    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,  # noqa: E712
    ).count()

    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712

    items = query.order_by(Notification.created_at.desc()).all()

    return {
        "items": items,
        "unread_count": unread_count,
        "total": total,
    }


def get_complaint_notifications(
    db: Session,
    complaint_id: int,
) -> List[Notification]:
    """
    Retrieve all notifications related to a specific complaint.
    """
    return (
        db.query(Notification)
        .filter(Notification.complaint_id == complaint_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def mark_as_read(
    db: Session,
    notification_id: int,
    user_id: Optional[int] = None,
) -> Optional[Notification]:
    """
    Mark a notification as read. Optionally checks user_id ownership.
    """
    query = db.query(Notification).filter(Notification.id == notification_id)
    if user_id is not None:
        query = query.filter(Notification.user_id == user_id)
    
    notification = query.first()
    if notification is None:
        return None

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_as_read(
    db: Session,
    user_id: int,
) -> int:
    """
    Mark all unread notifications for a user as read.
    Returns count of updated records.
    """
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return count
