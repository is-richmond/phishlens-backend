"""
Admin Router

Admin-only endpoints for user management, audit logs, system health,
and platform statistics.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import func, case, text
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_admin, get_client_ip
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.scenario import Scenario
from app.models.campaign import Campaign
from app.models.template import Template
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse
from app.services.audit import log_action
from app.services.abuse_detection import detect_anomalous_users, compute_usage_statistics
from app.services.data_retention import (
    get_retention_summary,
    run_full_retention_cycle,
)

router = APIRouter()


# --- User Management ---


@router.get("/users", response_model=list[UserResponse])
def list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all registered users with optional filtering (admin only)."""
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        term = f"%{search}%"
        from sqlalchemy import or_
        query = query.filter(
            or_(
                User.email.ilike(term),
                User.full_name.ilike(term),
                User.institution.ilike(term),
            )
        )

    users = (
        query.order_by(User.created_at.desc())
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
    request: Request,
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
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return user


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Suspend (deactivate) a user account (admin only).

    Prevents the user from logging in and using the platform.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already suspended",
        )

    user.is_active = False
    db.commit()

    log_action(
        db,
        admin.id,
        "admin.suspend_user",
        "user",
        user.id,
        details={"user_email": user.email},
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": f"User {user.email} has been suspended"}


@router.post("/users/{user_id}/reactivate")
def reactivate_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Reactivate a suspended user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active",
        )

    user.is_active = True
    db.commit()

    log_action(
        db,
        admin.id,
        "admin.reactivate_user",
        "user",
        user.id,
        details={"user_email": user.email},
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": f"User {user.email} has been reactivated"}


# --- Statistics ---


@router.get("/statistics")
def get_platform_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get comprehensive platform statistics (admin only).

    Returns user counts, generation metrics, model usage distribution,
    category breakdown, and score analytics.
    """
    # User stats
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712
    admin_users = db.query(User).filter(User.role == "admin").count()
    researcher_users = db.query(User).filter(User.role == "researcher").count()

    # Generation stats
    total_generations = db.query(Generation).count()
    scored_generations = db.query(Generation).filter(Generation.overall_score.isnot(None)).count()

    avg_score = db.query(func.avg(Generation.overall_score)).filter(
        Generation.overall_score.isnot(None)
    ).scalar()

    min_score = db.query(func.min(Generation.overall_score)).filter(
        Generation.overall_score.isnot(None)
    ).scalar()

    max_score = db.query(func.max(Generation.overall_score)).filter(
        Generation.overall_score.isnot(None)
    ).scalar()

    # Model usage distribution
    model_distribution = (
        db.query(Generation.model_used, func.count(Generation.id))
        .group_by(Generation.model_used)
        .all()
    )

    # Category distribution (via scenarios)
    category_distribution = (
        db.query(Scenario.pretext_category, func.count(Scenario.id))
        .group_by(Scenario.pretext_category)
        .all()
    )

    # Other counts
    total_scenarios = db.query(Scenario).count()
    total_campaigns = db.query(Campaign).count()
    total_templates = db.query(Template).count()
    predefined_templates = db.query(Template).filter(Template.is_predefined == True).count()  # noqa: E712

    # Score distribution (buckets)
    score_distribution = {}
    for low, high, label in [
        (0, 3, "low (0-3)"),
        (3, 5, "below_average (3-5)"),
        (5, 7, "average (5-7)"),
        (7, 9, "good (7-9)"),
        (9, 10.1, "excellent (9-10)"),
    ]:
        count = db.query(Generation).filter(
            Generation.overall_score >= low,
            Generation.overall_score < high,
        ).count()
        score_distribution[label] = count

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "suspended": total_users - active_users,
            "admins": admin_users,
            "researchers": researcher_users,
        },
        "generations": {
            "total": total_generations,
            "scored": scored_generations,
            "unscored": total_generations - scored_generations,
            "average_score": round(float(avg_score), 2) if avg_score else None,
            "min_score": round(float(min_score), 2) if min_score else None,
            "max_score": round(float(max_score), 2) if max_score else None,
            "score_distribution": score_distribution,
        },
        "models": {
            model: count for model, count in model_distribution
        },
        "categories": {
            cat: count for cat, count in category_distribution
        },
        "scenarios": {"total": total_scenarios},
        "campaigns": {"total": total_campaigns},
        "templates": {
            "total": total_templates,
            "predefined": predefined_templates,
            "custom": total_templates - predefined_templates,
        },
    }


# --- Audit Logs ---


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    user_id: Optional[UUID] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List audit logs with advanced filtering (admin only)."""
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action_type:
        query = query.filter(AuditLog.action_type == action_type)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
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


@router.get("/audit-logs/action-types")
def list_action_types(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all distinct action types in the audit log (admin only).

    Useful for populating filter dropdowns in the admin UI.
    """
    types = db.query(AuditLog.action_type).distinct().all()
    return [t[0] for t in types]


# --- Abuse Detection ---


@router.get("/abuse-detection")
def get_abuse_alerts(
    window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Detect users with anomalously high generation counts (admin only).

    Flags users whose generation count exceeds ``mean + N × std_dev``
    within the specified time window (default N = 2, window = 30 days).
    """
    stats = compute_usage_statistics(db, window_days)
    flagged = detect_anomalous_users(db, window_days)

    return {
        "statistics": stats,
        "flagged_users": flagged,
        "flagged_count": len(flagged),
    }


# --- Data Retention ---


@router.get("/retention")
def retention_summary(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get data retention policy summary and records due for archival.

    Shows generation/user counts that exceed the configured retention window
    (12 months for generations, 6 months for inactive users).
    """
    return get_retention_summary(db)


@router.post("/retention/run")
def trigger_retention_cycle(
    request: Request,
    dry_run: bool = Query(True, description="Preview mode — no records are modified"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Trigger a data retention cycle (admin only).

    By default runs in ``dry_run=True`` mode which only counts records
    without modifying data.  Set ``dry_run=false`` to perform actual
    archival and user deactivation.
    """
    result = run_full_retention_cycle(
        db,
        admin_user_id=admin.id,
        dry_run=dry_run,
    )

    log_action(
        db,
        admin.id,
        "admin.retention_cycle",
        details={
            "dry_run": dry_run,
            "generations_archived": result["generations_archived"]["count"],
            "users_deactivated": result["users_deactivated"]["count"],
        },
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return result


# --- System Health ---


@router.get("/health")
def system_health(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get system health status (admin only)."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712
    total_generations = db.query(Generation).count()

    return {
        "status": "ok",
        "database": db_status,
        "users": {
            "total": total_users,
            "active": active_users,
        },
        "generations": {
            "total": total_generations,
        },
    }
