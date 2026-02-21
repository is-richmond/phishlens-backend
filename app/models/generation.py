"""
Generation Model

Stores generated phishing messages with their parameters and evaluation scores.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Generation(Base):
    __tablename__ = "generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    # Generation Input
    input_parameters = Column(JSONB, nullable=False, default=dict)
    # Stores: temperature, max_tokens, model_variant, full constructed prompt

    # Generation Output
    generated_subject = Column(String(500), nullable=True)  # Email subject line
    generated_text = Column(Text, nullable=False)  # The generated phishing message
    model_used = Column(String(100), nullable=False)  # e.g., "gemini-2.5-flash-lite"

    # Realism Scoring
    overall_score = Column(Numeric(3, 1), nullable=True)  # 1.0 - 10.0
    dimensional_scores = Column(JSONB, nullable=True, default=dict)
    # Stores: {
    #   "linguistic_naturalness": 8.5,
    #   "psychological_triggers": 7.0,
    #   "technical_plausibility": 9.0,
    #   "contextual_relevance": 8.0
    # }
    evaluation_analysis = Column(Text, nullable=True)  # Textual analysis from LLM

    # Watermark
    watermark = Column(
        String(100),
        default="[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]",
        nullable=False,
    )

    # Metadata
    generation_time_ms = Column(Numeric(10, 2), nullable=True)  # Generation latency
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    scenario = relationship("Scenario", back_populates="generations")
    template = relationship("Template", back_populates="generations")

    def __repr__(self):
        return f"<Generation(id={self.id}, score={self.overall_score})>"
