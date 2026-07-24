from core.admin_auth import create_admin_access_token, hash_password
from db import models


def _auth_header(admin_id: int):
    return {"Authorization": f"Bearer {create_admin_access_token(admin_id)}"}


def _seed_admin(db_session):
    admin = models.Admin(
        email="settings@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_business_settings_require_auth(client):
    assert client.get("/api/admin/business-settings").status_code == 401


def test_public_business_settings_defaults(client, db_session):
    response = client.get("/business-settings")
    assert response.status_code == 200
    data = response.json()
    assert data["open_hour"] == 9
    assert data["close_hour"] == 21
    assert data["off_weekdays"] == [4, 5, 6]
    assert data["holidays"] == []


def test_update_settings_and_holidays(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    updated = client.put(
        "/api/admin/business-settings",
        headers=headers,
        json={
            "open_hour": 10,
            "close_hour": 18,
            "slot_interval_minutes": 30,
            "buffer_minutes": 30,
            "off_weekdays": [5, 6],
            "max_advance_days": 14,
            "slot_lock_minutes": 5,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["open_hour"] == 10
    assert body["close_hour"] == 18
    assert body["off_weekdays"] == [5, 6]
    assert body["max_advance_days"] == 14

    created = client.post(
        "/api/admin/business-holidays",
        headers=headers,
        json={"holiday_date": "2030-02-01", "name": "測試休假"},
    )
    assert created.status_code == 201
    holiday_id = created.json()["id"]

    public = client.get("/business-settings")
    assert public.status_code == 200
    assert public.json()["open_hour"] == 10
    assert len(public.json()["holidays"]) == 1
    assert public.json()["holidays"][0]["holiday_date"] == "2030-02-01"

    deleted = client.delete(
        f"/api/admin/business-holidays/{holiday_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert client.get("/business-settings").json()["holidays"] == []


def test_invalid_hours_rejected(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)
    response = client.put(
        "/api/admin/business-settings",
        headers=headers,
        json={"open_hour": 18, "close_hour": 10},
    )
    assert response.status_code == 400
