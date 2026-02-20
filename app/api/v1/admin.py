"""
Admin Router

Admin-only endpoints for user management, audit logs, and system health.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_admin
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse
from app.services.audit import log_action

router = APIRouter()


# --- User Management ---


@router.get("/users", response_model=list[UserResponse])
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all registered users (admin only)."""
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get a specific user's details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update a user's profile, role, or active status (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    log_action(
        db,
        admin.id,
        "admin.update_user",
        "user",
        user.id,
        details={"changes": update_data},
    )
    return user


# --- Audit Logs ---


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    user_id: Optional[UUID] = None,
    action_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List audit logs with filtering (admin only)."""
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action_type:
        query = query.filter(AuditLog.action_type == action_type)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return AuditLogListResponse(items=items, total=total, page=page, per_page=per_page)


# --- System Health ---


@router.get("/health")
def system_health(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get system health status (admin only)."""
    try:
        db.execute("SELECT 1")  # type: ignore
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712

    return {
        "status": "ok",
        "database": db_status,
        "users": {
            "total": total_users,
            "active": active_users,
        },
    }
