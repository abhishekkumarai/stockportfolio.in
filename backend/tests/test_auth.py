"""Tests for authentication endpoints, password hashing, and user sessions."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import secrets
from app.db import get_db, is_enabled
from app.db.models import Base
from app.db import repo
from app.main import app


@pytest.fixture()
def test_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'auth_test.db'}", future=True)
    Base.metadata.create_all(engine)

    def _override_db():
        with Session(engine) as s:
            yield s

    # Force is_enabled to True for tests
    monkeypatch.setattr("app.routes.auth.is_enabled", lambda: True)
    app.dependency_overrides[get_db] = _override_db

    yield engine

    app.dependency_overrides.clear()
    engine.dispose()


def test_password_hashing():
    pwd = "SuperSecretPassword123!"
    hashed = secrets.hash_password(pwd)
    assert hashed != pwd
    assert secrets.verify_password(pwd, hashed)
    assert not secrets.verify_password("WrongPassword", hashed)


def test_signup_and_signin_flow(test_db):
    client = TestClient(app)

    # 1. Sign up new user
    signup_resp = client.post(
        "/api/auth/signup",
        json={
            "email": "analyst@stockportfolio.in",
            "password": "Password123!",
            "display_name": "Quant Analyst",
        },
    )
    assert signup_resp.status_code == 200
    data = signup_resp.json()
    assert "token" in data
    assert data["user"]["email"] == "analyst@stockportfolio.in"
    assert data["user"]["display_name"] == "Quant Analyst"
    token = data["token"]

    # 2. Duplicate signup should be rejected with 409
    dup_resp = client.post(
        "/api/auth/signup",
        json={
            "email": "analyst@stockportfolio.in",
            "password": "Password123!",
        },
    )
    assert dup_resp.status_code == 409

    # 3. Sign in with correct password
    signin_resp = client.post(
        "/api/auth/signin",
        json={
            "email": "analyst@stockportfolio.in",
            "password": "Password123!",
        },
    )
    assert signin_resp.status_code == 200
    signin_data = signin_resp.json()
    assert "token" in signin_data
    assert signin_data["user"]["email"] == "analyst@stockportfolio.in"
    new_token = signin_data["token"]

    # 4. Sign in with invalid password
    bad_resp = client.post(
        "/api/auth/signin",
        json={
            "email": "analyst@stockportfolio.in",
            "password": "WrongPassword!",
        },
    )
    assert bad_resp.status_code == 401

    # 5. Access /api/auth/me with Bearer token
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "analyst@stockportfolio.in"

    # 6. Logout rotates key
    logout_resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert logout_resp.status_code == 200

    # 7. Old token should now be unauthorized
    unauth_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert unauth_resp.status_code == 401
