"""
Sprint 5.1.8 — Load Testing Script (Locust)

Simulates 50 concurrent researchers exercising the PhishLens API.
Focuses on read-heavy routes (scenarios, templates, generations)
with occasional writes (create scenario, create campaign).

Usage:
    locust -f tests/test_load.py --host http://localhost:8000
"""

import json
import random
import uuid

from locust import HttpUser, task, between, events


class PhishLensUser(HttpUser):
    """Simulates a researcher interacting with the PhishLens API."""

    wait_time = between(1, 3)  # 1–3 seconds between tasks

    # Filled during on_start
    token: str = ""
    scenario_ids: list[str] = []
    campaign_ids: list[str] = []

    def on_start(self):
        """Register + login to obtain a JWT token."""
        email = f"loadtest-{uuid.uuid4().hex[:8]}@iitu.edu.kz"
        password = "LoadTest1234!"

        # Register
        self.client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Load Test User",
            "institution": "IITU",
            "terms_accepted": True,
        })

        # Login
        resp = self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            self.token = ""

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # ── Scenario tasks ───────────────────────────────────────────────

    @task(3)
    def list_scenarios(self):
        self.client.get("/api/v1/scenarios", headers=self.auth_headers)

    @task(1)
    def create_scenario(self):
        resp = self.client.post("/api/v1/scenarios", json={
            "title": f"Load Scenario {uuid.uuid4().hex[:6]}",
            "target_role": random.choice([
                "HR Manager", "Software Engineer", "Finance Manager",
            ]),
            "pretext_category": random.choice([
                "credential_phishing", "business_email_compromise",
                "spear_phishing",
            ]),
            "urgency_level": random.randint(1, 5),
            "communication_channel": "email",
            "language": "english",
        }, headers=self.auth_headers)
        if resp.status_code == 201:
            self.scenario_ids.append(resp.json()["id"])

    # ── Template tasks ───────────────────────────────────────────────

    @task(2)
    def list_templates(self):
        self.client.get("/api/v1/templates", headers=self.auth_headers)

    # ── Campaign tasks ───────────────────────────────────────────────

    @task(2)
    def list_campaigns(self):
        self.client.get("/api/v1/campaigns", headers=self.auth_headers)

    @task(1)
    def create_campaign(self):
        resp = self.client.post("/api/v1/campaigns", json={
            "name": f"Load Campaign {uuid.uuid4().hex[:6]}",
            "description": "Created during load test",
        }, headers=self.auth_headers)
        if resp.status_code == 201:
            self.campaign_ids.append(resp.json()["id"])

    # ── Generation tasks (read-only — no actual LLM calls) ──────────

    @task(2)
    def list_generations(self):
        self.client.get("/api/v1/generations", headers=self.auth_headers)

    @task(1)
    def list_models(self):
        self.client.get("/api/v1/generations/models", headers=self.auth_headers)

    # ── Profile tasks ────────────────────────────────────────────────

    @task(1)
    def get_profile(self):
        self.client.get("/api/v1/auth/me", headers=self.auth_headers)

    # ── Health ────────────────────────────────────────────────────────

    @task(1)
    def health_check(self):
        self.client.get("/health")
