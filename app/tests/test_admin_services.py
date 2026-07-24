from core.admin_auth import create_admin_access_token, hash_password
from db import models


def _create_admin(db_session):
    admin = models.Admin(
        email="owner@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _auth_header(admin_id: int):
    token = create_admin_access_token(admin_id)
    return {"Authorization": f"Bearer {token}"}


def _seed_category_and_service(db_session):
    category = models.Category(category_name="阿卡西解讀")
    db_session.add(category)
    db_session.flush()
    service = models.Service(
        service_name="核心解讀",
        category_id=category.id,
        price=2222,
        duration_minutes=60,
        is_active=True,
        sort_order=1,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(category)
    db_session.refresh(service)
    return category, service


def test_admin_services_require_auth(client):
    assert client.get("/api/admin/services").status_code == 401
    assert client.get("/api/admin/categories").status_code == 401
    assert (
        client.post(
            "/api/admin/services",
            json={
                "service_name": "x",
                "category_id": 1,
                "price": 100,
                "duration_minutes": 60,
            },
        ).status_code
        == 401
    )


def test_admin_service_crud(client, db_session):
    admin = _create_admin(db_session)
    category, service = _seed_category_and_service(db_session)
    headers = _auth_header(admin.id)

    listed = client.get("/api/admin/services", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["service_name"] == "核心解讀"
    assert listed.json()[0]["category_name"] == "阿卡西解讀"

    created = client.post(
        "/api/admin/services",
        headers=headers,
        json={
            "service_name": "進階解讀",
            "category_id": category.id,
            "price": 3000,
            "duration_minutes": 90,
            "is_active": True,
            "sort_order": 2,
        },
    )
    assert created.status_code == 201
    created_id = created.json()["id"]
    assert created.json()["price"] == 3000

    updated = client.put(
        f"/api/admin/services/{created_id}",
        headers=headers,
        json={"price": 3500, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == 3500
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/admin/services/{created_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["action"] == "deleted"

    # 已被預約引用的服務只能停用
    client_row = models.Client(
        line_user_id="U_test",
        last_name="測",
        first_name="試",
    )
    db_session.add(client_row)
    db_session.flush()
    appointment = models.Appointment(
        client_id=client_row.id,
        total_price=2222,
        paid=False,
        total_duration=60,
    )
    db_session.add(appointment)
    db_session.flush()
    db_session.add(
        models.AppointmentItem(
            appointment_id=appointment.id,
            service_id=service.id,
        )
    )
    db_session.commit()

    disabled = client.delete(f"/api/admin/services/{service.id}", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["action"] == "disabled"
    db_session.refresh(service)
    assert service.is_active is False


def test_admin_services_reorder(client, db_session):
    admin = _create_admin(db_session)
    category, first = _seed_category_and_service(db_session)
    second = models.Service(
        service_name="進階解讀",
        category_id=category.id,
        price=3000,
        duration_minutes=90,
        is_active=True,
        sort_order=2,
    )
    db_session.add(second)
    db_session.commit()
    db_session.refresh(second)
    headers = _auth_header(admin.id)

    response = client.put(
        "/api/admin/services/reorder",
        headers=headers,
        json={
            "items": [
                {"id": second.id, "sort_order": 0},
                {"id": first.id, "sort_order": 1},
            ]
        },
    )
    assert response.status_code == 200
    names = [item["service_name"] for item in response.json()]
    assert names[:2] == ["進階解讀", "核心解讀"]
    assert response.json()[0]["sort_order"] == 0
    assert response.json()[1]["sort_order"] == 1


def test_public_services_filter_hides_inactive(client, db_session):
    category, service = _seed_category_and_service(db_session)
    service.is_active = False
    db_session.commit()

    response = client.get(f"/services/filter?category_id={category.id}")
    assert response.status_code == 200
    assert response.json() == []
