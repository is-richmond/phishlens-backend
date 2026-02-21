"""
Sprint 5.1.2 — Scenario CRUD & Filtering Tests

Covers: create, read, update, delete, ownership isolation, filtering,
        search, pagination, persona & category presets.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.scenario import Scenario
from tests.conftest import make_auth_headers


# ── Create Scenario ──────────────────────────────────────────────────

class TestCreateScenario:

    VALID_PAYLOAD = {
        "title": "Credential Phishing Test",
        "description": "A credential phishing scenario",
        "target_role": "Finance Manager",
        "target_department": "Finance",
        "organization_context": "Tech startup with 200 employees",
        "pretext_category": "credential_phishing",
        "pretext_description": "Password expiration warning",
        "urgency_level": 4,
        "communication_channel": "email",
        "language": "english",
    }

    def test_create_scenario_success(self, client: TestClient, researcher_headers):
        resp = client.post(
            "/api/v1/scenarios", json=self.VALID_PAYLOAD, headers=researcher_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Credential Phishing Test"
        assert data["pretext_category"] == "credential_phishing"
        assert "id" in data

    def test_create_scenario_requires_auth(self, client: TestClient):
        resp = client.post("/api/v1/scenarios", json=self.VALID_PAYLOAD)
        assert resp.status_code == 403

    def test_create_scenario_html_sanitised(self, client: TestClient, researcher_headers):
        payload = {**self.VALID_PAYLOAD, "title": "<script>alert('xss')</script>Clean Title"}
        resp = client.post("/api/v1/scenarios", json=payload, headers=researcher_headers)
        assert resp.status_code == 201
        assert "<script>" not in resp.json()["title"]

    def test_create_scenario_invalid_urgency(self, client: TestClient, researcher_headers):
        payload = {**self.VALID_PAYLOAD, "urgency_level": 6}
        resp = client.post("/api/v1/scenarios", json=payload, headers=researcher_headers)
        assert resp.status_code == 422

    def test_create_scenario_invalid_category(self, client: TestClient, researcher_headers):
        payload = {**self.VALID_PAYLOAD, "pretext_category": "nonexistent"}
        resp = client.post("/api/v1/scenarios", json=payload, headers=researcher_headers)
        assert resp.status_code == 422


# ── Read / List Scenarios ────────────────────────────────────────────

class TestListScenarios:

    def test_list_own_scenarios(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get("/api/v1/scenarios", headers=researcher_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_returns_only_own(
        self, client: TestClient, db: Session,
        sample_scenario: Scenario, researcher_headers,
    ):
        """Create a scenario for a different user and ensure it's not returned."""
        other = User(
            id=uuid.uuid4(), email="other@nu.edu.kz",
            hashed_password="x", full_name="Other", institution="NU",
            role="researcher", is_active=True,
        )
        db.add(other)
        db.commit()
        other_scenario = Scenario(
            id=uuid.uuid4(), user_id=other.id, title="Other Scenario",
            target_role="CEO", pretext_category="whaling",
            urgency_level=5, communication_channel="email", language="english",
        )
        db.add(other_scenario)
        db.commit()

        resp = client.get("/api/v1/scenarios", headers=researcher_headers)
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(other_scenario.id) not in ids

    def test_get_scenario_by_id(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get(
            f"/api/v1/scenarios/{sample_scenario.id}", headers=researcher_headers
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == sample_scenario.title

    def test_get_nonexistent_scenario(self, client: TestClient, researcher_headers):
        resp = client.get(
            f"/api/v1/scenarios/{uuid.uuid4()}", headers=researcher_headers
        )
        assert resp.status_code == 404


# ── Filtering & Search ───────────────────────────────────────────────

class TestScenarioFiltering:

    def test_filter_by_category(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get(
            "/api/v1/scenarios?category=credential_phishing",
            headers=researcher_headers,
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["pretext_category"] == "credential_phishing"

    def test_filter_by_channel(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get(
            "/api/v1/scenarios?channel=email",
            headers=researcher_headers,
        )
        assert resp.status_code == 200

    def test_search_by_text(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get(
            "/api/v1/scenarios?search=Credential",
            headers=researcher_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_pagination(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.get(
            "/api/v1/scenarios?page=1&per_page=5",
            headers=researcher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 5


# ── Update & Delete ──────────────────────────────────────────────────

class TestScenarioUpdateDelete:

    def test_update_scenario(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.put(
            f"/api/v1/scenarios/{sample_scenario.id}",
            headers=researcher_headers,
            json={"title": "Updated Title", "urgency_level": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        assert resp.json()["urgency_level"] == 5

    def test_update_nonexistent_scenario(self, client: TestClient, researcher_headers):
        resp = client.put(
            f"/api/v1/scenarios/{uuid.uuid4()}",
            headers=researcher_headers,
            json={"title": "No"},
        )
        assert resp.status_code == 404

    def test_delete_scenario(
        self, client: TestClient, sample_scenario: Scenario, researcher_headers
    ):
        resp = client.delete(
            f"/api/v1/scenarios/{sample_scenario.id}", headers=researcher_headers
        )
        assert resp.status_code == 204

    def test_delete_nonexistent_scenario(self, client: TestClient, researcher_headers):
        resp = client.delete(
            f"/api/v1/scenarios/{uuid.uuid4()}", headers=researcher_headers
        )
        assert resp.status_code == 404


# ── Presets ───────────────────────────────────────────────────────────

class TestPresets:

    def test_list_persona_presets(self, client: TestClient, researcher_headers):
        resp = client.get("/api/v1/scenarios/presets/personas", headers=researcher_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_list_pretext_categories(self, client: TestClient, researcher_headers):
        resp = client.get(
            "/api/v1/scenarios/presets/categories", headers=researcher_headers
        )
        assert resp.status_code == 200
        cats = resp.json()
        assert any(c["category"] == "credential_phishing" for c in cats)
