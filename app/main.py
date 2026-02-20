"""
PhishLens — FastAPI Application Factory

Main application entry point with lifespan events, CORS, rate limiting,
and router registration.
"""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before importing settings
load_dotenv()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

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

    # Seed predefined templates
    try:
        from app.database import SessionLocal
        from app.services.seed_templates import seed_templates

        db = SessionLocal()
        count = seed_templates(db)
        db.close()
        if count > 0:
            logger.info(f"Seeded {count} predefined templates")
        else:
            logger.info("All predefined templates already exist")
    except Exception as e:
        logger.warning(f"Template seeding skipped: {e}")

    yield

    logger.info("Shutting down PhishLens API")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP address.

    Uses a sliding window approach. Limits are configured per role
    in settings (rate_limit_researcher, rate_limit_admin).
    """

    def __init__(self, app, default_limit: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/ready", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Get client IP
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )

        now = time.time()
        # Clean old entries
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if now - t < self.window_seconds
        ]

        if len(self.requests[client_ip]) >= self.default_limit:
            return Response(
                content='{"detail": "Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response


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

# Rate Limiting Middleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=settings.rate_limit_researcher,
    window_seconds=60,
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
        from app.database import SessionLocal
        from sqlalchemy import text as sa_text

        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": str(e)}


# Initialize logging
setup_logging()
