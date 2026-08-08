from enum import Enum

class UserRole(str, Enum):
    CITIZEN = "citizen"
    STAFF = "staff"
    ADMIN = "admin"

class ComplaintStatus(str, Enum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    REOPENED = "reopened"

class ComplaintPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationType(str, Enum):
    COMPLAINT_CREATED = "complaint_created"
    STATUS_CHANGED = "status_changed"
    AI_ANALYSIS_RECORDED = "ai_analysis_recorded"
    DEPARTMENT_ASSIGNED = "department_assigned"
    COMPLAINT_RESOLVED = "complaint_resolved"
    COMPLAINT_REOPENED = "complaint_reopened"

