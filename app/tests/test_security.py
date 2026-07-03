from datetime import timedelta

from core.security import create_access_token, verify_token


def test_create_and_verify_token():
    token = create_access_token({"appointment_id": 42})
    payload = verify_token(token)
    assert payload is not None
    assert payload["appointment_id"] == 42


def test_invalid_token_returns_none():
    assert verify_token("not-a-valid-token") is None


def test_expired_token_returns_none():
    token = create_access_token(
        {"appointment_id": 1},
        expires_delta=timedelta(seconds=-1),
    )
    assert verify_token(token) is None
