"""Initial schema - all tables

Revision ID: 0001
Revises: None
Create Date: 2026-02-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM types ---
    user_role = postgresql.ENUM("researcher", "admin", name="user_role", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)

    pretext_category = postgresql.ENUM(
        "credential_phishing",
        "business_email_compromise",
        "quishing",
        "spear_phishing",
        "whaling",
        "smishing",
        name="pretext_category",
        create_type=False,
    )
    pretext_category.create(op.get_bind(), checkfirst=True)

    comm_channel = postgresql.ENUM(
        "email", "sms", "internal_chat", name="comm_channel", create_type=False
    )
    comm_channel.create(op.get_bind(), checkfirst=True)

    language = postgresql.ENUM(
        "english", "russian", "kazakh", name="language", create_type=False
    )
    language.create(op.get_bind(), checkfirst=True)

    template_category = postgresql.ENUM(
        "credential_phishing",
        "business_email_compromise",
        "quishing",
        "spear_phishing",
        "whaling",
        "smishing",
        name="template_category",
        create_type=False,
    )
    template_category.create(op.get_bind(), checkfirst=True)

    # --- Users table ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("institution", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="researcher"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- Scenarios table ---
    op.create_table(
        "scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_role", sa.String(100), nullable=False),
        sa.Column("target_department", sa.String(100), nullable=True),
        sa.Column("organization_context", sa.Text(), nullable=True),
        sa.Column("pretext_category", pretext_category, nullable=False),
        sa.Column("pretext_description", sa.Text(), nullable=True),
        sa.Column("urgency_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("communication_channel", comm_channel, nullable=False, server_default="email"),
        sa.Column("language", language, nullable=False, server_default="english"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_scenarios_user_id", "scenarios", ["user_id"])

    # --- Templates table ---
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", template_category, nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_skeleton", sa.Text(), nullable=False),
        sa.Column("is_predefined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_templates_category", "templates", ["category"])

    # --- Generations table ---
    op.create_table(
        "generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("input_parameters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("generated_subject", sa.String(500), nullable=True),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("overall_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("dimensional_scores", postgresql.JSONB(), nullable=True),
        sa.Column("evaluation_analysis", sa.Text(), nullable=True),
        sa.Column(
            "watermark",
            sa.String(100),
            nullable=False,
            server_default="[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]",
        ),
        sa.Column("generation_time_ms", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_generations_scenario_id", "generations", ["scenario_id"])
    op.create_index("ix_generations_created_at", "generations", ["created_at"])

    # --- Campaigns table ---
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- Campaign-Generations association table ---
    op.create_table(
        "campaign_generations",
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "generation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Audit Logs table ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    # --- Immutability TRIGGERs for audit_logs ---
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'UPDATE operations are not permitted on audit_logs table';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_prevent_audit_log_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_update();
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'DELETE operations are not permitted on audit_logs table';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_prevent_audit_log_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_delete();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_update ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_delete();")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_update();")

    # Drop tables in reverse dependency order
    op.drop_table("campaign_generations")
    op.drop_table("audit_logs")
    op.drop_table("campaigns")
    op.drop_table("generations")
    op.drop_table("templates")
    op.drop_table("scenarios")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS template_category;")
    op.execute("DROP TYPE IF EXISTS language;")
    op.execute("DROP TYPE IF EXISTS comm_channel;")
    op.execute("DROP TYPE IF EXISTS pretext_category;")
    op.execute("DROP TYPE IF EXISTS user_role;")
