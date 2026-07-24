from core.admin_auth import create_admin_access_token, hash_password
from db import models


def _auth_header(admin_id: int):
    return {"Authorization": f"Bearer {create_admin_access_token(admin_id)}"}


def _seed(db_session):
    admin = models.Admin(
        email="owner@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(admin)
    category = models.Category(category_name="阿卡西解讀")
    db_session.add(category)
    db_session.flush()
    template = models.MessageTemplate(
        key="payment_reminder",
        name="匯款提醒",
        category_id=None,
        body="請盡快完成匯款",
        description="無變數",
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(template)
    return admin, template


def test_message_templates_require_auth(client):
    assert client.get("/api/admin/message-templates").status_code == 401


def test_list_and_update_message_template(client, db_session):
    admin, template = _seed(db_session)
    headers = _auth_header(admin.id)

    listed = client.get("/api/admin/message-templates", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["key"] == "payment_reminder"

    updated = client.put(
        f"/api/admin/message-templates/{template.id}",
        headers=headers,
        json={"body": "更新後的提醒文案", "name": "匯款提醒（新）"},
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "更新後的提醒文案"
    assert updated.json()["name"] == "匯款提醒（新）"
