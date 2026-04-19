"""Add bulk generation tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-26

Adds support for bulk generation from Excel files:
- bulk_generations: Parent table for bulk campaigns
- bulk_generation_results: Individual results for each row
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM types for bulk generation ---
    bulk_generation_status = postgresql.ENUM(
        "uploaded",
        "mapped",
        "processing",
        "completed",
        "failed",
        name="bulk_generation_status",
        create_type=False,
    )
    bulk_generation_status.create(op.get_bind(), checkfirst=True)

    bulk_result_status = postgresql.ENUM(
        "pending",
        "generated",
        "failed",
        name="bulk_result_status",
        create_type=False,
    )
    bulk_result_status.create(op.get_bind(), checkfirst=True)

    # --- Add bulk_generation_id to generations table ---
    op.add_column(
        "generations",
        sa.Column(
            "bulk_generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bulk_generations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_generations_bulk_generation_id", "generations", ["bulk_generation_id"])

    # --- Create bulk_generations table ---
    op.create_table(
        "bulk_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_mapping", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("temperature", sa.String(10), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("model_variant", sa.String(100), nullable=False, server_default="gemini-2.5-flash-lite"),
        sa.Column("status", bulk_generation_status, nullable=False, server_default="uploaded"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bulk_generations_user_id", "bulk_generations", ["user_id"])
    op.create_index("ix_bulk_generations_status", "bulk_generations", ["status"])
    op.create_index("ix_bulk_generations_created_at", "bulk_generations", ["created_at"])

    # --- Create bulk_generation_results table ---
    op.create_table(
        "bulk_generation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bulk_generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bulk_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("input_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("generated_subject", sa.String(500), nullable=True),
        sa.Column("generated_message", sa.Text(), nullable=True),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", bulk_result_status, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("field_replacements", postgresql.JSONB(), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bulk_generation_results_bulk_generation_id", "bulk_generation_results", ["bulk_generation_id"])
    op.create_index("ix_bulk_generation_results_status", "bulk_generation_results", ["status"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_bulk_generation_results_status", table_name="bulk_generation_results")
    op.drop_index("ix_bulk_generation_results_bulk_generation_id", table_name="bulk_generation_results")
    op.drop_index("ix_bulk_generations_created_at", table_name="bulk_generations")
    op.drop_index("ix_bulk_generations_status", table_name="bulk_generations")
    op.drop_index("ix_bulk_generations_user_id", table_name="bulk_generations")
    op.drop_index("ix_generations_bulk_generation_id", table_name="generations")

    # Drop tables
    op.drop_table("bulk_generation_results")
    op.drop_table("bulk_generations")

    # Drop column from generations
    op.drop_column("generations", "bulk_generation_id")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS bulk_result_status;")
    op.execute("DROP TYPE IF EXISTS bulk_generation_status;")
