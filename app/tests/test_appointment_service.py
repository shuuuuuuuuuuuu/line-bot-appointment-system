from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from services.appointment_service import process_appointment_approval
from db import models


def _make_appointment(db_session):
    client = models.Client(
        line_user_id="U123",
        last_name="王",
        first_name="小明",
    )
    db_session.add(client)
    db_session.flush()

    appointment = models.Appointment(
        client_id=client.id,
        total_price=2222,
        paid=False,
        expired=False,
        service_dateTime=datetime(2030, 1, 7, 10, 0, 0),
        total_duration=60,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


@patch("services.appointment_service.send_line_message")
@patch("services.appointment_service.confirm_calendar_event")
@patch("services.appointment_service.delete_pending_slot")
def test_approval_success_without_calendar(
    mock_delete_slot,
    mock_confirm_event,
    mock_send_line,
    db_session,
):
    appointment = _make_appointment(db_session)

    result = process_appointment_approval(
        db_session,
        appointment.id,
        "success",
        calendar_service=None,
    )

    assert result.paid is True
    mock_send_line.assert_called_once()
    mock_confirm_event.assert_called_once()
    mock_delete_slot.assert_called_once()


@patch("services.appointment_service.send_line_message")
@patch("services.appointment_service.confirm_calendar_event")
@patch("services.appointment_service.delete_placeholder_calendar_event")
@patch("services.appointment_service.delete_pending_slot")
def test_repeated_approval_does_not_send_line_again(
    mock_delete_slot,
    mock_delete_event,
    mock_confirm_event,
    mock_send_line,
    db_session,
):
    appointment = _make_appointment(db_session)

    first_result = process_appointment_approval(
        db_session,
        appointment.id,
        "success",
        calendar_service=None,
    )
    repeated_result = process_appointment_approval(
        db_session,
        appointment.id,
        "reject",
        calendar_service=None,
    )

    assert first_result.paid is True
    assert repeated_result.paid is True
    assert repeated_result.expired is False
    mock_send_line.assert_called_once()
    mock_confirm_event.assert_called_once()
    mock_delete_event.assert_not_called()
    mock_delete_slot.assert_called_once()


@patch("services.appointment_service.send_line_message")
@patch("services.appointment_service.delete_placeholder_calendar_event")
@patch("services.appointment_service.delete_pending_slot")
def test_approval_reject_deletes_placeholder(
    mock_delete_slot,
    mock_delete_event,
    mock_send_line,
    db_session,
):
    appointment = _make_appointment(db_session)

    result = process_appointment_approval(
        db_session,
        appointment.id,
        "reject",
        calendar_service=None,
    )

    assert result.expired is True
    assert result.paid is False
    mock_send_line.assert_called_once()
    mock_delete_event.assert_called_once()
    mock_delete_slot.assert_called_once()


@patch("services.appointment_service.send_line_message")
def test_approval_not_found(mock_send_line, db_session):
    with pytest.raises(HTTPException) as exc:
        process_appointment_approval(db_session, 9999, "success", None)
    assert exc.value.status_code == 404
    mock_send_line.assert_not_called()
