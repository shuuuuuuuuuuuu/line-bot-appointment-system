from calendar import monthrange
from datetime import datetime, timedelta

from core.admin_auth import create_admin_access_token, hash_password
from db import models


def _auth_header(admin_id: int):
    return {"Authorization": f"Bearer {create_admin_access_token(admin_id)}"}


def _seed(db_session):
    admin = models.Admin(
        email="stats@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    category = models.Category(category_name="阿卡西解讀")
    db_session.add(category)
    db_session.flush()
    service = models.Service(
        service_name="感情與人際",
        category_id=category.id,
        price=2000,
        duration_minutes=60,
    )
    db_session.add(service)
    client = models.Client(
        line_user_id="U_stats_1",
        last_name="王",
        first_name="小明",
    )
    db_session.add(client)
    db_session.flush()

    now = datetime.now()
    last_day = monthrange(now.year, now.month)[1]
    # Keep all seeded appointments inside the current month and in the future
    anchor = datetime(now.year, now.month, last_day, 10, 0)
    if anchor <= now:
        anchor = now + timedelta(hours=1)

    paid = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=True,
        expired=False,
        service_dateTime=anchor,
        total_duration=60,
    )
    pending = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=False,
        expired=False,
        service_dateTime=anchor + timedelta(hours=1),
        total_duration=60,
        payment_proof_received=False,
    )
    review = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=False,
        expired=False,
        service_dateTime=anchor + timedelta(hours=2),
        total_duration=60,
        payment_proof_received=True,
    )
    db_session.add_all([paid, pending, review])
    db_session.flush()
    db_session.add(
        models.AppointmentItem(appointment_id=paid.id, service_id=service.id)
    )
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_stats_require_auth(client):
    assert client.get("/api/admin/stats").status_code == 401


def test_stats_summary(client, db_session):
    admin = _seed(db_session)
    response = client.get(
        "/api/admin/stats?period=month",
        headers=_auth_header(admin.id),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "month"
    assert data["confirmed_count"] == 1
    assert data["revenue"] == 2000
    assert data["pending_payment_count"] == 1
    assert data["awaiting_review_count"] == 1
    assert data["upcoming_count"] == 1
    assert len(data["by_category"]) == 1
    assert data["by_category"][0]["category_name"] == "阿卡西解讀"
    assert len(data["upcoming_appointments"]) == 1
    assert len(data["recent_appointments"]) == 3
    recent = data["recent_appointments"][0]
    assert "user_message" in recent
    assert "created_at" in recent
    assert "payment_proof_received" in recent
    assert "trend" in data
    assert isinstance(data["trend"], list)
    assert len(data["trend"]) >= 28  # days in month
    assert {"label", "confirmed_count", "revenue", "cancelled_count"} <= set(
        data["trend"][0].keys()
    )
    assert "by_akashic_service" in data
    assert len(data["by_akashic_service"]) == 1
    assert data["by_akashic_service"][0]["service_name"] == "感情與人際"
    assert data["by_akashic_service"][0]["booking_count"] == 1


def test_export_appointments_excel(client, db_session):
    admin = _seed(db_session)
    response = client.post(
        "/api/admin/stats/appointments/export",
        headers=_auth_header(admin.id),
        json={"period": "month"},
    )
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers.get("content-type", "")
    assert response.content[:2] == b"PK"  # xlsx zip header


def test_export_appointments_respects_ids(client, db_session):
    admin = _seed(db_session)
    listed = client.get(
        "/api/admin/stats?period=month",
        headers=_auth_header(admin.id),
    )
    rows = listed.json()["recent_appointments"]
    assert len(rows) == 3
    keep_id = rows[0]["id"]

    response = client.post(
        "/api/admin/stats/appointments/export",
        headers=_auth_header(admin.id),
        json={"period": "month", "appointment_ids": [keep_id]},
    )
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
