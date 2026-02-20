"""
PhishLens — FastAPI Application Factory

Main application entry point with lifespan events, CORS, and router registration.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before importing settings
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1 import api_router
from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger = get_logger()
    logger.info("Starting PhishLens API", version=settings.app_version, env=settings.app_env)

    # Create tables if in dev mode (production uses Alembic migrations)
    if settings.app_env == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (dev mode)")

    yield

    logger.info("Shutting down PhishLens API")


# Create the FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "PhishLens — Web Application for Phishing Message Generation "
        "Using Large Language Models. For authorized cybersecurity research only."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)


# --- Public Health Check Endpoints ---


@app.get("/health", tags=["Health"])
def health_check():
    """Public health check endpoint."""
    return {"status": "ok", "service": "phishlens-api"}


@app.get("/ready", tags=["Health"])
def readiness_check():
    """Readiness probe — checks database connectivity."""
    from app.database import SessionLocal

    try:
        db = SessionLocal()
        db.execute("SELECT 1")  # type: ignore
        db.close()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": str(e)}


# Initialize logging
setup_logging()
