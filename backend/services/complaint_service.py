"""
CivicPulse AI — Complaint Service Layer
All complaint business logic lives here. Route handlers must remain thin.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from backend.models.complaint import Complaint
from backend.models.status_history import ComplaintStatusHistory
from backend.models.user import User
from backend.models.department import Department
from backend.models.enums import ComplaintStatus, NotificationType
from backend.services import notification_service

import logging

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Valid status transitions
# None means "can come from any status"
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.SUBMITTED:     {ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.REJECTED},
    ComplaintStatus.ACKNOWLEDGED:  {ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REJECTED},
    ComplaintStatus.ASSIGNED:      {ComplaintStatus.IN_PROGRESS, ComplaintStatus.REJECTED},
    ComplaintStatus.IN_PROGRESS:   {ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED},
    ComplaintStatus.RESOLVED:      {ComplaintStatus.REOPENED},
    ComplaintStatus.REJECTED:      {ComplaintStatus.REOPENED},
    ComplaintStatus.REOPENED:      {ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS},
}


def create_complaint(
    db: Session,
    *,
    user_id: int,
    title: str,
    description: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    address: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    department_id: Optional[int] = None,
) -> Complaint:
    """
    Create a new complaint. Validates user existence, persists the complaint,
    then records the initial SUBMITTED status history entry.

    Designed for AI pipeline insertion: after this returns the Complaint,
    Phase 3 can call an async AI classification task using complaint.id
    without touching this function.
    """
    # Validate user exists
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise ValueError(f"User with id={user_id} does not exist or is inactive.")

    # Optionally validate department if provided
    if department_id is not None:
        dept = db.query(Department).filter(
            Department.id == department_id, Department.is_active == True
        ).first()
        if dept is None:
            raise ValueError(f"Department with id={department_id} does not exist or is inactive.")

    complaint = Complaint(
        user_id=user_id,
        department_id=department_id,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=address,
        category=category,
        subcategory=subcategory,
        status=ComplaintStatus.SUBMITTED.value,
    )
    db.add(complaint)
    db.flush()  # Get complaint.id without committing

    # Initial status history record
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=None,
        new_status=ComplaintStatus.SUBMITTED.value,
        changed_by=user_id,
        note="Complaint submitted by citizen.",
    )
    db.add(history)

    # Lifecycle Notification Event
    notification_service.create_notification(
        db,
        user_id=user_id,
        complaint_id=complaint.id,
        notification_type=NotificationType.COMPLAINT_CREATED.value,
        title="Complaint Submitted",
        message=f"Your complaint '{title}' has been successfully submitted.",
    )

    db.commit()
    db.refresh(complaint)
    return complaint



def get_complaint_by_public_id(db: Session, public_id: str) -> Optional[Complaint]:
    """
    Retrieve a complaint by its public UUID with all relationships eagerly loaded.
    Returns None if not found.
    """
    return (
        db.query(Complaint)
        .options(
            joinedload(Complaint.user),
            joinedload(Complaint.department),
            joinedload(Complaint.attachments),
            joinedload(Complaint.status_history),
            joinedload(Complaint.ai_analyses),
        )
        .filter(Complaint.public_id == public_id)
        .first()
    )


def list_complaints(
    db: Session,
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    department_id: Optional[int] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Return a paginated list of complaints with optional filters.
    page_size is capped at 100 to prevent abuse.
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    query = db.query(Complaint).options(
        joinedload(Complaint.department),
    )

    filters = []
    if status:
        filters.append(Complaint.status == status)
    if priority:
        filters.append(Complaint.priority == priority)
    if category:
        filters.append(Complaint.category == category)
    if department_id is not None:
        filters.append(Complaint.department_id == department_id)
    if user_id is not None:
        filters.append(Complaint.user_id == user_id)

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    items = (
        query.order_by(Complaint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }


def update_complaint_status(
    db: Session,
    *,
    public_id: str,
    new_status: ComplaintStatus,
    note: Optional[str] = None,
    changed_by: Optional[int] = None,
) -> Complaint:
    """
    Transition a complaint's status. Validates the transition is legal,
    records history, and manages resolved_at timestamps.
    """
    complaint = (
        db.query(Complaint).filter(Complaint.public_id == public_id).first()
    )
    if complaint is None:
        raise LookupError(f"Complaint '{public_id}' not found.")

    current_status = ComplaintStatus(complaint.status)

    # Validate transition
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Transition from '{current_status.value}' to '{new_status.value}' is not permitted. "
            f"Allowed: {[s.value for s in allowed]}"
        )

    old_status_value = complaint.status
    complaint.status = new_status.value
    complaint.updated_at = utc_now()

    # Manage resolved_at
    if new_status == ComplaintStatus.RESOLVED:
        complaint.resolved_at = utc_now()
    elif new_status == ComplaintStatus.REOPENED:
        complaint.resolved_at = None  # Clear resolution timestamp on reopen

    # Validate changed_by user if provided
    if changed_by is not None:
        changer = db.query(User).filter(User.id == changed_by).first()
        if changer is None:
            changed_by = None  # Silently clear rather than hard-fail

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=old_status_value,
        new_status=new_status.value,
        changed_by=changed_by,
        note=note,
    )
    db.add(history)

    # Determine notification type & message based on transition
    if new_status == ComplaintStatus.RESOLVED:
        ntype = NotificationType.COMPLAINT_RESOLVED.value
        title_str = "Complaint Resolved"
    elif new_status == ComplaintStatus.REOPENED:
        ntype = NotificationType.COMPLAINT_REOPENED.value
        title_str = "Complaint Reopened"
    else:
        ntype = NotificationType.STATUS_CHANGED.value
        title_str = f"Complaint Status: {new_status.value.replace('_', ' ').title()}"

    notification_service.create_notification(
        db,
        user_id=complaint.user_id,
        complaint_id=complaint.id,
        notification_type=ntype,
        title=title_str,
        message=f"Status changed from '{old_status_value}' to '{new_status.value}'.",
    )

    db.commit()
    db.refresh(complaint)
    return complaint


def assign_department(
    db: Session,
    *,
    public_id: str,
    department_id: int,
) -> Complaint:
    """
    Assign or reassign a department to a complaint.
    Validates both complaint and department exist.
    """
    complaint = db.query(Complaint).filter(Complaint.public_id == public_id).first()
    if complaint is None:
        raise LookupError(f"Complaint '{public_id}' not found.")

    dept = db.query(Department).filter(
        Department.id == department_id, Department.is_active == True
    ).first()
    if dept is None:
        raise ValueError(f"Department with id={department_id} does not exist or is inactive.")

    complaint.department_id = department_id
    complaint.updated_at = utc_now()

    notification_service.create_notification(
        db,
        user_id=complaint.user_id,
        complaint_id=complaint.id,
        notification_type=NotificationType.DEPARTMENT_ASSIGNED.value,
        title="Department Assigned",
        message=f"Your complaint has been assigned to the '{dept.name}' department.",
    )

    db.commit()
    db.refresh(complaint)
    return complaint

