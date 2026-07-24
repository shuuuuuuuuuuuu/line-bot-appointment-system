from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
from typing import List, Optional
import json
from db import models, schemas
from core.logging import get_logger

logger = get_logger("repository")

# 查詢所有分類
def get_categories(db: Session):
    return db.query(models.Category).all()

# 查詢特定分類的服務（公開：僅啟用）
def get_services_by_category_id(db: Session, cat_id: int):
    return (
        db.query(models.Service)
        .filter(
            models.Service.category_id == cat_id,
            models.Service.is_active == True,
        )
        .order_by(models.Service.sort_order.asc(), models.Service.id.asc())
        .all()
    )


def get_service_by_id(db: Session, service_id: int):
    return (
        db.query(models.Service)
        .options(joinedload(models.Service.category))
        .filter(models.Service.id == service_id)
        .first()
    )


def list_admin_services(db: Session, category_id: Optional[int] = None):
    query = db.query(models.Service).options(joinedload(models.Service.category))
    if category_id is not None:
        query = query.filter(models.Service.category_id == category_id)
    return query.order_by(
        models.Service.category_id.asc(),
        models.Service.sort_order.asc(),
        models.Service.id.asc(),
    ).all()


def create_service(db: Session, data: schemas.ServiceCreate):
    category = db.query(models.Category).filter(models.Category.id == data.category_id).first()
    if not category:
        raise ValueError("分類不存在")

    service = models.Service(
        service_name=data.service_name.strip(),
        category_id=data.category_id,
        price=data.price,
        duration_minutes=data.duration_minutes,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return get_service_by_id(db, service.id)


def update_service(db: Session, service_id: int, data: schemas.ServiceUpdate):
    service = get_service_by_id(db, service_id)
    if not service:
        return None

    payload = data.model_dump(exclude_unset=True)
    if "service_name" in payload and payload["service_name"] is not None:
        payload["service_name"] = payload["service_name"].strip()
    if "category_id" in payload:
        category = (
            db.query(models.Category)
            .filter(models.Category.id == payload["category_id"])
            .first()
        )
        if not category:
            raise ValueError("分類不存在")

    for key, value in payload.items():
        setattr(service, key, value)

    db.commit()
    return get_service_by_id(db, service_id)


def reorder_services(db: Session, items: List[schemas.ServiceReorderItem]):
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("排序清單含重複服務")

    services = (
        db.query(models.Service)
        .filter(models.Service.id.in_(ids))
        .all()
    )
    by_id = {service.id: service for service in services}
    missing = [service_id for service_id in ids if service_id not in by_id]
    if missing:
        raise ValueError("部分服務不存在")

    for item in items:
        by_id[item.id].sort_order = item.sort_order

    db.commit()
    return list_admin_services(db)


def delete_service(db: Session, service_id: int) -> Optional[str]:
    """刪除服務。若已有預約引用則改為停用。回傳 'deleted' | 'disabled' | None。"""
    service = get_service_by_id(db, service_id)
    if not service:
        return None

    referenced = (
        db.query(models.AppointmentItem)
        .filter(models.AppointmentItem.service_id == service_id)
        .first()
    )
    if referenced:
        service.is_active = False
        db.commit()
        return "disabled"

    db.delete(service)
    db.commit()
    return "deleted"


def list_message_templates(db: Session, key: Optional[str] = None):
    query = db.query(models.MessageTemplate).options(
        joinedload(models.MessageTemplate.category)
    )
    if key:
        query = query.filter(models.MessageTemplate.key == key)
    return query.order_by(
        models.MessageTemplate.key.asc(),
        models.MessageTemplate.category_id.asc(),
        models.MessageTemplate.id.asc(),
    ).all()


def get_message_template_by_id(db: Session, template_id: int):
    return (
        db.query(models.MessageTemplate)
        .options(joinedload(models.MessageTemplate.category))
        .filter(models.MessageTemplate.id == template_id)
        .first()
    )


def get_message_template(
    db: Session,
    key: str,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
):
    """優先取指定分類範本，其次取不分分類的通用範本。"""
    query = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.key == key,
        models.MessageTemplate.is_active == True,
    )

    resolved_category_id = category_id
    if resolved_category_id is None and category_name:
        category = (
            db.query(models.Category)
            .filter(models.Category.category_name.contains(category_name))
            .first()
        )
        if not category and category_name:
            # 寬鬆比對：分類名包含關鍵字
            for keyword in ("頌缽", "靈氣", "阿卡西"):
                if keyword in category_name:
                    category = (
                        db.query(models.Category)
                        .filter(models.Category.category_name.contains(keyword))
                        .first()
                    )
                    break
        if category:
            resolved_category_id = category.id

    if resolved_category_id is not None:
        specific = query.filter(
            models.MessageTemplate.category_id == resolved_category_id
        ).first()
        if specific:
            return specific

    return query.filter(models.MessageTemplate.category_id.is_(None)).first()


