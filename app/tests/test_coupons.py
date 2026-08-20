from datetime import date, datetime, timedelta

from core.admin_auth import create_admin_access_token, hash_password
from db import models


def _create_admin(db_session):
    admin = models.Admin(
        email="coupon-admin@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _auth_header(admin_id: int):
    return {"Authorization": f"Bearer {create_admin_access_token(admin_id)}"}


def _seed_categories(db_session):
    sound = models.Category(category_name="頌缽")
    akashic = models.Category(category_name="阿卡西解讀")
    db_session.add_all([sound, akashic])
    db_session.flush()
    service = models.Service(
        service_name="頌缽療癒",
        category_id=sound.id,
        price=3333,
        duration_minutes=70,
        is_active=True,
        sort_order=0,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(sound)
    db_session.refresh(akashic)
    db_session.refresh(service)
    return sound, akashic, service


def test_admin_coupons_require_auth(client):
    assert client.get("/api/admin/coupons").status_code == 401


def test_admin_coupon_crud(client, db_session):
    admin = _create_admin(db_session)
    sound, _, _ = _seed_categories(db_session)
    headers = _auth_header(admin.id)
    today = date.today()

    created = client.post(
        "/api/admin/coupons",
        headers=headers,
        json={
            "name": "頌缽療癒體驗活動",
            "code": "20260802_soundhealing_50",
            "category_id": sound.id,
            "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=30)).isoformat(),
            "max_uses": 100,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["discount_percent"] == 50
    assert body["service_slug"] == "soundhealing"
    assert body["category_id"] == sound.id
    assert body["category_name"] == "頌缽"
    coupon_id = body["id"]

    listed = client.get("/api/admin/coupons", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/api/admin/coupons/{coupon_id}",
        headers=headers,
        json={"name": "更新後活動", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "更新後活動"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/admin/coupons/{coupon_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["action"] == "deleted"


def test_coupon_requires_eligibility_and_matching_category(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "api.public.send_payment_instruction", lambda data: None
    )
    monkeypatch.setattr(
        "api.public.start_payment_followup", lambda appointment_id: None
    )

    sound, _, _ = _seed_categories(db_session)
    admin = _create_admin(db_session)
    headers = _auth_header(admin.id)
    today = date.today()

    created = client.post(
        "/api/admin/coupons",
        headers=headers,
        json={
            "name": "頌缽療癒體驗活動",
            "code": "20260802_soundhealing_50",
            "category_id": sound.id,
            "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=7)).isoformat(),
        },
    )
    assert created.status_code == 201
    coupon_id = created.json()["id"]

    # 未在發放名單 → 優惠碼無效（朋友轉傳）
    not_eligible = client.post(
        "/coupons/validate",
        json={
            "code": "20260802_soundhealing_50",
            "line_user_id": "U_friend",
            "category": "頌缽",
            "base_price": 3333,
        },
    )
    assert not_eligible.status_code == 400
    assert not_eligible.json()["detail"] == "優惠碼無效"

    added = client.post(
        f"/api/admin/coupons/{coupon_id}/eligibilities",
        headers=headers,
        json={"line_user_ids": ["U_coupon_1", "U_coupon_2"]},
    )
    assert added.status_code == 200
    assert len(added.json()) == 2

    # 選阿卡西卻套用頌缽折扣 → 阻擋
    wrong_category = client.post(
        "/coupons/validate",
        json={
            "code": "20260802_soundhealing_50",
            "line_user_id": "U_coupon_1",
            "category": "阿卡西解讀",
            "base_price": 3333,
        },
    )
    assert wrong_category.status_code == 400
    assert "服務類別" in wrong_category.json()["detail"]

    validated = client.post(
        "/coupons/validate",
        json={
            "code": "20260802_soundhealing_50",
            "line_user_id": "U_coupon_1",
            "category": "頌缽",
            "base_price": 3333,
        },
    )
    assert validated.status_code == 200
    assert validated.json()["discounted_price"] == 1666

    future = datetime.now() + timedelta(days=2)
    booked = client.post(
        "/appointments/",
        json={
            "line_user_id": "U_coupon_1",
            "last_name": "王",
            "first_name": "小明",
            "category": "頌缽",
            "service_items": ["頌缽療癒"],
            "total_price": 1666,
            "total_duration": 70,
            "service_dateTime": future.strftime("%Y-%m-%dT%H:%M:%S"),
            "coupon_code": "20260802_soundhealing_50",
        },
    )
    assert booked.status_code == 200
    assert booked.json()["total_price"] == 1666


def test_new_customer_via_line_contact(client, db_session):
    sound, _, _ = _seed_categories(db_session)
    admin = _create_admin(db_session)
    headers = _auth_header(admin.id)
    today = date.today()

    db_session.add(
        models.LineContact(
            line_user_id="U_new_customer",
            display_name="小華",
        )
    )
    db_session.commit()

    created = client.post(
        "/api/admin/coupons",
        headers=headers,
        json={
            "name": "頌缽療癒體驗活動",
            "code": "20260802_soundhealing_50",
            "category_id": sound.id,
            "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=7)).isoformat(),
        },
    )
    coupon_id = created.json()["id"]

    contacts = client.get("/api/admin/line-contacts", headers=headers)
    assert contacts.status_code == 200
    assert any(c["display_name"] == "小華" for c in contacts.json())

    added = client.post(
        f"/api/admin/coupons/{coupon_id}/eligibilities",
        headers=headers,
        json={"line_user_ids": ["U_new_customer"]},
    )
    assert added.status_code == 200
    assert added.json()[0]["display_name"] == "小華"

    validated = client.post(
        "/coupons/validate",
        json={
            "code": "20260802_soundhealing_50",
            "line_user_id": "U_new_customer",
            "category": "頌缽",
            "base_price": 3333,
        },
    )
    assert validated.status_code == 200
    admin = _create_admin(db_session)
    sound, _, _ = _seed_categories(db_session)
    headers = _auth_header(admin.id)
    today = date.today()

    created = client.post(
        "/api/admin/coupons",
        headers=headers,
        json={
            "name": "過期活動",
            "code": "20260101_soundhealing_50",
            "category_id": sound.id,
            "valid_from": (today - timedelta(days=10)).isoformat(),
            "valid_to": (today - timedelta(days=1)).isoformat(),
        },
    )
    coupon_id = created.json()["id"]
    client.post(
        f"/api/admin/coupons/{coupon_id}/eligibilities",
        headers=headers,
        json={"line_user_ids": ["U_expired"]},
    )

    response = client.post(
        "/coupons/validate",
        json={
            "code": "20260101_soundhealing_50",
            "line_user_id": "U_expired",
            "category": "頌缽",
            "base_price": 3333,
        },
    )
    assert response.status_code == 400
    assert "過期" in response.json()["detail"]
