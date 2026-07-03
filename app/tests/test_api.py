def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_logging_emits_access_log(client, seeded_db, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="line_bot.access"):
        response = client.get("/categories")

    assert response.status_code == 200
    assert any("GET /categories 200" in record.message for record in caplog.records)


def test_categories_empty(client):
    response = client.get("/categories")
    assert response.status_code == 200
    assert response.json() == []


def test_categories_with_data(client, seeded_db):
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["category_name"] == "阿卡西解讀"


def test_services_filter(client, seeded_db):
    response = client.get("/services/filter?category_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["service_name"] == "感情與人際的糾葛"


def test_available_slots_weekday(client, seeded_db):
    response = client.get("/available-slots?date=2030-01-07")
    assert response.status_code == 200
    slots = response.json()["available_slots"]
    assert "09:00" in slots


def test_available_slots_off_day(client, seeded_db):
    response = client.get("/available-slots?date=2030-01-04")
    assert response.status_code == 200
    assert response.json()["available_slots"] == []


def test_slot_lock_missing_params(client):
    response = client.post("/api/slot/lock", json={"date": "2030-01-07"})
    assert response.status_code == 400


def test_approve_invalid_token(client, seeded_db):
    response = client.get("/approve?token=invalid&action=success")
    assert response.status_code == 403
