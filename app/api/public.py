from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import db.schemas
from common.utils import get_full_name
from core.database import get_db
from core.logging import get_logger
from core.security import verify_token
from db import repository
from services.business_hours import resolve_business_hours_for_date_str
from services import google_calendar_service
from services.appointment_service import process_appointment_approval
from services.available_slots import (
    delete_pending_slot,
    get_available_slots_logic,
    get_busy_slots,
    get_pending_slots,
    try_lock_slot,
)
from services.line_service import send_payment_instruction
from services.payment_followup_service import start_payment_followup

router = APIRouter(tags=["booking"])
logger = get_logger("api.public")


@router.get("/categories", response_model=List[db.schemas.Category])
def list_categories(db: Session = Depends(get_db)):
    return repository.get_categories(db)


@router.get("/business-settings", response_model=db.schemas.BusinessSettingsOut)
def get_business_settings(db: Session = Depends(get_db)):
    return repository.business_settings_to_out(db)


@router.get("/services/filter", response_model=List[db.schemas.Service])
def filter_services(category_id: int, db: Session = Depends(get_db)):
    return repository.get_services_by_category_id(db, cat_id=category_id)


@router.get("/available-slots")
def read_slots(date: str, db: Session = Depends(get_db)):
    try:
        busy_slots = []
        try:
            service_gen = google_calendar_service.get_calendar_service()
            service = next(service_gen)
            busy_slots = get_busy_slots(service, date)
        except Exception as exc:
            logger.warning(
                "Google Calendar 不可用 (%s)，使用空的 busy slots",
                exc,
            )

        pending_slots = get_pending_slots(date)
        confirmed_slots = repository.get_confirmed_slots(db, date)
        db_pending_slots = repository.get_db_pending_slots(db, date)
        biz = repository.business_settings_to_out(db)
        resolved = resolve_business_hours_for_date_str(db, date)

        available = get_available_slots_logic(
            busy_slots,
            confirmed_slots,
            pending_slots,
            db_pending_slots,
            date,
            is_open=resolved.is_open,
            open_hour=resolved.open_hour or biz.open_hour,
            close_hour=resolved.close_hour or biz.close_hour,
            time_slots=[{"open_hour": slot.open_hour, "close_hour": slot.close_hour} for slot in (resolved.time_slots or [])],
            slot_interval_minutes=biz.slot_interval_minutes,
            buffer_minutes=biz.buffer_minutes,
            max_advance_days=biz.max_advance_days,
        )
        return {"available_slots": available}
    except Exception as exc:
        logger.error(
            "取得可預約時段失敗 (date=%s): %s",
            date,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/appointments/", response_model=db.schemas.Appointment)
def create_appointment(
    data: db.schemas.AppointmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        appointment = repository.create_appointment(db, data)

        background_tasks.add_task(send_payment_instruction, data)

        full_name = get_full_name(data)
        service_gen = google_calendar_service.get_calendar_service()
        calendar_service = next(service_gen)
        background_tasks.add_task(
            google_calendar_service.create_and_store_calendar_event,
            appointment.id,
            calendar_service,
            full_name,
            data.service_dateTime,
            data.category,
            data.total_duration,
        )
        background_tasks.add_task(start_payment_followup, appointment.id)

        return appointment
    except Exception as exc:
        logger.error("建立預約失敗: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/coupons/validate", response_model=db.schemas.CouponValidateOut)
def validate_coupon(
    data: db.schemas.CouponValidateRequest,
    db: Session = Depends(get_db),
):
    try:
        return repository.validate_coupon(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/slot/lock")
async def lock_slot(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    date_str = data.get("date")
    time_str = data.get("time")
    user_id = data.get("userId")

    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="日期與時間為必填")

    biz = repository.get_or_create_business_settings(db)
    return try_lock_slot(
        date_str,
        time_str,
        user_id,
        lock_minutes=biz.slot_lock_minutes,
    )


@router.post("/api/slot/action")
async def slot_action(request: Request):
    data = await request.json()
    if data.get("action") == "reject":
        delete_pending_slot(data.get("date"), data.get("time"))
        return {"success": True}
    return {"success": False}


@router.get("/approve")
def handle_approval(
    token: str,
    action: str,
    db: Session = Depends(get_db),
):
    if action not in {"success", "reject"}:
        raise HTTPException(status_code=422, detail="無效的審核動作")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="無效或過期的連結")

    appointment_id = payload.get("appointment_id")
    if not appointment_id:
        raise HTTPException(status_code=422, detail="缺少預約 ID")

    calendar_service = None
    try:
        service_gen = google_calendar_service.get_calendar_service()
        calendar_service = next(service_gen)
    except Exception as exc:
        logger.warning("核准流程略過 Google Calendar (%s)", exc)

    process_appointment_approval(db, appointment_id, action, calendar_service)

    return HTMLResponse(
        content="""
        <!doctype html>
        <html lang="zh-Hant">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>預約審核完成</title>
          </head>
          <body style="font-family: sans-serif; text-align: center; padding: 40px;">
            <h2>此預約已完成審核</h2>
          </body>
        </html>
        """,
        status_code=200,
    )


@router.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}
