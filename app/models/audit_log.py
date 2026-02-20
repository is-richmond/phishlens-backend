"""
AuditLog Model

Append-only audit log for tracking all user actions. 
Immutability enforced via PostgreSQL TRIGGER (no UPDATE/DELETE).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action Details
    action_type = Column(String(100), nullable=False, index=True)
    # e.g., "user.login", "scenario.create", "generation.create", "admin.suspend_user"
    resource_type = Column(String(100), nullable=True)  # e.g., "scenario", "generation"
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, nullable=True, default=dict)
    # Stores additional context about the action

    # Request Metadata
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Timestamp (immutable once set)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    from sqlalchemy.orm import relationship
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action_type}, user={self.user_id})>"


# -----------------------------------------------------------------------
# PostgreSQL TRIGGER SQL (to be applied via Alembic migration)
# -----------------------------------------------------------------------
AUDIT_LOG_IMMUTABILITY_TRIGGER = """
-- Prevent UPDATE on audit_logs
CREATE OR REPLACE FUNCTION prevent_audit_log_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'UPDATE operations are not permitted on audit_logs table';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_audit_log_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_update();

-- Prevent DELETE on audit_logs
CREATE OR REPLACE FUNCTION prevent_audit_log_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'DELETE operations are not permitted on audit_logs table';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_audit_log_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_delete();
"""
