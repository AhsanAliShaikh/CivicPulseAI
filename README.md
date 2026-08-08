# CivicPulse AI Backend Platform

An intelligent, production-ready civic issue reporting and municipal intelligence backend built with FastAPI, SQLAlchemy, JWT Authentication, Role-based Access Control (RBAC), and automated local AI triage.

---

## Complete Features & Capabilities (Phases 0–9)

- **Authentication & Security (Phase 6 & 7)**:
  - PBKDF2-HMAC-SHA256 password hashing & HS256 JWT access token verification.
  - Role-based Access Control (`citizen`, `staff`, `admin`).
  - Strict Complaint & Notification Ownership enforcement: Citizens can only access their own private data.
- **Complaint Lifecycle Management (Phase 1 & 2)**:
  - Complaint submission with geolocation, address, category, and department assignment.
  - Strict valid status transitions (`submitted` → `acknowledged` → `assigned` → `in_progress` → `resolved` / `rejected` / `reopened`).
  - Full audit logging in status history table.
- **Local AI Triage Engine (Phase 8)**:
  - Local, deterministic rule-based NLP classification across 8 municipal domains (Roads, Water, Lighting, Sanitation, Parks, Traffic, Electricity, General).
  - Department auto-routing based on keyword confidence score.
  - Manual AI triage trigger endpoint (`POST /api/v1/complaints/{public_id}/triage`) for staff/admin.
- **Municipal Department Management (Phase 8)**:
  - Public listing and detail retrieval of municipal departments.
  - Admin department management (`POST /api/v1/departments`).
- **Attachments & Notifications (Phase 4 & 5)**:
  - Media attachment registration and complaint association.
  - Automatic notification event triggers across complaint lifecycle actions.
- **Production Operations & Containerization (Phase 9)**:
  - Structured health probes (`GET /health`) checking database connectivity.
  - System database entity diagnostics (`GET /api/v1/system/database-summary`).
  - Multi-stage Docker containerization and CORS support.

---

## Directory Structure

```
CivicPulse-AI/
├── backend/
│   ├── main.py                   # FastAPI app entry point & router registration
│   ├── api/
│   │   └── routes/               # API route handlers (auth, complaints, departments, notifications, health, system)
│   ├── core/                     # Database engine, Pydantic settings, security & RBAC dependencies
│   ├── models/                   # SQLAlchemy domain models (User, Complaint, Department, AIAnalysis, Notification, Attachment)
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic & AI triage engine (complaint_service, ai_triage_engine, etc.)
│   ├── templates/                # Jinja2 template pages
│   └── static/                   # Static assets
├── tests/                        # 9 test modules (102 tests, 100% pass rate)
├── Dockerfile                    # Production multi-stage Docker build
├── .dockerignore                 # Container build exclusions
├── .env.example                  # Environment configuration template
├── requirements.txt              # Dependency specifications
└── README.md                     # Documentation
```

---

## Setup & Local Run Instructions

### 1. Virtual Environment Setup
```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```env
PROJECT_NAME="CivicPulse AI"
VERSION="1.0.0"
ENVIRONMENT="production"
DEBUG=False
DATABASE_URL="sqlite:///./civicpulse.db"
SECRET_KEY="super-secret-production-key-change-me"
```

### 3. Local Development Run
```bash
.\.venv\Scripts\python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Seed Default Departments (Required on First Run)

After the application starts for the first time, seed the 8 default municipal departments so AI triage auto-routing works correctly:

```python
# Run once after first startup — uses the existing backend/core/seed.py
from backend.core.database import SessionLocal, init_db
from backend.core.seed import seed_default_departments

init_db()
db = SessionLocal()
seed_default_departments(db)
db.close()
```

Or run it as a one-liner from the project root:
```bash
.\.venv\Scripts\python -c "from backend.core.database import SessionLocal, init_db; from backend.core.seed import seed_default_departments; init_db(); db=SessionLocal(); seed_default_departments(db); db.close(); print('Departments seeded.')"
```

Alternatively, an Admin user can `POST /api/v1/departments` to create departments individually.

---

## Production Docker Deployment

### 1. Build Container Image
```bash
docker build -t civicpulse-ai:latest .
```

### 2. Run Production Container
```bash
docker run -d \
  --name civicpulse-backend \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DEBUG=False \
  -e SECRET_KEY="your-production-secret-key" \
  civicpulse-ai:latest
```

---

## Testing & Verification

Execute the complete automated test suite (102 tests):
```bash
.\.venv\Scripts\pytest
```

---

## API Summary

| Category | Endpoint | Method | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| **System** | `/health` | GET | Public | System & database health probe |
| **System** | `/api/v1/system/database-summary` | GET | Public | DB record count & table diagnostics |
| **Auth** | `/api/v1/auth/register` | POST | Public | Register new user account |
| **Auth** | `/api/v1/auth/login` | POST | Public | Authenticate user & receive JWT token |
| **Auth** | `/api/v1/auth/me` | GET | Authenticated | Retrieve current user profile |
| **Departments** | `/api/v1/departments` | GET | Public | List active municipal departments |
| **Departments** | `/api/v1/departments/{id}` | GET | Public | Get department details |
| **Departments** | `/api/v1/departments` | POST | Admin | Create a new department |
| **Complaints** | `/api/v1/complaints` | POST | Public / Auth | Submit a citizen complaint |
| **Complaints** | `/api/v1/complaints` | GET | Public / Auth | List complaints (filtered/paginated) |
| **Complaints** | `/api/v1/complaints/{public_id}` | GET | Public / Owner | Retrieve complaint details |
| **Complaints** | `/api/v1/complaints/{public_id}/status` | PATCH | Owner / Staff / Admin | Update complaint status |
| **Complaints** | `/api/v1/complaints/{public_id}/department` | PATCH | Staff / Admin | Assign department to complaint |
| **Complaints** | `/api/v1/complaints/{public_id}/triage` | POST | Staff / Admin | Trigger manual AI triage analysis |
| **Notifications**| `/api/v1/notifications/user/{user_id}` | GET | Owner / Staff / Admin | Get user notification list |
