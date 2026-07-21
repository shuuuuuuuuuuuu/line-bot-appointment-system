from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
from db import models, schemas
from core.logging import get_logger

logger = get_logger("repository")

# 查詢所有分類
def get_categories(db: Session):
    return db.query(models.Category).all()

# 查詢特定分類的服務
def get_services_by_category_id(db: Session, cat_id: int):
    return db.query(models.Service).filter(models.Service.category_id == cat_id).all()

# 建立預約資料
def create_appointment(db: Session, data: schemas.AppointmentCreate):
    try:
        logger.info("開始建立預約")
        logger.debug("搜尋 Client: %s", data.line_user_id)
        db_client = db.query(models.Client).filter(models.Client.line_user_id == data.line_user_id).first()
        if not db_client:
            db_client = models.Client(line_user_id=data.line_user_id, last_name=data.last_name, first_name=data.first_name)
            db.add(db_client)
            db.flush() 
        
        # 建立 Appointment
        now = datetime.now()
        db_appointment = models.Appointment(
            client_id=db_client.id,
            total_price=data.total_price,  
            paid=False,       
            service_dateTime=data.service_dateTime, 
            total_duration=data.total_duration,
            user_message=data.user_message,
            payment_deadline_at=now + timedelta(hours=1),
            payment_proof_received=False,
            payment_reminder_sent=False,
            owner_notified=False,
        )
        db.add(db_appointment)
        db.flush() 

        for s_name in data.service_items:
            service = db.query(models.Service).filter(models.Service.service_name == s_name).first()
            if service:
                db_item = models.AppointmentItem(
                    appointment_id=db_appointment.id,
                    service_id=service.id
                )
                db.add(db_item)
            else:
                logger.warning("找不到服務名稱: %s", s_name)

        logger.info("預約建立完成，準備 Commit")
        db.commit()
        db.refresh(db_appointment)
        return db_appointment

    except Exception as e:
        logger.error("建立預約失敗: %s", e, exc_info=True)
        db.rollback()
        raise e

# 更新付款狀態
def update_appointment_status(db: Session, appointment_id: int, action: str):
    """原子化處理審核；回傳 (appointment, 是否為首次處理)。"""
    if action not in {"success", "reject"}:
        return None, False

    values = {
        models.Appointment.paid: action == "success",
        models.Appointment.expired: action == "reject",
    }

    try:
        updated_count = (
            db.query(models.Appointment)
            .filter(
                models.Appointment.id == appointment_id,
                models.Appointment.paid == False,
                models.Appointment.expired == False,
                models.Appointment.deleted_at.is_(None),
            )
            .update(values, synchronize_session=False)
        )
        db.commit()
        return get_appointment(db, appointment_id), updated_count == 1
    except Exception as e:
        db.rollback()
        logger.error("更新預約狀態失敗 (ID: %s): %s", appointment_id, e, exc_info=True)
        return None, False


# 查詢特定id預約（排除刪除）
def get_appointment(db: Session, appointment_id: int):
    return (
        db.query(models.Appointment)
        .options(
            joinedload(models.Appointment.client),
            joinedload(models.Appointment.items)
            .joinedload(models.AppointmentItem.service)
            .joinedload(models.Service.category),
        )
        .filter(
            models.Appointment.id == appointment_id,
            models.Appointment.deleted_at.is_(None),
        )
        .first()
    )


def get_appointment_category_name(appointment) -> str:
    for item in getattr(appointment, "items", None) or []:
        service = getattr(item, "service", None)
        category = getattr(service, "category", None) if service else None
        if category and category.category_name:
            return category.category_name
    return ""


