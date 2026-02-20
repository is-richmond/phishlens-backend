"""
Authentication Router

Endpoints: register, login, logout, refresh, me, change-password
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_client_ip
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.validation import validate_password_strength
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, ChangePasswordRequest
from app.schemas.user import UserResponse
from app.services.audit import log_action

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    """Register a new researcher account.

    Validates password strength and terms acceptance.
    """
    # Verify terms acceptance
    if not data.terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms of Use to register.",
        )

    # Validate password strength
    password_error = validate_password_strength(data.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=password_error,
        )

    # Check duplicate email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        institution=data.institution,
        role="researcher",
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(
        db,
        user.id,
        "user.register",
        "user",
        user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return user


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, response: Response, request: Request, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT token."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        # Log failed login attempt (use None user_id if user not found)
        log_action(
            db,
            user.id if user else None,
            "user.login_failed",
            "user",
            user.id if user else None,
            details={"email": data.email, "reason": "invalid_credentials"},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        log_action(
            db,
            user.id,
            "user.login_failed",
            "user",
            user.id,
            details={"reason": "account_deactivated"},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    access_token = create_access_token(user.id, user.role)

    # Set HTTP-only cookie (Secure, SameSite=Strict)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,  # 24 hours
    )

    log_action(
        db,
        user.id,
        "user.login",
        "user",
        user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refresh the JWT access token.

    The current valid token is used to issue a new one with a fresh expiry.
    """
    new_token = create_access_token(current_user.id, current_user.role)

    # Update HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,
    )

    log_action(
        db,
        current_user.id,
        "user.token_refresh",
        "user",
        current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(access_token=new_token)


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout and clear the session cookie."""
    response.delete_cookie("access_token")
    log_action(
        db,
        current_user.id,
        "user.logout",
        "user",
        current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {"message": "Logged out successfully"}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password.

    Requires the current password for verification and validates new password strength.
    """
    # Verify current password
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    # Validate new password strength
    password_error = validate_password_strength(data.new_password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=password_error,
        )

    # Ensure new password differs from current
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    log_action(
        db,
        current_user.id,
        "user.change_password",
        "user",
        current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return current_user
