from datetime import timedelta

from core.admin_auth import (
    create_admin_access_token,
    hash_password,
    verify_admin_token,
    verify_password,
)
from core.security import create_access_token
from db import models


def test_hash_and_verify_password():
    hashed = hash_password("secret-password")
    assert hashed != "secret-password"
    assert verify_password("secret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_admin_token_roundtrip():
    token = create_admin_access_token(7)
    payload = verify_admin_token(token)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["type"] == "admin"


def test_approval_token_is_not_admin_token():
    token = create_access_token({"appointment_id": 42})
    assert verify_admin_token(token) is None


def test_expired_admin_token_returns_none():
    token = create_admin_access_token(
        1,
        expires_delta=timedelta(seconds=-1),
    )
    assert verify_admin_token(token) is None


def test_login_success(client, db_session):
    db_session.add(
        models.Admin(
            email="owner@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/admin/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_wrong_password(client, db_session):
    db_session.add(
        models.Admin(
            email="owner@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/admin/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/api/admin/me")
    assert response.status_code == 401


def test_me_with_admin_token(client, db_session):
    admin = models.Admin(
        email="owner@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    token = create_admin_access_token(admin.id)
    response = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_me_rejects_approval_token(client, db_session):
    admin = models.Admin(
        email="owner@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    approval_token = create_access_token({"appointment_id": admin.id})
    response = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {approval_token}"},
    )
    assert response.status_code == 401
