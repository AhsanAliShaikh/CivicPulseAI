"""
CivicPulse AI — Reusable Security Dependencies (Phase 6)
Provides current user extraction, token validation, and role-based authorization checks.
"""
from typing import Callable, Optional, Sequence, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.models.user import User
from backend.models.enums import UserRole

# HTTP Bearer scheme for Swagger UI & header parsing
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate JWT access token from Authorization header.
    Returns authenticated User or raises 401 Unauthorized.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional user extraction. Returns User if valid token is provided, else None.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def require_roles(*allowed_roles: str) -> Callable:
    """
    Dependency factory enforcing role-based access control (RBAC).
    Usage: Depends(require_roles(UserRole.STAFF.value, UserRole.ADMIN.value))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User role '{current_user.role}' lacks required permissions.",
            )
        return current_user

    return role_checker


def verify_complaint_ownership(complaint: Any, user: Optional[User]) -> None:
    """
    Verify that an authenticated user has permission to access or modify a complaint.
    Admins & Staff can access any complaint; Citizens can only access their own.
    """
    if user is None:
        return
    if user.role in (UserRole.ADMIN.value, UserRole.STAFF.value):
        return
    if complaint.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to access or modify this complaint.",
        )


def verify_user_access(target_user_id: int, user: Optional[User]) -> None:
    """
    Verify that an authenticated user has permission to access target_user_id's resources.
    """
    if user is None:
        return
    if user.role in (UserRole.ADMIN.value, UserRole.STAFF.value):
        return
    if user.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to access another user's private data.",
        )

