"""
PhishLens Dependency Injection

Common dependencies used across API endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.core.security import decode_access_token
from app.core.config import settings
from app.models.user import User

# HTTP Bearer scheme for JWT
security_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token.

    Raises:
        HTTPException 401: If token is invalid or user not found.
        HTTPException 403: If user account is deactivated.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has admin privileges.

    Raises:
        HTTPException 403: If user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_terms_current(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the user has accepted Terms of Use within the validity period.

    The validity window is configured via ``TERMS_VALIDITY_DAYS`` (default 90).
    If the terms have expired, the user must re-accept before generating
    content.

    Raises:
        HTTPException 403: If terms are expired or never accepted.
    """
    if current_user.terms_accepted_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must accept the Terms of Use before using this feature.",
        )

    # Normalise to offset-aware UTC for comparison
    accepted = current_user.terms_accepted_at
    if accepted.tzinfo is None:
        accepted = accepted.replace(tzinfo=timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.terms_validity_days)
    if accepted < cutoff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your Terms of Use acceptance has expired. "
                "Please re-accept the terms to continue."
            ),
        )

    return current_user


def get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --- Institutional Affiliation Helpers ---

# Allowed email domain suffixes for institutional verification
INSTITUTIONAL_DOMAIN_SUFFIXES = (
    ".edu",
    ".edu.kz",
    ".ac.uk",
    ".ac.jp",
    ".ac.kr",
    ".ac.in",
    ".ac.za",
    ".ac.nz",
    ".edu.au",
    ".edu.cn",
    ".edu.ru",
    ".uni-",       # Many European universities
    ".university",
)

# Explicitly allowed research institution domains
ALLOWED_RESEARCH_DOMAINS = frozenset({
    "iitu.edu.kz",
    "nu.edu.kz",
    "kaznu.kz",
    "enu.kz",
    "kbtu.kz",
    "sdu.edu.kz",
})


def validate_institutional_email(email: str) -> tuple[bool, str]:
    """Check whether an email belongs to an institutional / research domain.

    Returns:
        (is_valid, message) — ``is_valid=True`` if the domain is institutional,
        otherwise ``False`` with a human-readable reason.
    """
    domain = email.rsplit("@", 1)[-1].lower()

    if domain in ALLOWED_RESEARCH_DOMAINS:
        return True, "Recognised research institution"

    for suffix in INSTITUTIONAL_DOMAIN_SUFFIXES:
        if domain.endswith(suffix) or suffix in domain:
            return True, "Institutional domain detected"

    return False, (
        f"The email domain '{domain}' could not be verified as an institutional address. "
        "Please use your institutional (.edu) email or contact an administrator."
    )
