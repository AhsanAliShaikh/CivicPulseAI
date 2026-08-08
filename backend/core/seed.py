from sqlalchemy.orm import Session
from backend.models.department import Department
import logging

logger = logging.getLogger(__name__)

DEFAULT_DEPARTMENTS = [
    {"name": "Sanitation & Waste Management", "code": "SAN", "description": "Garbage collection, street cleaning, and waste management services."},
    {"name": "Roads & Transport Infrastructure", "code": "RD", "description": "Potholes, road repair, sidewalks, and traffic signal maintenance."},
    {"name": "Water & Sewage Services", "code": "WTR", "description": "Water supply leaks, drainage, sewage backups, and pipe repairs."},
    {"name": "Electricity & Power", "code": "ELE", "description": "Power outages, transformer faults, and electrical grid issues."},
    {"name": "Street Lighting", "code": "STL", "description": "Broken street lamps, dark corridors, and lighting repairs."},
    {"name": "Parks & Recreation", "code": "PRK", "description": "Public park maintenance, fallen trees, and playground safety."},
    {"name": "Traffic Management", "code": "TRF", "description": "Illegal parking, signages, signal timing, and traffic hazards."},
    {"name": "General Municipal Services", "code": "GEN", "description": "General civic inquiries, noise complaints, and uncategorized issues."},
]

def seed_default_departments(db: Session) -> list:
    """
    Explicitly callable seed function to insert initial core municipal departments if empty.
    NOTE: Not called automatically on startup or during test runs.
    """
    existing_count = db.query(Department).count()
    if existing_count > 0:
        logger.info(f"Seed skipped: {existing_count} departments already exist.")
        return []

    created_departments = []
    for dept_data in DEFAULT_DEPARTMENTS:
        dept = Department(
            name=dept_data["name"],
            code=dept_data["code"],
            description=dept_data["description"],
            is_active=True
        )
        db.add(dept)
        created_departments.append(dept)

    db.commit()
    for dept in created_departments:
        db.refresh(dept)
    
    logger.info(f"Successfully seeded {len(created_departments)} default municipal departments.")
    return created_departments
