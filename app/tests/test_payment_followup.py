from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import payment_followup_service as followup


@pytest.mark.asyncio
async def test_first_timeout_sends_reminder_and_extends_deadline(db_session):
    from db import models

    client = models.Client(
        line_user_id="U_followup",
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
        payment_deadline_at=datetime.now() - timedelta(seconds=1),
        payment_proof_received=False,
        payment_reminder_sent=False,
        owner_notified=False,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    with patch.object(followup, "SessionLocal", return_value=db_session), patch.object(
        followup, "send_line_message"
    ) as mock_line, patch.object(
        followup, "_sleep_until", new_callable=AsyncMock
    ) as mock_sleep:
        call_count = {"n": 0}

        async def _sleep(_deadline):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                appointment.payment_proof_received = True
                db_session.commit()

        mock_sleep.side_effect = _sleep
        db_session.close = MagicMock()

        await followup.payment_followup_loop(appointment.id)

        mock_line.assert_called_once_with(
            "U_followup",
            "匯款後請務必提供匯款資訊，才算預約成功呦！",
        )
        db_session.refresh(appointment)
        assert appointment.payment_reminder_sent is True
        assert appointment.payment_deadline_at > datetime.now()


@pytest.mark.asyncio
async def test_second_timeout_cancels_and_deletes_appointment(db_session):
    from db import models

    client = models.Client(
        line_user_id="U_final",
        last_name="李",
        first_name="小華",
    )
    db_session.add(client)
    db_session.flush()

    appointment = models.Appointment(
        client_id=client.id,
        total_price=2222,
        paid=False,
        expired=False,
        service_dateTime=datetime(2030, 1, 7, 11, 0, 0),
        total_duration=60,
        payment_deadline_at=datetime.now() - timedelta(seconds=1),
        payment_proof_received=False,
        payment_reminder_sent=True,
        owner_notified=False,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    appointment_id = appointment.id

    with patch.object(followup, "SessionLocal", return_value=db_session), patch.object(
        followup, "send_line_message"
    ) as mock_line, patch.object(
        followup, "delete_pending_slot"
    ) as mock_unlock, patch.object(
        followup, "get_calendar_service"
    ) as mock_cal_gen, patch.object(
        followup, "delete_placeholder_calendar_event"
    ) as mock_delete_event, patch.object(
        followup, "_sleep_until", new_callable=AsyncMock
    ):
        mock_cal_gen.return_value = iter([MagicMock()])
        db_session.close = MagicMock()

        await followup.payment_followup_loop(appointment_id)

        mock_line.assert_called_once_with(
            "U_final",
            "收款逾期，您的預約已取消。請重新預約。",
        )
        mock_unlock.assert_called_once_with("2030-01-07", "11:00")
        mock_delete_event.assert_called_once()
        soft_deleted = (
            db_session.query(models.Appointment)
            .filter(models.Appointment.id == appointment_id)
            .first()
        )
        assert soft_deleted is not None
        assert soft_deleted.deleted_at is not None
        assert soft_deleted.expired is True
