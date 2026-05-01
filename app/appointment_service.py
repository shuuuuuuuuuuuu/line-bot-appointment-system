from sqlalchemy.orm import Session
from fastapi import HTTPException
import crud
from available_slots import delete_pending_slot
from line_service import send_line_message

def process_appointment_approval(db: Session, appointment_id: int, action: str):
    # 獲取預約資料
    appointment = crud.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")
    
    if not hasattr(appointment, 'client') or not appointment.client:
        raise HTTPException(status_code=400, detail="此預約缺乏關聯的客戶資料")

    # 更新 db paid / expired
    updated_appointment = crud.update_appointment_status(db, appointment_id, action)
    if not updated_appointment:
        raise HTTPException(status_code=500, detail="資料庫更新失敗")

    # 釋放 Redis 鎖定
    try:
        service_dt = updated_appointment.service_dateTime
        delete_pending_slot(service_dt.strftime("%Y-%m-%d"), service_dt.strftime("%H:%M"))
    except Exception as e:
        print(f"Redis 解鎖失敗: {e}")

    # line bot message
    is_paid = (action == "success")
    msg = "預約成功！已收到您的款項。" if is_paid else "收款逾期，您的預約已取消。請重新預約。"
    send_line_message(updated_appointment.client.line_user_id, msg)

    return updated_appointment