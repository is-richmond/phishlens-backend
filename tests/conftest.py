"""
PhishLens — Pytest Configuration & Shared Fixtures

Provides:
  • In-memory SQLite test database with PostgreSQL type shims
  • User, Scenario, Template, Generation, Campaign factory fixtures
  • JWT auth-header helpers for researcher & admin roles
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, JSON, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# ── Compile PostgreSQL-specific types for SQLite ──────────────────────
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, INET

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"

# ── Override env BEFORE importing app modules ─────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.security import hash_password, create_access_token  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.models.template import Template  # noqa: E402
from app.models.generation import Generation  # noqa: E402
from app.models.campaign import Campaign  # noqa: E402

# ── In-memory SQLite engine ───────────────────────────────────────────

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Core fixtures ─────────────────────────────────────────────────────

RESEARCHER_PASSWORD = "Test1234!"
ADMIN_PASSWORD = "Admin1234!"


@pytest.fixture(autouse=True)
def db() -> Generator[Session, None, None]:
    """Fresh database for each test — create tables, yield session, drop."""
    Base.metadata.create_all(bind=engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db: Session) -> TestClient:
    """FastAPI TestClient with overridden DB dependency.

    Uses TestClient without context manager to avoid lifespan threading
    issues with coverage.py tracing. Lifespan is a no-op in testing anyway.
    """

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── User factories ────────────────────────────────────────────────────

@pytest.fixture()
def researcher_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="researcher@iitu.edu.kz",
        hashed_password=hash_password(RESEARCHER_PASSWORD),
        full_name="Test Researcher",
        institution="IITU",
        role="researcher",
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@iitu.edu.kz",
        hashed_password=hash_password(ADMIN_PASSWORD),
        full_name="Test Admin",
        institution="IITU",
        role="admin",
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def inactive_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="suspended@iitu.edu.kz",
        hashed_password=hash_password(RESEARCHER_PASSWORD),
        full_name="Suspended User",
        institution="IITU",
        role="researcher",
        is_active=False,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def expired_terms_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="expired@iitu.edu.kz",
        hashed_password=hash_password(RESEARCHER_PASSWORD),
        full_name="Expired Terms User",
        institution="IITU",
        role="researcher",
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Auth header helpers ───────────────────────────────────────────────

def make_auth_headers(user: User) -> dict[str, str]:
    """Generate ``Authorization: Bearer <jwt>`` header dict for a user."""
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def researcher_headers(researcher_user: User) -> dict[str, str]:
    return make_auth_headers(researcher_user)


@pytest.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    return make_auth_headers(admin_user)


# ── Model factories ──────────────────────────────────────────────────

@pytest.fixture()
def sample_scenario(db: Session, researcher_user: User) -> Scenario:
    scenario = Scenario(
        id=uuid.uuid4(),
        user_id=researcher_user.id,
        title="Test Credential Phishing Scenario",
        description="A test scenario for credential phishing",
        target_role="HR Manager",
        target_department="Human Resources",
        organization_context="Large multinational corporation",
        pretext_category="credential_phishing",
        pretext_description="Password reset notification",
        urgency_level=3,
        communication_channel="email",
        language="english",
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@pytest.fixture()
def sample_template(db: Session, researcher_user: User) -> Template:
    template = Template(
        id=uuid.uuid4(),
        user_id=researcher_user.id,
        name="Test Custom Template",
        description="A test custom template",
        category="credential_phishing",
        system_prompt=(
            "You are a cybersecurity research assistant for PhishLens. "
            "Generate realistic phishing simulation messages."
        ),
        user_prompt_skeleton=(
            "Generate a {{ATTACK_CATEGORY}} message targeting "
            "{{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}."
        ),
        is_predefined=False,
        is_public=False,
        version="1.0",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@pytest.fixture()
def predefined_template(db: Session) -> Template:
    template = Template(
        id=uuid.uuid4(),
        user_id=None,
        name="System Template",
        description="Predefined system template",
        category="business_email_compromise",
        system_prompt=(
            "You are a cybersecurity research assistant. "
            "Generate BEC simulation messages for training purposes."
        ),
        user_prompt_skeleton=(
            "Generate a {{ATTACK_CATEGORY}} message targeting {{TARGET_ROLE}}."
        ),
        is_predefined=True,
        is_public=True,
        version="1.0",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@pytest.fixture()
def sample_generation(db: Session, sample_scenario: Scenario) -> Generation:
    generation = Generation(
        id=uuid.uuid4(),
        scenario_id=sample_scenario.id,
        template_id=None,
        input_parameters={
            "temperature": 0.7,
            "max_tokens": 1024,
            "model_variant": "gemini-2.5-flash-lite",
        },
        generated_subject="Urgent: Password Reset Required",
        generated_text=(
            "Dear [TARGET_NAME],\n\nYour password will expire in 24 hours.\n\n"
            "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]"
        ),
        model_used="gemini-2.5-flash-lite",
        overall_score=7.5,
        dimensional_scores={
            "linguistic_naturalness": 8.0,
            "psychological_triggers": 7.0,
            "technical_plausibility": 7.5,
            "contextual_relevance": 7.5,
        },
        evaluation_analysis="Good overall quality with convincing urgency.",
        watermark="[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]",
        generation_time_ms=1200.50,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


@pytest.fixture()
def sample_campaign(db: Session, researcher_user: User) -> Campaign:
    campaign = Campaign(
        id=uuid.uuid4(),
        user_id=researcher_user.id,
        name="Q1 2026 Security Training",
        description="Campaign for Q1 security awareness training",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign
