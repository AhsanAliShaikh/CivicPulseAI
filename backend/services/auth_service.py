"""
CivicPulse AI — Auth Service Layer (Phase 6)
Handles user registration with password hashing, credential authentication,
and JWT token generation.
"""
from typing import Optional, Dict
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.enums import UserRole
from backend.core.security import hash_password, verify_password, create_access_token

import logging

logger = logging.getLogger(__name__)


def register_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: UserRole = UserRole.CITIZEN,
) -> User:
    """
    Register a new user with hashed password. Raises ValueError if email is already taken.
    """
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is not None:
        raise ValueError(f"User with email '{email}' already exists.")

    hashed_pw = hash_password(password)
    user = User(
        name=name,
        email=email,
        role=role.value,
        password_hash=hashed_pw,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered new user id=%s email=%s role=%s", user.id, user.email, user.role)
    return user


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate user by email and password.
    Returns User if credentials match and account is active, else None.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        return None
    if not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def generate_user_token(user: User) -> Dict[str, str]:
    """
    Generate JWT access token for an authenticated user.
    """
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }
    access_token = create_access_token(payload)
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
