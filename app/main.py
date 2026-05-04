from mail import fm 

from sqlalchemy.orm import Session
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from typing import List

import database
import schemas
import crud
from models import Base
from database import engine
from google_calendar import get_calendar_service
from available_slots import get_available_slots_logic, get_busy_slots, get_pending_slots, delete_pending_slot, try_lock_slot
from mail_tasks import send_owner_notification
from line_service import handler, line_bot_api, send_line_message, send_payment_instruction
from linebot.exceptions import InvalidSignatureError
from auth import verify_token
from appointment_service import process_appointment_approval


# 自動建立資料表 (若資料庫中尚不存在)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 允許 Vue 開發環境的來源
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://7672-218-172-15-197.ngrok-free.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

@app.get("/available-slots")
def read_slots(date: str, db: Session = Depends(database.get_db), service = Depends(get_calendar_service)): 
    try:

        busy_slots = get_busy_slots(service, date)           
        pending_slots = get_pending_slots(date)             
        confirmed_slots = crud.get_confirmed_slots(db, date) 
        db_pending_slots = crud.get_db_pending_slots(db, date)

        available = get_available_slots_logic(
            busy_slots, 
            confirmed_slots, 
            pending_slots, 
            db_pending_slots,
            date
        )

        return {"available_slots": available}
    
    except Exception as e:
        print(f"ERROR in read_slots: {e}") 
        raise HTTPException(status_code=500, detail=str(e))


# 讀取services table
@app.get("/services", response_model=List[schemas.Service])
def read_services(db: Session = Depends(database.get_db)):
    return crud.get_services(db)


# 建立預約資料
@app.post("/appointments/", response_model=schemas.Appointment)
def create_appointment(
    data: schemas.AppointmentCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)):

    try:
        appointment = crud.create_appointment(db, data)
        
        # 發送付款連結給預約者
        background_tasks.add_task(
            send_payment_instruction, 
            data.line_user_id,
            appointment.id
        )

        # email通知業主有新預約
        background_tasks.add_task(send_owner_notification, appointment.id, data.name)
        
        return appointment
    
    except Exception as e:
        print(f"DEBUG ERROR: {e}") 
        raise HTTPException(status_code=400, detail=str(e))

# 鎖定點擊時段
@app.post("/api/slot/lock")
async def lock_slot(request: Request):
    data = await request.json()
    date_str = data.get('date')
    time_str = data.get('time')
    user_id = data.get('userId') # 來自 LIFF

    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="日期與時間為必填")

    result = try_lock_slot(date_str, time_str, user_id)

    return result

# 更換日期的釋放
@app.post("/api/slot/action")
async def slot_action(request: Request):
    data = await request.json()
    if data.get('action') == 'reject':
        delete_pending_slot(data.get('date'), data.get('time'))
        return {"success": True}
    return {"success": False}


# 業主email觸發line-bot訊息
@app.get("/approve")
def handle_approval(
    token: str, 
    action: str, 
    db: Session = Depends(database.get_db), 
    calendar_service = Depends(get_calendar_service)
):
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="無效或過期的連結")

    appointment_id = payload.get("appointment_id")
    if not appointment_id:
        raise HTTPException(status_code=422, detail="缺少預約 ID")

    # 2. 呼叫 Service 處理剩餘邏輯
    process_appointment_approval(db, appointment_id, action, calendar_service)
    
    return {"message": "Success"}


# LINE Webhook 路由
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers['X-Line-Signature']
    body = await request.body()
    body_str = body.decode('utf-8')
    
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return 'OK'


@app.get("/health")
def health_check():
    return {"status": "ok"}
