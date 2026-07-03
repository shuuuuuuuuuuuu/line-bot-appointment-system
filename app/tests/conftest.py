import os
import sys

import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# 測試用 SQLite，需在 import main 前替換 database engine
import core.database as database_module
from db.models import Base

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
database_module.engine = _test_engine
database_module.SessionLocal = _test_session_local

from core.database import get_db
from main import app
from db import models


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr("services.available_slots.r", fake)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    session = _test_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_db(db_session):
    cat1 = models.Category(id=1, category_name="阿卡西解讀")
    cat2 = models.Category(id=2, category_name="頌缽")
    db_session.add_all([cat1, cat2])
    db_session.add(models.Service(id=1, service_name="感情與人際的糾葛", category_id=1))
    db_session.add(models.Service(id=2, service_name="頌缽療癒", category_id=2))
    db_session.commit()
    return db_session
