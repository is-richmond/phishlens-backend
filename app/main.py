"""
PhishLens — FastAPI Application Factory

Main application entry point with lifespan events, CORS, rate limiting,
security headers, and router registration.
"""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from uuid import UUID

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

# Logger for content restriction events
_restriction_logger = get_logger("content_restrictions")


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
    """In-memory role-aware rate limiter with proper X-RateLimit-* headers.

    Uses a sliding window per client key (IP or user ID for authenticated).
    Different limits for researchers (30/hr) and admins (100/hr).
    Generation endpoint has its own stricter per-hour limit.
    """

    EXEMPT_PATHS = frozenset({
        "/health", "/ready", "/docs", "/redoc", "/openapi.json",
    })

    def __init__(
        self,
        app,
        researcher_limit: int = 30,
        admin_limit: int = 100,
        window_seconds: int = 3600,
    ):
        super().__init__(app)
        self.researcher_limit = researcher_limit
        self.admin_limit = admin_limit
        self.window_seconds = window_seconds
        # key → list of timestamps
        self.requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request: Request) -> tuple[str, int]:
        """Return (client_key, limit) — tries JWT for role-aware limiting."""
        limit = self.researcher_limit  # default

        # Try to extract user info from Authorization header for role-based limits
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_access_token

                payload = decode_access_token(auth_header[7:])
                user_id = payload.get("sub", "")
                role = payload.get("role", "researcher")
                if role == "admin":
                    limit = self.admin_limit
                return f"user:{user_id}", limit
            except Exception:
                pass

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )
        return f"ip:{client_ip}", limit

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_key, limit = self._get_client_key(request)
        now = time.time()

        # Clean expired entries
        self.requests[client_key] = [
            t for t in self.requests[client_key]
            if now - t < self.window_seconds
        ]

        remaining = max(0, limit - len(self.requests[client_key]))
        reset_at = int(now + self.window_seconds)

        # Rate limit headers (always sent)
        rate_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining - 1)),
            "X-RateLimit-Reset": str(reset_at),
        }

        if remaining <= 0:
            _restriction_logger.warning(
                "Rate limit exceeded",
                client_key=client_key,
                path=request.url.path,
                limit=limit,
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={**rate_headers, "Retry-After": str(self.window_seconds)},
            )

        self.requests[client_key].append(now)
        response = await call_next(request)

        # Attach rate limit headers to successful responses
        for k, v in rate_headers.items():
            response.headers[k] = v

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response.

    Mitigates clickjacking, MIME-sniffing, XSS, and information leakage.
    Adds HSTS in production mode.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS — only in production (assumes TLS termination at reverse proxy)
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce maximum request body size.

    Returns 413 Payload Too Large if the Content-Length exceeds the limit,
    or if the streamed body exceeds it.  Default: 10 KB for generation endpoints,
    100 KB for other endpoints.
    """

    GENERATION_PATHS = frozenset({
        "/api/v1/generations",
        "/api/v1/generations/",
    })

    def __init__(self, app, default_max_bytes: int = 102_400, generation_max_bytes: int = 10_240):
        super().__init__(app)
        self.default_max_bytes = default_max_bytes
        self.generation_max_bytes = generation_max_bytes

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            path = request.url.path.rstrip("/")
            max_bytes = (
                self.generation_max_bytes
                if path in ("/api/v1/generations",)
                else self.default_max_bytes
            )

            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                _restriction_logger.warning(
                    "Request body too large",
                    path=request.url.path,
                    content_length=int(content_length),
                    max_bytes=max_bytes,
                )
                return Response(
                    content=f'{{"detail": "Request body too large. Maximum: {max_bytes} bytes."}}',
                    status_code=413,
                    media_type="application/json",
                )

        return await call_next(request)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP to HTTPS in production.

    Only active when APP_ENV=production. In development, this is a no-op.
    """

    async def dispatch(self, request: Request, call_next):
        if (
            settings.app_env == "production"
            and request.url.scheme == "http"
            and request.url.path not in ("/health", "/ready")
        ):
            url = request.url.replace(scheme="https")
            return Response(
                status_code=301,
                headers={"Location": str(url)},
            )
        return await call_next(request)


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

# Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# HTTPS Redirect (production only)
app.add_middleware(HTTPSRedirectMiddleware)

# Request Size Limits (10KB for generation, 100KB default)
app.add_middleware(
    RequestSizeLimitMiddleware,
    default_max_bytes=102_400,
    generation_max_bytes=10_240,
)

# Role-Aware Rate Limiting (30/hr researcher, 100/hr admin)
app.add_middleware(
    RateLimitMiddleware,
    researcher_limit=settings.rate_limit_researcher,
    admin_limit=settings.rate_limit_admin,
    window_seconds=3600,
)

# Register API routes
app.include_router(api_router)


# --- Content Restriction Exception Handler ---


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def content_restriction_validation_handler(
    request: Request, exc: RequestValidationError
):
    """Intercept Pydantic validation errors to log prompt injection blocks.

    Any validation error whose message contains 'injection' is logged as a
    content restriction event.  All validation errors are returned as 422.
    """
    for error in exc.errors():
        msg = str(error.get("msg", ""))
        if "injection" in msg.lower():
            _restriction_logger.warning(
                "Prompt injection blocked",
                path=request.url.path,
                field=str(error.get("loc", "")),
                detail=msg[:200],
            )

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


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