def _find_template_conflict(
    db: Session,
    key: str,
    category_id: Optional[int],
    exclude_id: Optional[int] = None,
):
    query = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.key == key,
    )
    if category_id is None:
        query = query.filter(models.MessageTemplate.category_id.is_(None))
    else:
        query = query.filter(models.MessageTemplate.category_id == category_id)
    if exclude_id is not None:
        query = query.filter(models.MessageTemplate.id != exclude_id)
    return query.first()


def update_message_template(
    db: Session,
    template_id: int,
    data: schemas.MessageTemplateUpdate,
):
    template = get_message_template_by_id(db, template_id)
    if not template:
        return None

    payload = data.model_dump(exclude_unset=True)
    next_category_id = (
        payload["category_id"] if "category_id" in payload else template.category_id
    )

    if "category_id" in payload and payload["category_id"] is not None:
        category = (
            db.query(models.Category)
            .filter(models.Category.id == payload["category_id"])
            .first()
        )
        if not category:
            raise ValueError("分類不存在")

    if "category_id" in payload and _find_template_conflict(
        db, template.key, next_category_id, exclude_id=template_id
    ):
        raise ValueError("相同觸發時機與分類的範本已存在")

    for field, value in payload.items():
        if field == "name" and isinstance(value, str):
            value = value.strip()
        if field == "description" and isinstance(value, str):
            value = value.strip() or None
        setattr(template, field, value)

    db.commit()
    return get_message_template_by_id(db, template_id)


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


DEFAULT_OFF_WEEKDAYS = [4, 5, 6]


def parse_off_weekdays(raw) -> list[int]:
    if raw is None:
        return list(DEFAULT_OFF_WEEKDAYS)
    if isinstance(raw, list):
        return [int(x) for x in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [int(x) for x in parsed if 0 <= int(x) <= 6]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return list(DEFAULT_OFF_WEEKDAYS)


def get_or_create_business_settings(db: Session) -> models.BusinessSetting:
    row = (
        db.query(models.BusinessSetting)
        .order_by(models.BusinessSetting.id.asc())
        .first()
    )
    if row:
        return row
    row = models.BusinessSetting(
        open_hour=9,
        close_hour=21,
        slot_interval_minutes=60,
        buffer_minutes=60,
        off_weekdays=json.dumps(DEFAULT_OFF_WEEKDAYS),
        max_advance_days=30,
        slot_lock_minutes=10,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_business_holidays(db: Session):
    return (
        db.query(models.BusinessHoliday)
        .order_by(models.BusinessHoliday.holiday_date.asc())
        .all()
    )


def business_settings_to_out(db: Session) -> schemas.BusinessSettingsOut:
    row = get_or_create_business_settings(db)
    holidays = list_business_holidays(db)
    return schemas.BusinessSettingsOut(
        open_hour=row.open_hour,
        close_hour=row.close_hour,
        slot_interval_minutes=row.slot_interval_minutes,
        buffer_minutes=row.buffer_minutes,
        off_weekdays=parse_off_weekdays(row.off_weekdays),
        max_advance_days=row.max_advance_days,
        slot_lock_minutes=row.slot_lock_minutes,
        holidays=[
            schemas.BusinessHolidayOut(
                id=h.id,
                holiday_date=h.holiday_date.isoformat(),
                name=h.name,
            )
            for h in holidays
        ],
    )


def update_business_settings(db: Session, data: schemas.BusinessSettingsUpdate):
    row = get_or_create_business_settings(db)
    payload = data.model_dump(exclude_unset=True)

    if "off_weekdays" in payload and payload["off_weekdays"] is not None:
        days = payload["off_weekdays"]
        if not isinstance(days, list) or any(
            not isinstance(d, int) or d < 0 or d > 6 for d in days
        ):
            raise ValueError("休假曜日須為 0–6（週一至週日）的整數陣列")
        payload["off_weekdays"] = json.dumps(sorted(set(days)))

    open_hour = payload.get("open_hour", row.open_hour)
    close_hour = payload.get("close_hour", row.close_hour)
    if open_hour >= close_hour:
        raise ValueError("開始營業時間須早於結束時間")

    for field, value in payload.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    return business_settings_to_out(db)


def create_business_holiday(db: Session, data: schemas.BusinessHolidayCreate):
    try:
        holiday_date = datetime.strptime(data.holiday_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式須為 YYYY-MM-DD") from exc

    existing = (
        db.query(models.BusinessHoliday)
        .filter(models.BusinessHoliday.holiday_date == holiday_date)
        .first()
    )
    if existing:
        raise ValueError("此日期已設為休假日")

    row = models.BusinessHoliday(
        holiday_date=holiday_date,
        name=(data.name or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas.BusinessHolidayOut(
        id=row.id,
        holiday_date=row.holiday_date.isoformat(),
        name=row.name,
    )


def delete_business_holiday(db: Session, holiday_id: int) -> bool:
    row = (
        db.query(models.BusinessHoliday)
        .filter(models.BusinessHoliday.id == holiday_id)
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
