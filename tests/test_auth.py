"""
Sprint 5.1.1 — Authentication & Authorization Tests

Covers: registration, login, JWT lifecycle, password hashing, RBAC,
        terms re-acceptance, inactive-user blocking, profile updates.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.models.user import User
from tests.conftest import RESEARCHER_PASSWORD, ADMIN_PASSWORD, make_auth_headers


# ── Password hashing unit tests ──────────────────────────────────────

class TestPasswordHashing:

    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("StrongPass1!")
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("Test1234!")
        assert verify_password("Test1234!", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("Test1234!")
        assert verify_password("WrongPass1!", hashed) is False

    def test_different_passwords_produce_different_hashes(self):
        h1 = hash_password("Password1!")
        h2 = hash_password("Password2!")
        assert h1 != h2


# ── JWT unit tests ────────────────────────────────────────────────────

class TestJWT:

    def test_create_and_decode_token(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "researcher")
        payload = decode_access_token(token)
        assert payload["sub"] == str(uid)
        assert payload["role"] == "researcher"

    def test_token_contains_iat_and_exp(self):
        token = create_access_token(uuid.uuid4(), "admin")
        payload = decode_access_token(token)
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_expired_token_raises(self):
        from jose import JWTError
        token = create_access_token(
            uuid.uuid4(), "researcher", expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_admin_role_in_token(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "admin")
        payload = decode_access_token(token)
        assert payload["role"] == "admin"


# ── Registration endpoint tests ──────────────────────────────────────

class TestRegister:

    def test_successful_registration(self, client: TestClient, db: Session):
        resp = client.post("/api/v1/auth/register", json={
            "email": "newuser@iitu.edu.kz",
            "password": "Secure1234!",
            "full_name": "New User",
            "institution": "IITU",
            "terms_accepted": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@iitu.edu.kz"
        assert data["role"] == "researcher"

    def test_registration_requires_terms(self, client: TestClient):
        resp = client.post("/api/v1/auth/register", json={
            "email": "noterms@iitu.edu.kz",
            "password": "Secure1234!",
            "full_name": "No Terms",
            "institution": "IITU",
            "terms_accepted": False,
        })
        assert resp.status_code == 400

    def test_registration_rejects_weak_password(self, client: TestClient):
        resp = client.post("/api/v1/auth/register", json={
            "email": "weak@iitu.edu.kz",
            "password": "short",
            "full_name": "Weak Pass",
            "institution": "IITU",
            "terms_accepted": True,
        })
        assert resp.status_code == 422

    def test_registration_rejects_duplicate_email(
        self, client: TestClient, researcher_user: User
    ):
        resp = client.post("/api/v1/auth/register", json={
            "email": researcher_user.email,
            "password": "Secure1234!",
            "full_name": "Duplicate",
            "institution": "IITU",
            "terms_accepted": True,
        })
        assert resp.status_code == 409

    def test_registration_rejects_non_institutional_email(self, client: TestClient):
        resp = client.post("/api/v1/auth/register", json={
            "email": "user@gmail.com",
            "password": "Secure1234!",
            "full_name": "Gmail User",
            "institution": "Home",
            "terms_accepted": True,
        })
        assert resp.status_code == 422


# ── Login endpoint tests ─────────────────────────────────────────────

class TestLogin:

    def test_successful_login(self, client: TestClient, researcher_user: User):
        resp = client.post("/api/v1/auth/login", json={
            "email": researcher_user.email,
            "password": RESEARCHER_PASSWORD,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_sets_cookie(self, client: TestClient, researcher_user: User):
        resp = client.post("/api/v1/auth/login", json={
            "email": researcher_user.email,
            "password": RESEARCHER_PASSWORD,
        })
        assert "access_token" in resp.cookies

    def test_login_wrong_password(self, client: TestClient, researcher_user: User):
        resp = client.post("/api/v1/auth/login", json={
            "email": researcher_user.email,
            "password": "WrongPass1!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@iitu.edu.kz",
            "password": "Whatever1!",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client: TestClient, inactive_user: User):
        resp = client.post("/api/v1/auth/login", json={
            "email": inactive_user.email,
            "password": RESEARCHER_PASSWORD,
        })
        assert resp.status_code == 403


# ── Authenticated endpoint tests ─────────────────────────────────────

class TestAuthenticatedEndpoints:

    def test_get_me(self, client: TestClient, researcher_user: User, researcher_headers):
        resp = client.get("/api/v1/auth/me", headers=researcher_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == researcher_user.email

    def test_get_me_no_token(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # HTTPBearer returns 403 when no creds

    def test_get_me_invalid_token(self, client: TestClient):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_refresh_token(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/refresh", headers=researcher_headers)
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_logout(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/logout", headers=researcher_headers)
        assert resp.status_code == 200

    def test_update_profile(self, client: TestClient, researcher_headers):
        resp = client.patch("/api/v1/auth/me", headers=researcher_headers, json={
            "full_name": "Updated Name",
        })
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    def test_update_profile_empty_body(self, client: TestClient, researcher_headers):
        resp = client.patch("/api/v1/auth/me", headers=researcher_headers, json={})
        assert resp.status_code == 400


# ── Password change tests ────────────────────────────────────────────

class TestChangePassword:

    def test_change_password_success(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/change-password", headers=researcher_headers, json={
            "current_password": RESEARCHER_PASSWORD,
            "new_password": "NewSecure1234!",
        })
        assert resp.status_code == 200

    def test_change_password_wrong_current(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/change-password", headers=researcher_headers, json={
            "current_password": "WrongCurrent1!",
            "new_password": "NewSecure1234!",
        })
        assert resp.status_code == 401

    def test_change_password_same_password(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/change-password", headers=researcher_headers, json={
            "current_password": RESEARCHER_PASSWORD,
            "new_password": RESEARCHER_PASSWORD,
        })
        assert resp.status_code == 400

    def test_change_password_weak_new(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/change-password", headers=researcher_headers, json={
            "current_password": RESEARCHER_PASSWORD,
            "new_password": "weak",
        })
        assert resp.status_code == 422


# ── Terms re-acceptance tests ────────────────────────────────────────

class TestTerms:

    def test_reaccept_terms(self, client: TestClient, researcher_headers):
        resp = client.post("/api/v1/auth/reaccept-terms", headers=researcher_headers)
        assert resp.status_code == 200

    def test_expired_terms_user_can_reaccept(
        self, client: TestClient, expired_terms_user: User
    ):
        headers = make_auth_headers(expired_terms_user)
        resp = client.post("/api/v1/auth/reaccept-terms", headers=headers)
        assert resp.status_code == 200


# ── RBAC tests ────────────────────────────────────────────────────────

class TestRBAC:

    def test_researcher_cannot_access_admin_routes(
        self, client: TestClient, researcher_headers
    ):
        resp = client.get("/api/v1/admin/users", headers=researcher_headers)
        assert resp.status_code == 403

    def test_admin_can_access_admin_routes(
        self, client: TestClient, admin_headers
    ):
        resp = client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
