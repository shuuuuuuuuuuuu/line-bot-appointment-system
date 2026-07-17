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
        followup, "send_owner_notification", new_callable=AsyncMock
    ) as mock_mail, patch.object(
        followup, "_sleep_until", new_callable=AsyncMock
    ) as mock_sleep:
        # First sleep -> reminder; second sleep -> stop after we mark owner_notified manually mid-loop
        call_count = {"n": 0}

        async def _sleep(_deadline):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                # After reminder, pretend proof arrived so loop exits
                appointment.payment_proof_received = True
                db_session.commit()

        mock_sleep.side_effect = _sleep

        # SessionLocal() is used as context via try/finally close - need close method
        db_session.close = MagicMock()

        await followup.payment_followup_loop(appointment.id)

        mock_line.assert_called_once_with(
            "U_followup",
            followup.PAYMENT_REMINDER_MESSAGE,
        )
        mock_mail.assert_not_called()
        db_session.refresh(appointment)
        assert appointment.payment_reminder_sent is True
        assert appointment.payment_deadline_at > datetime.now()


@pytest.mark.asyncio
async def test_second_timeout_notifies_owner(db_session):
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

    with patch.object(followup, "SessionLocal", return_value=db_session), patch.object(
        followup, "send_line_message"
    ) as mock_line, patch.object(
        followup, "send_owner_notification", new_callable=AsyncMock
    ) as mock_mail, patch.object(
        followup, "_sleep_until", new_callable=AsyncMock
    ):
        db_session.close = MagicMock()
        await followup.payment_followup_loop(appointment.id)

        mock_line.assert_not_called()
        mock_mail.assert_awaited_once()
        assert mock_mail.await_args.args[0] == appointment.id
        assert mock_mail.await_args.kwargs["last_five_digits"] == "未提供"
        db_session.refresh(appointment)
        assert appointment.owner_notified is True
