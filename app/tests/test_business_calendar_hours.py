from datetime import date, timedelta

from core.admin_auth import create_admin_access_token, hash_password
from db import models
from services.business_hours import resolve_business_hours_for_date_str


def _auth_header(admin_id: int):
    return {"Authorization": f"Bearer {create_admin_access_token(admin_id)}"}


def _seed_admin(db_session):
    admin = models.Admin(
        email="calendar@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _weekly_payload(overrides=None):
    overrides = overrides or {}
    items = []
    for weekday in range(7):
        item = {
            "weekday": weekday,
            "is_open": weekday < 4,
            "open_hour": 9,
            "close_hour": 21,
        }
        if weekday in overrides:
            item.update(overrides[weekday])
        items.append(item)
    return {"items": items}


def _next_weekday(target_weekday: int) -> str:
    today = date.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (today + timedelta(days=days_ahead)).isoformat()


def _ensure_bookable_window(client, headers):
    client.put(
        "/api/admin/business-settings",
        headers=headers,
        json={"max_advance_days": 3650},
    )


def test_public_settings_include_weekly_and_overrides(client, db_session):
    response = client.get("/business-settings")
    assert response.status_code == 200
    data = response.json()
    assert len(data["weekly_hours"]) == 7
    assert data["date_overrides"] == []
    assert data["off_weekdays"] == [4, 5, 6]


def test_update_weekly_hours_per_day(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    response = client.put(
        "/api/admin/business-settings/weekly-hours",
        headers=headers,
        json=_weekly_payload({
            0: {"open_hour": 10, "close_hour": 18},
            1: {"open_hour": 11, "close_hour": 19},
        }),
    )
    assert response.status_code == 200
    monday = next(item for item in response.json()["weekly_hours"] if item["weekday"] == 0)
    tuesday = next(item for item in response.json()["weekly_hours"] if item["weekday"] == 1)
    assert monday["open_hour"] == 10
    assert tuesday["open_hour"] == 11


def test_weekly_hours_persist_multiple_time_slots(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    payload = _weekly_payload()
    monday = next(item for item in payload["items"] if item["weekday"] == 0)
    monday["time_slots"] = [
        {"open_hour": 8, "close_hour": 12},
        {"open_hour": 20, "close_hour": 22},
    ]
    monday["open_hour"] = 8
    monday["close_hour"] = 22

    response = client.put(
        "/api/admin/business-settings/weekly-hours",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200
    saved_monday = next(item for item in response.json()["weekly_hours"] if item["weekday"] == 0)
    assert saved_monday["time_slots"] == [
        {"open_hour": 8, "close_hour": 12},
        {"open_hour": 20, "close_hour": 22},
    ]

    reloaded = client.get("/business-settings")
    assert reloaded.status_code == 200
    reloaded_monday = next(
        item for item in reloaded.json()["weekly_hours"] if item["weekday"] == 0
    )
    assert reloaded_monday["time_slots"] == [
        {"open_hour": 8, "close_hour": 12},
        {"open_hour": 20, "close_hour": 22},
    ]


def test_date_override_special_closed_and_open(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    closed = client.post(
        "/api/admin/business-settings/date-overrides",
        headers=headers,
        json={
            "target_date": "2030-02-01",
            "is_open": False,
            "note": "國定假日",
        },
    )
    assert closed.status_code == 201
    override_id = closed.json()["id"]

    resolved_closed = resolve_business_hours_for_date_str(db_session, "2030-02-01")
    assert resolved_closed.is_open is False

    open_override = client.post(
        "/api/admin/business-settings/date-overrides",
        headers=headers,
        json={
            "target_date": "2030-02-07",
            "is_open": True,
            "open_hour": 12,
            "close_hour": 16,
            "note": "週五臨時營業",
        },
    )
    assert open_override.status_code == 201

    resolved_open = resolve_business_hours_for_date_str(db_session, "2030-02-07")
    assert resolved_open.is_open is True
    assert resolved_open.open_hour == 12
    assert resolved_open.close_hour == 16

    deleted = client.delete(
        f"/api/admin/business-settings/date-overrides/{override_id}",
        headers=headers,
    )
    assert deleted.status_code == 200


def test_available_slots_respects_override_hours(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)
    target_date = _next_weekday(0)
    _ensure_bookable_window(client, headers)
    client.put(
        "/api/admin/business-settings",
        headers=headers,
        json={"slot_interval_minutes": 30},
    )

    client.put(
        "/api/admin/business-settings/weekly-hours",
        headers=headers,
        json=_weekly_payload(),
    )
    client.post(
        "/api/admin/business-settings/date-overrides",
        headers=headers,
        json={
            "target_date": target_date,
            "is_open": True,
            "open_hour": 10,
            "close_hour": 12,
        },
    )

    response = client.get("/available-slots", params={"date": target_date})
    assert response.status_code == 200
    assert response.json()["available_slots"] == ["10:00", "10:30", "11:00", "11:30"]


def test_create_appointment_rejects_closed_day(client, db_session, seeded_db):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    client.post(
        "/api/admin/business-settings/date-overrides",
        headers=headers,
        json={"target_date": "2030-02-01", "is_open": False},
    )

    response = client.post(
        "/appointments/",
        json={
            "line_user_id": "U123",
            "last_name": "王",
            "first_name": "小明",
            "category": "阿卡西解讀",
            "service_items": ["感情與人際的糾葛"],
            "user_message": "測試",
            "total_price": 1000,
            "total_duration": 60,
            "service_dateTime": "2030-02-01T10:00:00",
        },
    )
    assert response.status_code == 400
    assert "非營業日" in response.json()["detail"]


def test_create_appointment_rejects_outside_hours(client, db_session, seeded_db):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)
    target_date = _next_weekday(0)
    _ensure_bookable_window(client, headers)

    client.put(
        "/api/admin/business-settings/weekly-hours",
        headers=headers,
        json=_weekly_payload({0: {"open_hour": 10, "close_hour": 12}}),
    )

    response = client.post(
        "/appointments/",
        json={
            "line_user_id": "U123",
            "last_name": "王",
            "first_name": "小明",
            "category": "阿卡西解讀",
            "service_items": ["感情與人際的糾葛"],
            "user_message": "測試",
            "total_price": 1000,
            "total_duration": 60,
            "service_dateTime": f"{target_date}T09:00:00",
        },
    )
    assert response.status_code == 400
    assert "不在營業時段內" in response.json()["detail"]


def test_legacy_holiday_api_still_works(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    created = client.post(
        "/api/admin/business-holidays",
        headers=headers,
        json={"holiday_date": "2030-03-01", "name": "測試休假"},
    )
    assert created.status_code == 201

    settings = client.get("/business-settings").json()
    assert any(item["target_date"] == "2030-03-01" for item in settings["date_overrides"])
    assert any(item["holiday_date"] == "2030-03-01" for item in settings["holidays"])

    holiday_id = created.json()["id"]
    deleted = client.delete(f"/api/admin/business-holidays/{holiday_id}", headers=headers)
    assert deleted.status_code == 200


def test_legacy_settings_update_syncs_weekly_template(client, db_session):
    admin = _seed_admin(db_session)
    headers = _auth_header(admin.id)

    updated = client.put(
        "/api/admin/business-settings",
        headers=headers,
        json={
            "open_hour": 10,
            "close_hour": 18,
            "off_weekdays": [5, 6],
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["open_hour"] == 10
    assert body["close_hour"] == 18
    assert body["off_weekdays"] == [5, 6]

    friday = next(item for item in body["weekly_hours"] if item["weekday"] == 4)
    saturday = next(item for item in body["weekly_hours"] if item["weekday"] == 5)
    assert friday["is_open"] is True
    assert saturday["is_open"] is False
