"""
CivicPulse AI — Municipal Department API Routes (Phase 8)
Provides department listing, retrieval, and administrative department creation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.core.database import get_db
from backend.core.deps import require_roles
from backend.models.department import Department
from backend.models.enums import UserRole
from backend.schemas.department import DepartmentCreate, DepartmentRead

router = APIRouter(
    prefix="/api/v1/departments",
    tags=["Departments"],
)


@router.get(
    "",
    response_model=List[DepartmentRead],
    summary="List all active municipal departments",
)
def list_departments(db: Session = Depends(get_db)):
    """Public endpoint returning list of active departments."""
    return (
        db.query(Department)
        .filter(Department.is_active == True)  # noqa: E712
        .order_by(Department.name.asc())
        .all()
    )


@router.get(
    "/{department_id}",
    response_model=DepartmentRead,
    summary="Get department details by ID",
)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
):
    """Public endpoint returning department detail by ID."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if dept is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id={department_id} not found.",
        )
    return dept


@router.post(
    "",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new municipal department (Admin only)",
)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _current_admin=Depends(require_roles(UserRole.ADMIN.value)),
):
    """Admin-only endpoint to create a new department. Checks unique department code."""
    existing = (
        db.query(Department)
        .filter(Department.code == payload.code.strip().upper())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with code '{payload.code.strip().upper()}' already exists.",
        )

    dept = Department(
        name=payload.name.strip(),
        code=payload.code.strip().upper(),
        description=payload.description.strip() if payload.description else None,
        is_active=True,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept
