"""Add distributions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-02

Adds support for distribution (sending) of bulk generated messages:
- distributions: Individual email distributions to recipients
- Tracks delivery status, opens, and clicks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Create ENUM for distribution status ---
    distribution_status = postgresql.ENUM(
        "pending",
        "sent",
        "opened",
        "clicked",
        "failed",
        "bounced",
        name="distribution_status",
        create_type=False,
    )
    distribution_status.create(op.get_bind(), checkfirst=True)

    # --- Create distributions table ---
    op.create_table(
        "distributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bulk_generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bulk_generations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("recipient_email", sa.String(255), nullable=False, index=True),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status",
            distribution_status,
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.String(10), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- Create indexes ---
    op.create_index("ix_distributions_bulk_generation_id", "distributions", ["bulk_generation_id"])
    op.create_index("ix_distributions_campaign_id", "distributions", ["campaign_id"])
    op.create_index("ix_distributions_recipient_email", "distributions", ["recipient_email"])
    op.create_index("ix_distributions_status", "distributions", ["status"])
    op.create_index("ix_distributions_created_at", "distributions", ["created_at"])


def downgrade() -> None:
    # --- Drop indexes ---
    op.drop_index("ix_distributions_created_at", table_name="distributions")
    op.drop_index("ix_distributions_status", table_name="distributions")
    op.drop_index("ix_distributions_recipient_email", table_name="distributions")
    op.drop_index("ix_distributions_campaign_id", table_name="distributions")
    op.drop_index("ix_distributions_bulk_generation_id", table_name="distributions")

    # --- Drop table ---
    op.drop_table("distributions")

    # --- Drop ENUM type ---
    op.execute("DROP TYPE IF EXISTS distribution_status;")
