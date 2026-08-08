"""
CivicPulse AI — AI Analysis Service (Phase 3)
Handles storage of AI triage results and complaint field updates.
No external AI calls are made here; this layer receives already-computed
results from an upstream AI pipeline and persists them.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models.ai_analysis import AIAnalysis
from backend.models.complaint import Complaint
from backend.models.department import Department
from backend.models.enums import NotificationType
from backend.services import notification_service

import logging

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_ai_analysis(
    db: Session,
    *,
    complaint: Complaint,
    model_name: str,
    model_version: str,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    confidence: Optional[float] = None,
    summary: Optional[str] = None,
    reasoning: Optional[str] = None,
    suggested_department_id: Optional[int] = None,
) -> AIAnalysis:
    """
    Persist an AI analysis result for a complaint.

    Side-effects:
    - Updates complaint.ai_category / ai_priority / ai_confidence / ai_summary
      when the new analysis has higher (or equal) confidence than the current value.
    - Auto-assigns the suggested department when the complaint currently has none
      and the department exists and is active.
    - Triggers AI_ANALYSIS_RECORDED notification event.
    """
    analysis = AIAnalysis(
        complaint_id=complaint.id,
        model_name=model_name,
        model_version=model_version,
        category=category,
        priority=priority,
        confidence=confidence,
        summary=summary,
        reasoning=reasoning,
    )
    db.add(analysis)

    # Update complaint ai_* fields: accept if confidence is higher than current
    current_conf = complaint.ai_confidence if complaint.ai_confidence is not None else -1.0
    new_conf = confidence if confidence is not None else 0.0
    if new_conf >= current_conf:
        if category is not None:
            complaint.ai_category = category
        if priority is not None:
            complaint.ai_priority = priority
        if confidence is not None:
            complaint.ai_confidence = confidence
        if summary is not None:
            complaint.ai_summary = summary
        complaint.updated_at = utc_now()

    # Auto-assign department if complaint has none and suggestion is valid
    if suggested_department_id is not None and complaint.department_id is None:
        dept = db.query(Department).filter(
            Department.id == suggested_department_id,
            Department.is_active == True,  # noqa: E712
        ).first()
        if dept is not None:
            complaint.department_id = suggested_department_id
            complaint.updated_at = utc_now()
            logger.info(
                "Auto-routed complaint %s to department %s via AI suggestion",
                complaint.public_id,
                suggested_department_id,
            )
        else:
            logger.warning(
                "Suggested department_id=%s for complaint %s not found or inactive; skipping auto-route",
                suggested_department_id,
                complaint.public_id,
            )

    # Trigger Lifecycle Notification Event
    notification_service.create_notification(
        db,
        user_id=complaint.user_id,
        complaint_id=complaint.id,
        notification_type=NotificationType.AI_ANALYSIS_RECORDED.value,
        title="AI Analysis Complete",
        message=f"AI classification complete for complaint '{complaint.title}'.",
    )

    db.commit()
    db.refresh(analysis)
    db.refresh(complaint)
    return analysis



def get_analyses_for_complaint(
    db: Session,
    complaint_id: int,
) -> List[AIAnalysis]:
    """Return all AI analysis records for a complaint, newest first."""
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.complaint_id == complaint_id)
        .order_by(AIAnalysis.created_at.desc())
        .all()
    )
