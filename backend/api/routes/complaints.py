"""
CivicPulse AI — Complaint API Routes
Thin route handlers; all business logic delegated to complaint_service.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.core.database import get_db
from backend.core.deps import get_optional_current_user, verify_complaint_ownership, require_roles
from backend.models.user import User
from backend.models.enums import ComplaintStatus, ComplaintPriority, UserRole
from backend.schemas.complaint import (
    ComplaintCreate,
    ComplaintRead,
    ComplaintListResponse,
    ComplaintSummary,
    StatusUpdateRequest,
    DepartmentAssignRequest,
)
from backend.schemas.ai_analysis import AIAnalysisCreate, AIAnalysisRead
from backend.schemas.attachment import ComplaintAttachmentCreate, ComplaintAttachmentRead
from backend.schemas.notification import NotificationRead
from backend.services import complaint_service, ai_analysis_service, attachment_service, notification_service, ai_triage_engine

router = APIRouter(
    prefix="/api/v1/complaints",
    tags=["Complaints"],
)


@router.post(
    "",
    response_model=ComplaintRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new civic complaint",
    description=(
        "Creates a new citizen complaint. Validates the user, persists the complaint, "
        "and records the initial SUBMITTED status history entry. "
        "AI classification will be triggered in Phase 3."
    ),
)
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    user_id = current_user.id if current_user else payload.user_id
    try:
        complaint = complaint_service.create_complaint(
            db,
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            latitude=payload.latitude,
            longitude=payload.longitude,
            address=payload.address,
            category=payload.category,
            subcategory=payload.subcategory,
            department_id=payload.department_id,
        )
        return complaint
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=ComplaintListResponse,
    summary="List complaints with optional filters and pagination",
)
def list_complaints(
    complaint_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    if current_user and current_user.role == UserRole.CITIZEN.value:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have permission to access another user's private data.",
            )
        if user_id is None:
            user_id = current_user.id

    result = complaint_service.list_complaints(
        db,
        status=complaint_status,
        priority=priority,
        category=category,
        department_id=department_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return ComplaintListResponse(
        items=[ComplaintSummary.model_validate(c) for c in result["items"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
        pages=result["pages"],
    )


@router.get(
    "/{public_id}",
    response_model=ComplaintRead,
    summary="Retrieve a complaint by its public ID",
)
def get_complaint(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with public_id '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    return complaint


@router.patch(
    "/{public_id}/status",
    response_model=ComplaintRead,
    summary="Update complaint status",
    description=(
        "Transitions a complaint's status. Validates the transition is permitted, "
        "records the full status history, and manages resolved_at timestamps."
    ),
)
def update_status(
    public_id: str,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    changed_by = current_user.id if current_user else payload.changed_by

    try:
        updated = complaint_service.update_complaint_status(
            db,
            public_id=public_id,
            new_status=payload.status,
            note=payload.note,
            changed_by=changed_by,
        )
        return updated
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch(
    "/{public_id}/department",
    response_model=ComplaintRead,
    summary="Assign or reassign a department to a complaint",
    description=(
        "Assigns a department to an existing complaint. "
        "This endpoint will later be called by the AI department recommendation system."
    ),
)
def assign_department(
    public_id: str,
    payload: DepartmentAssignRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    if current_user and current_user.role == UserRole.CITIZEN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Citizens cannot assign departments.",
        )
    try:
        complaint = complaint_service.assign_department(
            db,
            public_id=public_id,
            department_id=payload.department_id,
        )
        return complaint
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{public_id}/ai-analysis",
    response_model=AIAnalysisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record AI analysis result for a complaint",
    description=(
        "Persists an AI analysis result for the complaint. "
        "Updates complaint level AI summary/confidence/category/priority fields "
        "and auto-routes to suggested department if unassigned."
    ),
)
def record_ai_analysis(
    public_id: str,
    payload: AIAnalysisCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    if current_user and current_user.role == UserRole.CITIZEN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Citizens cannot record AI analysis.",
        )
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    try:
        analysis = ai_analysis_service.create_ai_analysis(
            db,
            complaint=complaint,
            model_name=payload.model_name,
            model_version=payload.model_version,
            category=payload.category,
            priority=payload.priority,
            confidence=payload.confidence,
            summary=payload.summary,
            reasoning=payload.reasoning,
            suggested_department_id=payload.suggested_department_id,
        )
        return analysis
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{public_id}/ai-analysis",
    response_model=List[AIAnalysisRead],
    summary="Get all AI analyses for a complaint",
)
def get_ai_analyses(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    return ai_analysis_service.get_analyses_for_complaint(db, complaint.id)


# ---------------------------------------------------------------------------
# Attachment Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{public_id}/attachments",
    response_model=ComplaintAttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register an attachment for a complaint",
    description="Adds media/file attachment metadata to an existing complaint.",
)
def create_attachment(
    public_id: str,
    payload: ComplaintAttachmentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    attachment = attachment_service.create_attachment(
        db,
        complaint_id=complaint.id,
        file_name=payload.file_name,
        file_url=payload.file_url,
        file_type=payload.file_type,
        file_size=payload.file_size,
    )
    return attachment


@router.get(
    "/{public_id}/attachments",
    response_model=List[ComplaintAttachmentRead],
    summary="List all attachments for a complaint",
)
def list_attachments(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    return attachment_service.get_attachments_for_complaint(db, complaint.id)


@router.get(
    "/{public_id}/attachments/{attachment_id}",
    response_model=ComplaintAttachmentRead,
    summary="Retrieve specific attachment metadata",
)
def get_attachment(
    public_id: str,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    attachment = attachment_service.get_attachment_by_id(
        db,
        attachment_id=attachment_id,
        complaint_id=complaint.id,
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment with id={attachment_id} not found for complaint '{public_id}'.",
        )
    return attachment


# ---------------------------------------------------------------------------
# Notification Event Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/{public_id}/notifications",
    response_model=List[NotificationRead],
    summary="List all notification events for a complaint",
)
def list_complaint_notifications(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    verify_complaint_ownership(complaint, current_user)
    return notification_service.get_complaint_notifications(db, complaint.id)


@router.post(
    "/{public_id}/triage",
    response_model=AIAnalysisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger manual AI triage analysis for a complaint (Staff/Admin only)",
)
def trigger_ai_triage(
    public_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.STAFF.value, UserRole.ADMIN.value)),
):
    complaint = complaint_service.get_complaint_by_public_id(db, public_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{public_id}' not found.",
        )
    return ai_triage_engine.run_triage(db, complaint)





