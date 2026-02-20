"""
Audit Service

Provides helper functions for creating immutable audit log entries.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: Optional[UUID],
    action_type: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Create an immutable audit log entry.

    Args:
        db: Database session.
        user_id: The user performing the action.
        action_type: Action identifier (e.g., "user.login", "scenario.create").
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        details: Additional context (stored as JSONB).
        ip_address: Client IP address.
        user_agent: Client User-Agent string.

    Returns:
        The created AuditLog instance.
    """
    log = AuditLog(
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
