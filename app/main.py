from services.mail import fm 

from sqlalchemy.orm import Session
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from core.config import settings
from core.logging import setup_logging, get_logger
from core.request_logging import RequestLoggingMiddleware
from typing import List

import core.database
import db.schemas
from db import repository
from db.models import Base
from core.database import engine, get_db
from services.google_calendar_service import get_calendar_service, create_and_store_calendar_event
from services.available_slots import get_available_slots_logic, get_busy_slots, get_pending_slots, delete_pending_slot, try_lock_slot
from services.line_service import handler, line_bot_api, send_line_message, send_payment_instruction
from linebot.exceptions import InvalidSignatureError
from core.security import verify_token
from services.appointment_service import process_appointment_approval
from services.payment_followup_service import (
    resume_payment_followups,
    start_payment_followup,
)
from common.utils import get_full_name

setup_logging()
logger = get_logger("main")

# 自動建立資料表 (若資料庫中尚不存在)
Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    resume_payment_followups()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://4737-36-231-70-14.ngrok-free.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.error(
        "未處理的錯誤 %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/categories", response_model=List[db.schemas.Category])
def list_categories(db: Session = Depends(core.database.get_db)):
    return repository.get_categories(db)

@app.get("/services/filter", response_model=List[db.schemas.Service])
def filter_services(category_id: int, db: Session = Depends(core.database.get_db)):
    return repository.get_services_by_category_id(db, cat_id=category_id)

@app.get("/available-slots")
def read_slots(date: str, db: Session = Depends(core.database.get_db)): 
    try:
        busy_slots = []
        try:
            service_gen = get_calendar_service()
            service = next(service_gen)
            busy_slots = get_busy_slots(service, date)
        except Exception as e:
            logger.warning("Google Calendar 不可用 (%s)，使用空的 busy slots", e)

        pending_slots = get_pending_slots(date)             
        confirmed_slots = repository.get_confirmed_slots(db, date) 
        db_pending_slots = repository.get_db_pending_slots(db, date)

        available = get_available_slots_logic(
            busy_slots, 
            confirmed_slots, 
            pending_slots, 
            db_pending_slots,
            date
        )

        return {"available_slots": available}
    
    except Exception as e:
        logger.error("取得可預約時段失敗 (date=%s): %s", date, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/appointments/", response_model=db.schemas.Appointment)
def create_appointment(
    data: db.schemas.AppointmentCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(core.database.get_db)):

    try:
        appointment = repository.create_appointment(db, data)
        
        background_tasks.add_task(
            send_payment_instruction, 
            data
        )

        full_name = get_full_name(data)
        service_gen = get_calendar_service()
        calendar_service = next(service_gen)
        background_tasks.add_task(
            create_and_store_calendar_event,
            appointment.id,
            calendar_service,
            full_name,
            data.service_dateTime,
            data.category,
            data.total_duration,
        )
        background_tasks.add_task(start_payment_followup, appointment.id)
        
        return appointment
    
    except Exception as e:
        logger.error("建立預約失敗: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/slot/lock")
async def lock_slot(request: Request):
    data = await request.json()
    date_str = data.get('date')
    time_str = data.get('time')
    user_id = data.get('userId')

    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="日期與時間為必填")

    result = try_lock_slot(date_str, time_str, user_id)

    return result

@app.post("/api/slot/action")
async def slot_action(request: Request):
    data = await request.json()
    if data.get('action') == 'reject':
        delete_pending_slot(data.get('date'), data.get('time'))
        return {"success": True}
    return {"success": False}


@app.get("/approve")
def handle_approval(
    token: str, 
    action: str, 
    db: Session = Depends(core.database.get_db),
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
        service_gen = get_calendar_service()
        calendar_service = next(service_gen)
    except Exception as e:
        logger.warning("核准流程略過 Google Calendar (%s)", e)

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


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers['X-Line-Signature']
    body = await request.body()
    body_str = body.decode('utf-8')
    logger.info("LINE webhook received: %s", body_str)
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        logger.warning("LINE webhook signature 驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error("LINE webhook 處理失敗: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook handler error")
    
    return 'OK'


@app.get("/health")
def health_check():
    return {"status": "ok"}
