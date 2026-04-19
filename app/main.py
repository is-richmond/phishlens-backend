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
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1 import api_router
from app.database import engine, Base

# Logger for content restriction events
_restriction_logger = get_logger("content_restrictions")

# Debug: Print CORS configuration
print(f"[STARTUP] FRONTEND_URL from settings: {settings.frontend_url}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger = get_logger()
    logger.info("Starting PhishLens API", version=settings.app_version, env=settings.app_env)
    logger.info(f"CORS FRONTEND_URL from settings: {settings.frontend_url}")
    logger.info(f"CORS allowed origins: {[url.strip() for url in settings.frontend_url.split(',') if url.strip()]}")

    # Create tables if in dev mode (production uses Alembic migrations)
    if settings.app_env == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (dev mode)")

    # Seed predefined templates (skip in testing — tests manage their own DB)
    if settings.app_env != "testing":
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


class SecurityHeadersMiddleware:
    """Add security headers to every response.

    Mitigates clickjacking, MIME-sniffing, XSS, and information leakage.
    Adds HSTS in production mode.
    Pure ASGI implementation to avoid BaseHTTPMiddleware thread-deadlocks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                if settings.app_env == "production":
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestSizeLimitMiddleware:
    """Enforce maximum request body size.

    Returns 413 Payload Too Large if the Content-Length exceeds the limit.
    Default: 10 KB for generation endpoints, 100 KB for other endpoints.
    Pure ASGI implementation to avoid BaseHTTPMiddleware thread-deadlocks.
    """

    GENERATION_PATHS = frozenset({"/api/v1/generations"})

    def __init__(self, app: ASGIApp, default_max_bytes: int = 102_400, generation_max_bytes: int = 10_240):
        self.app = app
        self.default_max_bytes = default_max_bytes
        self.generation_max_bytes = generation_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method in ("POST", "PUT", "PATCH"):
            path = scope.get("path", "").rstrip("/")
            max_bytes = (
                self.generation_max_bytes
                if path in self.GENERATION_PATHS
                else self.default_max_bytes
            )

            headers_dict = dict(scope.get("headers", []))
            content_length = headers_dict.get(b"content-length")
            if content_length and int(content_length) > max_bytes:
                _restriction_logger.warning(
                    "Request body too large",
                    path=path,
                    content_length=int(content_length),
                    max_bytes=max_bytes,
                )
                response = Response(
                    content=f'{{"detail": "Request body too large. Maximum: {max_bytes} bytes."}}',
                    status_code=413,
                    media_type="application/json",
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


class HTTPSRedirectMiddleware:
    """Redirect HTTP to HTTPS in production.

    Only active when APP_ENV=production. In development/testing, this is a no-op.
    Pure ASGI implementation to avoid BaseHTTPMiddleware thread-deadlocks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip redirect for OPTIONS (CORS preflight) and health checks
        if (
            settings.app_env == "production"
            and scope.get("scheme") == "http"
            and scope.get("method") != "OPTIONS"
            and scope["path"] not in ("/health", "/ready")
        ):
            headers_dict = dict(scope.get("headers", []))
            host = headers_dict.get(b"host", b"localhost").decode()
            path = scope.get("path", "/")
            qs = scope.get("query_string", b"")
            url = f"https://{host}{path}"
            if qs:
                url += f"?{qs.decode()}"
            response = Response(
                status_code=301,
                headers={"Location": url},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


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
    redirect_slashes=False,
)

# Middleware stack (added in reverse order - last added executes first)
# 1. CORS must be first to handle preflight OPTIONS requests
frontend_origins = [
    url.strip() for url in settings.frontend_url.split(",") if url.strip()
]
print(f"CORS configured for origins: {frontend_origins}")

# Request Size Limits (10KB for generation, 100KB default)
app.add_middleware(
    RequestSizeLimitMiddleware,
    default_max_bytes=102_400,
    generation_max_bytes=10_240,
)

# HTTPS Redirect (production only)
app.add_middleware(HTTPSRedirectMiddleware)

# Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS Middleware - MUST be last added (so it executes first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Role-Aware Rate Limiting (30/hr researcher, 100/hr admin)
# app.add_middleware(
#     RateLimitMiddleware,
#     researcher_limit=settings.rate_limit_researcher,
#     admin_limit=settings.rate_limit_admin,
#     window_seconds=3600,
# )

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
    errors = exc.errors()
    for error in errors:
        msg = str(error.get("msg", ""))
        if "injection" in msg.lower():
            _restriction_logger.warning(
                "Prompt injection blocked",
                path=request.url.path,
                field=str(error.get("loc", "")),
                detail=msg[:200],
            )

    # Ensure ctx values are JSON-serializable (Pydantic v2 may embed
    # ValueError objects which are not serializable by default).
    safe_errors = []
    for error in errors:
        safe = {k: v for k, v in error.items() if k != "ctx"}
        if "ctx" in error and error["ctx"]:
            safe["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
        safe_errors.append(safe)

    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
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
