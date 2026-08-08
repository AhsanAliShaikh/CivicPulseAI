from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.core.database import get_db, Base, engine
import backend.models  # noqa: F401

router = APIRouter(prefix="/api/v1/system", tags=["System Verification"])

@router.get("/database-summary")
def get_database_summary(db: Session = Depends(get_db)):
    """
    Returns summary of registered database entities and current record counts.
    Useful for system verification during development.
    """
    table_counts = {}
    registered_tables = list(Base.metadata.tables.keys())

    for table_name in registered_tables:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            table_counts[table_name] = result
        except Exception:
            table_counts[table_name] = "error/uninitialized"

    return {
        "status": "online",
        "database_engine": engine.name,
        "total_tables": len(registered_tables),
        "tables": table_counts
    }
