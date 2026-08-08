"""
CivicPulse AI — Authentication API Routes (Phase 6)
Provides user registration, password authentication login, and current user retrieval.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.auth import UserRegister, UserLogin, TokenResponse
from backend.schemas.user import UserRead
from backend.services import auth_service

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a citizen, staff, or admin account with hashed credentials and returns an access token.",
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    try:
        user = auth_service.register_user(
            db,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role=payload.role,
        )
        token_data = auth_service.generate_user_token(user)
        return TokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data["token_type"],
            user=UserRead.model_validate(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and obtain access token",
    description="Validates email and password credentials, returning a JWT bearer token.",
)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate_user(
        db,
        email=payload.email,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = auth_service.generate_user_token(user)
    return TokenResponse(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        user=UserRead.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user
