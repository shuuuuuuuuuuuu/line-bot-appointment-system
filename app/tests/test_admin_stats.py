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
    paid = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=True,
        expired=False,
        service_dateTime=now + timedelta(days=2),
        total_duration=60,
    )
    pending = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=False,
        expired=False,
        service_dateTime=now + timedelta(days=3),
        total_duration=60,
        payment_proof_received=False,
    )
    review = models.Appointment(
        client_id=client.id,
        total_price=2000,
        paid=False,
        expired=False,
        service_dateTime=now + timedelta(days=4),
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
