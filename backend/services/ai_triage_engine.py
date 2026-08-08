"""
CivicPulse AI — Local Deterministic AI Triage Engine (Phase 8)
Rule-based NLP classification engine that analyzes complaint text,
determines category, priority, confidence, summary, reasoning,
and resolves suggested municipal department without external AI dependencies.
"""
import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.complaint import Complaint
from backend.models.department import Department
from backend.models.ai_analysis import AIAnalysis
from backend.services import ai_analysis_service

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification Rules mapping keyword groups to department codes and metadata
# ---------------------------------------------------------------------------
CLASSIFICATION_RULES = [
    {
        "code": "WTR",
        "category": "Water & Sewage Services",
        "priority": "high",
        "confidence": 0.95,
        "keywords": ["water", "leak", "pipe", "sewage", "drain", "flood", "overflow", "burst"],
    },
    {
        "code": "ELE",
        "category": "Electricity & Power",
        "priority": "critical",
        "confidence": 0.94,
        "keywords": ["power", "electricity", "transformer", "grid", "voltage", "outage", "sparks"],
    },
    {
        "code": "RD",
        "category": "Roads & Transport Infrastructure",
        "priority": "high",
        "confidence": 0.92,
        "keywords": ["pothole", "road", "asphalt", "pavement", "sidewalk", "tarmac"],
    },
    {
        "code": "TRF",
        "category": "Traffic Management",
        "priority": "high",
        "confidence": 0.90,
        "keywords": ["traffic", "signal", "parking", "signage", "congestion", "intersection", "speeding"],
    },
    {
        "code": "STL",
        "category": "Street Lighting",
        "priority": "medium",
        "confidence": 0.90,
        "keywords": ["lamp", "light", "dark", "street light", "bulb", "illumination", "darkness"],
    },
    {
        "code": "SAN",
        "category": "Sanitation & Waste Management",
        "priority": "medium",
        "confidence": 0.88,
        "keywords": ["garbage", "trash", "waste", "dump", "rubbish", "litter", "smell", "bin"],
    },
    {
        "code": "PRK",
        "category": "Parks & Recreation",
        "priority": "low",
        "confidence": 0.85,
        "keywords": ["park", "bench", "tree", "playground", "grass", "garden", "lawn"],
    },
]


def classify_text(text: str) -> Dict[str, Any]:
    """
    Deterministic rule-based classification function using word boundaries.
    Returns category, priority, confidence, summary, reasoning, and department code.
    """
    text_lower = text.lower()

    for rule in CLASSIFICATION_RULES:
        for kw in rule["keywords"]:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text_lower):
                return {
                    "code": rule["code"],
                    "category": rule["category"],
                    "priority": rule["priority"],
                    "confidence": rule["confidence"],
                    "summary": f"Automated triage classified as '{rule['category']}' with {rule['priority']} priority.",
                    "reasoning": f"Matched key term '{kw}' in complaint title/description.",
                }

    # Fallback to General Municipal Services
    return {
        "code": "GEN",
        "category": "General Municipal Services",
        "priority": "medium",
        "confidence": 0.70,
        "summary": "Automated triage assigned fallback category 'General Municipal Services'.",
        "reasoning": "No specific category keywords matched complaint text.",
    }


def run_triage(db: Session, complaint: Complaint) -> AIAnalysis:
    """
    Execute AI triage for a given complaint.
    Resolves department by code, invokes ai_analysis_service.create_ai_analysis,
    which persists AIAnalysis, updates complaint ai_* fields, auto-routes department,
    and generates notification.
    """
    combined_text = f"{complaint.title} {complaint.description}"
    result = classify_text(combined_text)

    # Resolve department ID by code from database
    suggested_dept_id: Optional[int] = None
    dept = db.query(Department).filter(
        Department.code == result["code"],
        Department.is_active == True,  # noqa: E712
    ).first()
    if dept:
        suggested_dept_id = dept.id

    analysis = ai_analysis_service.create_ai_analysis(
        db,
        complaint=complaint,
        model_name="civicpulse-triage-v1",
        model_version="1.0",
        category=result["category"],
        priority=result["priority"],
        confidence=result["confidence"],
        summary=result["summary"],
        reasoning=result["reasoning"],
        suggested_department_id=suggested_dept_id,
    )
    return analysis
