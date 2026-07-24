from sqlalchemy.orm import Session
from fastapi import HTTPException
from db import repository
from services.available_slots import delete_pending_slot
from services.line_service import send_line_message
from services.google_calendar_service import (
    confirm_calendar_event,
    delete_placeholder_calendar_event,
)
from services.message_template_service import get_rendered_message
from common.utils import format_appointment_time, get_full_name
from core.logging import get_logger

logger = get_logger("appointment_service")

def process_appointment_approval(db: Session, appointment_id: int, action: str, calendar_service):
    appointment = repository.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")
    
    if not hasattr(appointment, 'client') or not appointment.client:
        raise HTTPException(status_code=400, detail="此預約缺乏關聯的客戶資料")

    updated_appointment, is_first_action = repository.update_appointment_status(
        db,
        appointment_id,
        action,
    )
    if not updated_appointment:
        raise HTTPException(status_code=500, detail="資料庫更新失敗")
    if not is_first_action:
        logger.info(
            "預約審核已處理，略過重複操作 (appointment_id=%s, action=%s)",
            appointment_id,
            action,
        )
        return updated_appointment

    try:
        service_dt = updated_appointment.service_dateTime
        delete_pending_slot(service_dt.strftime("%Y-%m-%d"), service_dt.strftime("%H:%M"))
    except Exception as e:
        logger.warning("Redis 解鎖失敗 (appointment_id=%s): %s", appointment_id, e)

    full_name = get_full_name(updated_appointment.client)
    time_display = format_appointment_time(updated_appointment.service_dateTime)
    category_name = repository.get_appointment_category_name(updated_appointment)
    first_name = updated_appointment.client.first_name
    variables = {
        "time_display": time_display,
        "first_name": first_name,
        "full_name": full_name,
    }
    
    is_paid = (action == "success")
    if is_paid:
        msg = get_rendered_message(
            db,
            "approval_success",
            category_name=category_name,
            variables=variables,
            fallback=f"預約成功！已收到您的款項\n我們 {time_display} 見😊",
        )
        try:
            confirm_calendar_event(
                service=calendar_service,
                client_name=full_name,
                start_dt=updated_appointment.service_dateTime,
                category=category_name,
                event_id=getattr(updated_appointment, "google_event_id", None),
            )
        except Exception as e:
            logger.error("Google Calendar 同步失敗 (appointment_id=%s): %s", appointment_id, e, exc_info=True)
    else:
        msg = get_rendered_message(
            db,
            "approval_reject",
            variables=variables,
            fallback="您的預約已取消。請重新預約。",
        )
        try:
            delete_placeholder_calendar_event(
                service=calendar_service,
                client_name=full_name,
                start_dt=updated_appointment.service_dateTime,
                category=category_name,
                event_id=getattr(updated_appointment, "google_event_id", None),
            )
        except Exception as e:
            logger.error(
                "Google Calendar 刪除 placeholder 失敗 (appointment_id=%s): %s",
                appointment_id,
                e,
                exc_info=True,
            )

    send_line_message(updated_appointment.client.line_user_id, msg)

    return updated_appointment
