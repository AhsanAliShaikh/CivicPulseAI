from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Configure engine arguments based on database type (SQLite vs Postgres/other)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency for obtaining database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_database_connection() -> dict:
    """
    Safely checks database connectivity.
    Returns status dict without throwing exceptions or crashing app.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "connected", "database": "sqlite" if "sqlite" in settings.DATABASE_URL else "relational"}
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        return {"status": "disconnected", "error": str(e)}

def init_db():
    """Initialize database tables (declarative Base metadata)."""
    try:
        import backend.models  # noqa: F401 - Register models with Base.metadata
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
