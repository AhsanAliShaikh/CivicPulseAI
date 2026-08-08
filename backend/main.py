from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import os

from backend.core.config import settings
from backend.core.database import init_db
from backend.api.routes import health, system, complaints, notifications, auth, departments



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB schema foundation
    init_db()
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "AI-powered civic issue reporting and intelligence platform. "
        "Citizens submit complaints; AI classifies, prioritises, and routes them "
        "to the correct municipal department."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for production & client integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve absolute path for static & templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 Templates setup
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(departments.router)
app.include_router(complaints.router)
app.include_router(notifications.router)



# ---------------------------------------------------------------------------
# UI Page Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["UI"])
async def render_landing_page(request: Request):
    """Renders the CivicPulse AI landing page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )


@app.get("/report", tags=["UI"])
async def render_report_page(request: Request):
    """Renders the citizen complaint submission page."""
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
        },
    )


@app.get("/track", tags=["UI"])
async def render_track_page(request: Request):
    """Renders the complaint tracking page."""
    return templates.TemplateResponse(
        request=request,
        name="track.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
        },
    )
