from core.request_logging import _build_context, _sanitize


def test_sanitize_hides_token():
    data = {"token": "secret", "action": "success"}
    assert _sanitize(data) == {"token": "***", "action": "success"}


def test_build_context_from_query():
    context = _build_context("/available-slots", {"date": "2030-01-07"}, None)
    assert "date=2030-01-07" in context


def test_build_context_from_appointment_body():
    body = {
        "line_user_id": "U123",
        "first_name": "小明",
        "last_name": "王",
        "date": "2030-01-07",
    }
    context = _build_context("/appointments/", {}, body)
    assert "line_user_id=U123" in context
    assert "first_name=小明" in context


def test_build_context_masks_approve_token():
    context = _build_context("/approve", {"token": "jwt-here", "action": "success"}, None)
    assert "token=***" in context
    assert "jwt-here" not in context
