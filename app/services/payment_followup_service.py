import asyncio
from datetime import datetime, timedelta
from typing import Set

from core.database import SessionLocal
from core.logging import get_logger
from common.utils import get_full_name
from db import repository
from services.line_service import send_line_message
from services.mail_tasks import send_owner_notification

logger = get_logger("payment_followup")

PAYMENT_WINDOW = timedelta(hours=1)
PAYMENT_REMINDER_MESSAGE = "匯款後請務必提供匯款資訊，才算預約成功呦！"

_scheduled_appointment_ids: Set[int] = set()


def _normalize_deadline(deadline: datetime) -> datetime:
    if deadline.tzinfo is not None:
        return deadline.replace(tzinfo=None)
    return deadline


async def _sleep_until(deadline: datetime):
    seconds = (_normalize_deadline(deadline) - datetime.now()).total_seconds()
    if seconds > 0:
        await asyncio.sleep(seconds)


def _is_followup_done(appointment) -> bool:
    return (
        appointment is None
        or appointment.paid
        or appointment.expired
        or appointment.payment_proof_received
        or appointment.owner_notified
    )


async def payment_followup_loop(appointment_id: int):
    """
    1) 到期仍未收到後五碼／截圖 → LINE 提醒案主，並延長匯款期限 1 小時
    2) 延長後再到期仍未提供 → 寄送 send_owner_notification 供業主最終確認
    """
    while True:
        db = SessionLocal()
        try:
            appointment = repository.get_appointment(db, appointment_id)
            if _is_followup_done(appointment):
                return
            deadline = appointment.payment_deadline_at
            if not deadline:
                return
        finally:
            db.close()

        await _sleep_until(deadline)

        db = SessionLocal()
        try:
            appointment = repository.get_appointment(db, appointment_id)
            if _is_followup_done(appointment):
                return

            if not appointment.payment_reminder_sent:
                line_user_id = appointment.client.line_user_id
                appointment.payment_reminder_sent = True
                appointment.payment_deadline_at = datetime.now() + PAYMENT_WINDOW
                db.commit()

                try:
                    send_line_message(line_user_id, PAYMENT_REMINDER_MESSAGE)
                except Exception as e:
                    logger.error(
                        "匯款提醒推播失敗 (appointment_id=%s): %s",
                        appointment_id,
                        e,
                        exc_info=True,
                    )

                logger.info(
                    "已延長匯款期限並提醒案主 (appointment_id=%s, new_deadline=%s)",
                    appointment_id,
                    appointment.payment_deadline_at,
                )
                continue

            full_name = get_full_name(appointment.client)
            appointment.owner_notified = True
            db.commit()

            try:
                await send_owner_notification(
                    appointment_id,
                    full_name,
                    last_five_digits="未提供",
                )
            except Exception as e:
                logger.error(
                    "最終業主通知失敗 (appointment_id=%s): %s",
                    appointment_id,
                    e,
                    exc_info=True,
                )
            logger.info("已寄出最終業主確認信 (appointment_id=%s)", appointment_id)
            return
        except Exception as e:
            logger.error(
                "匯款追蹤失敗 (appointment_id=%s): %s",
                appointment_id,
                e,
                exc_info=True,
            )
            return
        finally:
            db.close()


def schedule_payment_followup(appointment_id: int):
    if appointment_id in _scheduled_appointment_ids:
        return

    _scheduled_appointment_ids.add(appointment_id)

    async def _runner():
        try:
            await payment_followup_loop(appointment_id)
        finally:
            _scheduled_appointment_ids.discard(appointment_id)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        # 同步 FastAPI route 在 threadpool 執行，沒有 running loop。
        # 不可 asyncio.run()（會卡住整段匯款追蹤時間），改丟回主 loop。
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_runner(), loop)
            else:
                _scheduled_appointment_ids.discard(appointment_id)
                raise RuntimeError("event loop 未在執行，無法排程匯款追蹤")
        except Exception as e:
            _scheduled_appointment_ids.discard(appointment_id)
            logger.error(
                "排程匯款追蹤失敗 (appointment_id=%s): %s",
                appointment_id,
                e,
                exc_info=True,
            )
            return

    logger.info("已排程匯款追蹤 (appointment_id=%s)", appointment_id)


async def start_payment_followup(appointment_id: int):
    """供 FastAPI BackgroundTasks 呼叫：在 event loop 上非阻塞排程。"""
    schedule_payment_followup(appointment_id)


def resume_payment_followups():
    """服務重啟後，為尚未完成匯款追蹤的預約重新排程。"""
    db = SessionLocal()
    try:
        appointments = repository.get_appointments_needing_payment_followup(db)
        for appointment in appointments:
            schedule_payment_followup(appointment.id)
        logger.info("重啟後恢復匯款追蹤 %s 筆", len(appointments))
    except Exception as e:
        logger.error("恢復匯款追蹤失敗: %s", e, exc_info=True)
    finally:
        db.close()
