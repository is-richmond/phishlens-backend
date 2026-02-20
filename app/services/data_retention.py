"""
Data Retention Service

Implements the PhishLens data retention policy:

- **Generations**: Archived/deleted after 12 months (configurable).
- **Inactive users**: Flagged/deactivated after 6 months of inactivity.
- **Audit logs**: Retained indefinitely (compliance requirement).
- **Scenarios/Campaigns**: Cascaded with generation cleanup where applicable.

This module provides:
  - ``get_retention_summary()`` — statistics on records due for archival.
  - ``archive_old_generations()`` — soft-delete generations older than the
    retention window.
  - ``flag_inactive_users()`` — deactivate users with no login/generation
    activity within the inactive-user window.
  - ``run_full_retention_cycle()`` — orchestrate all retention tasks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.scenario import Scenario
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.audit import log_action
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("data_retention")


# ---------------------------------------------------------------------------
# Retention summary (read-only)
# ---------------------------------------------------------------------------


def get_retention_summary(db: Session) -> dict:
    """Return statistics on records that are due for archival/cleanup.

    Returns a dict with counts for:
    - ``generations_due``: generations older than the retention window.
    - ``inactive_users_due``: users with no recent activity.
    - ``total_audit_logs``: total audit log entries (retained indefinitely).
    """
    gen_cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.retention_generation_months * 30
    )
    user_cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.retention_inactive_user_months * 30
    )

    # Generations older than retention window
    generations_due = (
        db.query(func.count(Generation.id))
        .filter(Generation.created_at < gen_cutoff)
        .scalar()
    ) or 0

    # Total generations
    total_generations = db.query(func.count(Generation.id)).scalar() or 0

    # Users with no activity (no audit_log entry) since the cutoff
    # Activity = any audit log entry with this user_id after cutoff
    active_user_ids = (
        db.query(AuditLog.user_id)
        .filter(
            AuditLog.user_id.isnot(None),
            AuditLog.created_at >= user_cutoff,
        )
        .distinct()
        .subquery()
    )

    inactive_users_due = (
        db.query(func.count(User.id))
        .filter(
            User.is_active == True,  # noqa: E712
            User.role != "admin",    # never auto-deactivate admins
            ~User.id.in_(db.query(active_user_ids.c.user_id)),
        )
        .scalar()
    ) or 0

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_audit_logs = db.query(func.count(AuditLog.id)).scalar() or 0

    return {
        "retention_policy": {
            "generation_months": settings.retention_generation_months,
            "inactive_user_months": settings.retention_inactive_user_months,
            "audit_logs": "retained indefinitely",
        },
        "generations": {
            "total": total_generations,
            "due_for_archival": generations_due,
            "cutoff_date": gen_cutoff.isoformat(),
        },
        "users": {
            "total": total_users,
            "inactive_due": inactive_users_due,
            "cutoff_date": user_cutoff.isoformat(),
        },
        "audit_logs": {
            "total": total_audit_logs,
        },
    }


# ---------------------------------------------------------------------------
# Archival / cleanup operations
# ---------------------------------------------------------------------------


def archive_old_generations(
    db: Session,
    admin_user_id: Optional[UUID] = None,
    dry_run: bool = False,
) -> dict:
    """Delete generations older than the configured retention window.

    Args:
        db: Database session.
        admin_user_id: The admin triggering the archival (for audit).
        dry_run: If True, only count — do not delete.

    Returns:
        Dict with ``count`` of affected records and ``dry_run`` flag.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.retention_generation_months * 30
    )

    query = db.query(Generation).filter(Generation.created_at < cutoff)
    count = query.count()

    if count == 0:
        logger.info("No generations due for archival")
        return {"count": 0, "dry_run": dry_run, "cutoff": cutoff.isoformat()}

    if not dry_run:
        query.delete(synchronize_session="fetch")
        db.commit()

        logger.info(
            "Archived old generations",
            count=count,
            cutoff=cutoff.isoformat(),
        )

        if admin_user_id:
            log_action(
                db,
                admin_user_id,
                "retention.archive_generations",
                "generation",
                None,
                details={
                    "count": count,
                    "cutoff": cutoff.isoformat(),
                    "policy_months": settings.retention_generation_months,
                },
            )
    else:
        logger.info(
            "Dry run: generations due for archival",
            count=count,
            cutoff=cutoff.isoformat(),
        )

    return {"count": count, "dry_run": dry_run, "cutoff": cutoff.isoformat()}


def flag_inactive_users(
    db: Session,
    admin_user_id: Optional[UUID] = None,
    dry_run: bool = False,
) -> dict:
    """Deactivate non-admin users with no activity in the retention window.

    Activity is determined by the most recent ``AuditLog`` entry for each user.

    Args:
        db: Database session.
        admin_user_id: The admin triggering the operation (for audit).
        dry_run: If True, only count — do not deactivate.

    Returns:
        Dict with ``count`` of affected users, their emails, and ``dry_run``.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.retention_inactive_user_months * 30
    )

    # Subquery: user IDs with *any* activity after cutoff
    active_ids = (
        db.query(AuditLog.user_id)
        .filter(
            AuditLog.user_id.isnot(None),
            AuditLog.created_at >= cutoff,
        )
        .distinct()
        .subquery()
    )

    inactive_users = (
        db.query(User)
        .filter(
            User.is_active == True,  # noqa: E712
            User.role != "admin",
            ~User.id.in_(db.query(active_ids.c.user_id)),
        )
        .all()
    )

    count = len(inactive_users)
    emails = [u.email for u in inactive_users]

    if count == 0:
        logger.info("No inactive users due for deactivation")
        return {"count": 0, "dry_run": dry_run, "emails": []}

    if not dry_run:
        for user in inactive_users:
            user.is_active = False
        db.commit()

        logger.info(
            "Deactivated inactive users",
            count=count,
            cutoff=cutoff.isoformat(),
        )

        if admin_user_id:
            log_action(
                db,
                admin_user_id,
                "retention.deactivate_inactive_users",
                "user",
                None,
                details={
                    "count": count,
                    "emails": emails,
                    "cutoff": cutoff.isoformat(),
                    "policy_months": settings.retention_inactive_user_months,
                },
            )
    else:
        logger.info(
            "Dry run: inactive users due for deactivation",
            count=count,
            emails=emails,
        )

    return {"count": count, "dry_run": dry_run, "emails": emails}


def run_full_retention_cycle(
    db: Session,
    admin_user_id: Optional[UUID] = None,
    dry_run: bool = False,
) -> dict:
    """Execute the complete data retention cycle.

    1. Archive old generations.
    2. Flag inactive users.

    Args:
        db: Database session.
        admin_user_id: Admin triggering the cycle.
        dry_run: Preview-only mode.

    Returns:
        Combined results from all retention operations.
    """
    logger.info(
        "Starting retention cycle",
        dry_run=dry_run,
        admin=str(admin_user_id) if admin_user_id else "system",
    )

    gen_result = archive_old_generations(db, admin_user_id, dry_run)
    user_result = flag_inactive_users(db, admin_user_id, dry_run)

    return {
        "dry_run": dry_run,
        "generations_archived": gen_result,
        "users_deactivated": user_result,
    }
