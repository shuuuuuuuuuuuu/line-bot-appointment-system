from sqlalchemy.orm import Session
from fastapi import HTTPException
from db import repository
from services.available_slots import delete_pending_slot
from services.line_service import send_line_message
from services.google_calendar_service import create_calendar_event
from common.utils import format_appointment_time, get_full_name
from core.logging import get_logger

logger = get_logger("appointment_service")

def process_appointment_approval(db: Session, appointment_id: int, action: str, calendar_service):
    appointment = repository.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")
    
    if not hasattr(appointment, 'client') or not appointment.client:
        raise HTTPException(status_code=400, detail="此預約缺乏關聯的客戶資料")

    updated_appointment = repository.update_appointment_status(db, appointment_id, action)
    if not updated_appointment:
        raise HTTPException(status_code=500, detail="資料庫更新失敗")

    try:
        service_dt = updated_appointment.service_dateTime
        delete_pending_slot(service_dt.strftime("%Y-%m-%d"), service_dt.strftime("%H:%M"))
    except Exception as e:
        logger.warning("Redis 解鎖失敗 (appointment_id=%s): %s", appointment_id, e)

    full_name = get_full_name(updated_appointment.client)
    time_display = format_appointment_time(updated_appointment.service_dateTime)
    
    is_paid = (action == "success")
    if is_paid:
        msg = f"""預約成功！已收到您的款項           
我們 {time_display} 線上見😊

🪐幾個注意事項：

1. 閱讀前 24 小時不要飲酒、實用安眠藥或娛樂性藥物。解讀時要保持清醒以達到最佳療癒效果。

2. 解讀過程輕鬆像聊天，也可能在過程中延伸其他問題進行療癒。只需要敞開內心接受宇宙最直接的指引😇

3. 我們會用 Line 語音通話方式進行，請確保閱讀過程在安靜、不受干擾且有良好網路收訊的環境。

4. 可以錄音或做筆記：閱讀過程中會有許多訊息與指引，建議可以透過錄音或筆記記錄下來，之後也能反覆回顧與整理。

希望這場對話可以讓懿敏感受到靈魂深處的智慧與啟發，還有來自宇宙無條件的愛與支持💫🤍"""
        try:
            create_calendar_event(
                service=calendar_service,
                client_name=full_name,
                start_dt=updated_appointment.service_dateTime
            )
        except Exception as e:
            logger.error("Google Calendar 同步失敗 (appointment_id=%s): %s", appointment_id, e, exc_info=True)
    else:
        msg = "收款逾期，您的預約已取消。請重新預約。"

    send_line_message(updated_appointment.client.line_user_id, msg)

    return updated_appointment
