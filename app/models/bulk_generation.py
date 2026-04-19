"""
Bulk Generation Models

Stores bulk generation campaigns and their individual results.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    LargeBinary,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class BulkGeneration(Base):
    """Groups a bulk generation campaign (one uploaded Excel file)."""

    __tablename__ = "bulk_generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign metadata
    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # File storage
    file_data = Column(LargeBinary, nullable=False)

    # Scenario & Template references
    scenario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Field mapping: column_index -> placeholder_name
    # Example: {"0": "[TARGET_NAME]", "1": "[TARGET_EMAIL]", "2": "[TARGET_DEPARTMENT]"}
    field_mapping = Column(JSONB, nullable=False, default=dict)

    # Generation parameters
    temperature = Column(String(10), default="0.7", nullable=False)
    max_tokens = Column(Integer, default=1024, nullable=False)
    model_variant = Column(String(100), default="gemini-2.5-flash-lite", nullable=False)

    # Processing status
    status = Column(
        SAEnum(
            "uploaded",
            "mapped",
            "processing",
            "completed",
            "failed",
            name="bulk_generation_status",
        ),
        default="uploaded",
        nullable=False,
    )

    # Progress tracking
    total_rows = Column(Integer, default=0, nullable=False)
    generated_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User")
    scenario = relationship("Scenario")
    template = relationship("Template")
    results = relationship(
        "BulkGenerationResult",
        back_populates="bulk_generation",
        cascade="all, delete-orphan",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_bulk_generations_user_id", "user_id"),
        Index("ix_bulk_generations_status", "status"),
        Index("ix_bulk_generations_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<BulkGeneration(id={self.id}, title={self.title}, status={self.status})>"


class BulkGenerationResult(Base):
    """Individual results for each row in a bulk generation campaign."""

    __tablename__ = "bulk_generation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bulk_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bulk_generations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Row metadata
    row_index = Column(Integer, nullable=False)

    # Input data from Excel row (with replacements applied)
    # Example: {"ФИО": "Иван Петров", "Email": "ivan@company.com", "Должность": "Менеджер"}
    input_data = Column(JSONB, nullable=False, default=dict)

    # Generated output
    generated_subject = Column(String(500), nullable=True)
    generated_message = Column(Text, nullable=True)

    # Link to Generation model if created
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status and error handling
    status = Column(
        SAEnum("pending", "generated", "failed", name="bulk_result_status"),
        default="pending",
        nullable=False,
    )
    error_message = Column(Text, nullable=True)

    # Generation parameters used
    field_replacements = Column(JSONB, nullable=True, default=dict)
    # Example: {"[TARGET_NAME]": "Иван Петров", "[TARGET_EMAIL]": "ivan@company.com"}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    bulk_generation = relationship("BulkGeneration", back_populates="results")
    generation = relationship("Generation")

    # Indexes
    __table_args__ = (
        Index("ix_bulk_generation_results_bulk_generation_id", "bulk_generation_id"),
        Index("ix_bulk_generation_results_status", "status"),
    )

    def __repr__(self):
        return f"<BulkGenerationResult(id={self.id}, row={self.row_index}, status={self.status})>"
