"""
Template Model

Stores system prompt templates and user prompt skeletons for phishing message generation.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # NULL for system-predefined templates
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(
        SAEnum(
            "credential_phishing",
            "business_email_compromise",
            "quishing",
            "spear_phishing",
            "whaling",
            "smishing",
            name="template_category",
        ),
        nullable=False,
    )

    # Prompt Content
    system_prompt = Column(Text, nullable=False)  # Role definition and constraints
    user_prompt_skeleton = Column(Text, nullable=False)  # Placeholder template

    # Metadata
    is_predefined = Column(Boolean, default=False, nullable=False)  # System vs custom
    is_public = Column(Boolean, default=False, nullable=False)  # Shared vs private
    version = Column(String(20), default="1.0", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="templates")
    generations = relationship("Generation", back_populates="template")

    def __repr__(self):
        return f"<Template(id={self.id}, name={self.name}, category={self.category})>"
