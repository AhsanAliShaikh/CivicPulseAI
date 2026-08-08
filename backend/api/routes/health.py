from fastapi import APIRouter
from backend.core.config import settings
from backend.core.database import check_database_connection

router = APIRouter()

@router.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint for CivicPulse AI.
    Verifies service availability, version, environment, and database connectivity.
    """
    db_check = check_database_connection()
    overall_status = "healthy" if db_check.get("status") == "connected" else "degraded"

    return {
        "status": overall_status,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_check
    }
