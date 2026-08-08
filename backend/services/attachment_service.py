"""
CivicPulse AI — Attachment Service Layer (Phase 4)
Handles attachment creation, listing, and metadata retrieval for complaints.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.models.attachment import ComplaintAttachment
from backend.models.complaint import Complaint

import logging

logger = logging.getLogger(__name__)


def create_attachment(
    db: Session,
    *,
    complaint_id: int,
    file_name: str,
    file_url: str,
    file_type: str,
    file_size: int,
) -> ComplaintAttachment:
    """
    Create a new attachment record associated with a complaint.
    """
    attachment = ComplaintAttachment(
        complaint_id=complaint_id,
        file_name=file_name,
        file_url=file_url,
        file_type=file_type,
        file_size=file_size,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def get_attachments_for_complaint(
    db: Session,
    complaint_id: int,
) -> List[ComplaintAttachment]:
    """
    Return all attachments belonging to a complaint, ordered by creation timestamp.
    """
    return (
        db.query(ComplaintAttachment)
        .filter(ComplaintAttachment.complaint_id == complaint_id)
        .order_by(ComplaintAttachment.created_at.asc())
        .all()
    )


def get_attachment_by_id(
    db: Session,
    attachment_id: int,
    complaint_id: Optional[int] = None,
) -> Optional[ComplaintAttachment]:
    """
    Retrieve an attachment by ID. If complaint_id is provided, ensures
    the attachment belongs to that specific complaint.
    """
    query = db.query(ComplaintAttachment).filter(ComplaintAttachment.id == attachment_id)
    if complaint_id is not None:
        query = query.filter(ComplaintAttachment.complaint_id == complaint_id)
    return query.first()