def get_latest_pending_appointment_by_line_user_id(db: Session, line_user_id: str):
    """取得該 LINE 使用者最新一筆尚未付款、尚未過期的預約。"""
    now = datetime.now()
    return (
        db.query(models.Appointment)
        .options(joinedload(models.Appointment.client))
        .join(models.Client)
        .filter(
            models.Client.line_user_id == line_user_id,
            models.Appointment.paid == False,
            models.Appointment.expired == False,
            models.Appointment.deleted_at.is_(None),
            (
                (models.Appointment.payment_deadline_at.is_(None))
                | (models.Appointment.payment_deadline_at >= now)
            ),
        )
        .order_by(models.Appointment.created_at.desc())
        .first()
    )


def mark_payment_proof_received(db: Session, appointment_id: int):
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        return None
    appointment.payment_proof_received = True
    appointment.owner_notified = True
    try:
        db.commit()
        db.refresh(appointment)
        return appointment
    except Exception as e:
        db.rollback()
        logger.error("標記匯款資訊失敗 (ID: %s): %s", appointment_id, e, exc_info=True)
        return None


def soft_delete_appointment(db: Session, appointment_id: int) -> bool:
    """刪除預約：標記 deleted_at，並設為逾期。"""
    appointment = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.id == appointment_id,
            models.Appointment.deleted_at.is_(None),
        )
        .first()
    )
    if not appointment:
        return False
    try:
        appointment.deleted_at = datetime.now()
        appointment.expired = True
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error("刪除預約失敗 (ID: %s): %s", appointment_id, e, exc_info=True)
        return False


def set_google_event_id(db: Session, appointment_id: int, event_id: str):
    appointment = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.id == appointment_id,
            models.Appointment.deleted_at.is_(None),
        )
        .first()
    )
    if not appointment:
        return None
    try:
        appointment.google_event_id = event_id
        db.commit()
        db.refresh(appointment)
        return appointment
    except Exception as e:
        db.rollback()
        logger.error(
            "寫入 google_event_id 失敗 (ID: %s): %s",
            appointment_id,
            e,
            exc_info=True,
        )
        return None


def get_appointments_needing_payment_followup(db: Session):
    """尚未收到匯款資訊、尚未結束匯款追蹤的待付款預約。"""
    return (
        db.query(models.Appointment)
        .options(joinedload(models.Appointment.client))
        .filter(
            models.Appointment.paid == False,
            models.Appointment.expired == False,
            models.Appointment.deleted_at.is_(None),
            models.Appointment.payment_proof_received == False,
            models.Appointment.payment_deadline_at.isnot(None),
        )
        .all()
    )


# 查詢已確認預約的忙碌區間（含服務時長；buffer 由 available_slots 統一加）
def get_confirmed_slots(db: Session, date_str: str):
    
    start_dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    appointments = db.query(models.Appointment).filter(
        models.Appointment.service_dateTime >= start_dt,
        models.Appointment.service_dateTime <= end_dt,
        models.Appointment.paid == True,
        models.Appointment.deleted_at.is_(None),
    ).all()

    return [_appointment_to_busy_range(app) for app in appointments]


# 新增：獲取資料庫中「尚未過期且尚未付款」的忙碌區間
def get_db_pending_slots(db: Session, date_str: str):
    now = datetime.now()
    day_start = datetime.strptime(date_str, "%Y-%m-%d")
    day_end = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    # 找出匯款期限尚未到期、未付款、未標記過期的預約
    pending = db.query(models.Appointment).filter(
        models.Appointment.service_dateTime >= day_start,
        models.Appointment.service_dateTime <= day_end,
        models.Appointment.paid == False,
        models.Appointment.expired == False,
        models.Appointment.deleted_at.is_(None),
        models.Appointment.payment_deadline_at.isnot(None),
        models.Appointment.payment_deadline_at >= now,
    ).all()
    
    return [_appointment_to_busy_range(app) for app in pending]


def _appointment_to_busy_range(appointment) -> dict:
    start = appointment.service_dateTime
    duration = appointment.total_duration or 60
    end = start + timedelta(minutes=duration)
    return {
        "start": f"{start.isoformat()}+08:00",
        "end": f"{end.isoformat()}+08:00",
    }
