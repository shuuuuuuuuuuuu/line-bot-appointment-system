from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime, timedelta
from typing import List, Optional
import json
from db import models, schemas
from core.logging import get_logger
from services.business_hours import (
    derive_legacy_fields,
    is_time_within_resolved_hours,
    resolve_business_hours_for_date,
)

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
        validate_appointment_business_hours(db, data.service_dateTime)
        logger.debug("搜尋 Client: %s", data.line_user_id)
        db_client = db.query(models.Client).filter(models.Client.line_user_id == data.line_user_id).first()
        if not db_client:
            db_client = models.Client(line_user_id=data.line_user_id, last_name=data.last_name, first_name=data.first_name)
            db.add(db_client)
            db.flush()

        original_price = data.total_price
        final_price = data.total_price
        coupon_code = normalize_coupon_code(data.coupon_code)
        coupon = None

        if coupon_code:
            base_price = _resolve_base_price(db, data.service_items, data.total_price)
            original_price = base_price
            coupon, final_price = _validate_coupon_for_use(
                db,
                code=coupon_code,
                line_user_id=data.line_user_id,
                category=data.category,
                base_price=base_price,
            )
            # 寫回 schema，讓後續 LINE 匯款訊息使用折扣後金額
            data.total_price = final_price

        # 建立 Appointment
        now = datetime.now()
        db_appointment = models.Appointment(
            client_id=db_client.id,
            total_price=final_price,
            paid=False,
            service_dateTime=data.service_dateTime,
            total_duration=data.total_duration,
            user_message=data.user_message,
            payment_deadline_at=now + timedelta(hours=1),
            payment_proof_received=False,
            payment_reminder_sent=False,
            owner_notified=False,
            coupon_code=coupon.code if coupon else None,
            original_price=original_price if coupon else None,
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

        if coupon:
            db.add(
                models.CouponRedemption(
                    coupon_id=coupon.id,
                    line_user_id=data.line_user_id,
                    appointment_id=db_appointment.id,
                )
            )

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


from services.coupon_service import (
    apply_discount,
    category_matches_coupon,
    normalize_coupon_code,
    parse_coupon_code,
)

DEFAULT_OFF_WEEKDAYS = [4, 5, 6]
DEFAULT_WEEKLY_OPEN_HOUR = 9
DEFAULT_WEEKLY_CLOSE_HOUR = 21


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




def _slot_pair_from_item(item):
    if item is None:
        return None
    if isinstance(item, dict):
        o, c = item.get("open_hour"), item.get("close_hour")
    elif hasattr(item, "model_dump"):
        data = item.model_dump()
        o, c = data.get("open_hour"), data.get("close_hour")
    else:
        o = getattr(item, "open_hour", None)
        c = getattr(item, "close_hour", None)
    if isinstance(o, int) and isinstance(c, int) and 0 <= o < c <= 24:
        return int(o), int(c)
    return None


def _normalize_time_slots(time_slots, open_hour: int, close_hour: int):
    slots = []
    if isinstance(time_slots, str):
        try:
            time_slots = json.loads(time_slots or "[]")
        except Exception:
            time_slots = []
    for item in time_slots or []:
        pair = _slot_pair_from_item(item)
        if pair is not None:
            o, c = pair
            slots.append({"open_hour": o, "close_hour": c})
    if not slots and open_hour is not None and close_hour is not None and open_hour < close_hour:
        slots.append({"open_hour": int(open_hour), "close_hour": int(close_hour)})
    slots.sort(key=lambda x: x["open_hour"])
    return slots


def _time_slots_to_json(time_slots, open_hour: int, close_hour: int) -> str:
    return json.dumps(_normalize_time_slots(time_slots, open_hour, close_hour))


def _bounds_from_time_slots(time_slots, default_open=9, default_close=21):
    normalized = _normalize_time_slots(time_slots, default_open, default_close)
    if not normalized:
        return default_open, default_close
    return normalized[0]["open_hour"], normalized[-1]["close_hour"]

def get_or_create_business_settings(db: Session) -> models.BusinessSetting:
    row = (
        db.query(models.BusinessSetting)
        .order_by(models.BusinessSetting.id.asc())
        .first()
    )
    if not row:
        row = models.BusinessSetting(
            open_hour=DEFAULT_WEEKLY_OPEN_HOUR,
            close_hour=DEFAULT_WEEKLY_CLOSE_HOUR,
            slot_interval_minutes=60,
            buffer_minutes=60,
            off_weekdays=json.dumps(DEFAULT_OFF_WEEKDAYS),
            max_advance_days=30,
            slot_lock_minutes=10,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    ensure_default_weekly_hours(db)
    return row


def ensure_default_weekly_hours(db: Session) -> List[models.BusinessWeeklyHours]:
    existing = (
        db.query(models.BusinessWeeklyHours)
        .order_by(models.BusinessWeeklyHours.weekday.asc())
        .all()
    )
    if existing:
        return existing

    settings = (
        db.query(models.BusinessSetting)
        .order_by(models.BusinessSetting.id.asc())
        .first()
    )
    if not settings:
        return []

    off_weekdays = parse_off_weekdays(settings.off_weekdays)
    rows = []
    for weekday in range(7):
        is_open = weekday not in off_weekdays
        row = models.BusinessWeeklyHours(
            weekday=weekday,
            is_open=is_open,
            open_hour=settings.open_hour,
            close_hour=settings.close_hour,
            time_slots=_time_slots_to_json([], settings.open_hour, settings.close_hour),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_weekly_hours(db: Session) -> List[models.BusinessWeeklyHours]:
    rows = ensure_default_weekly_hours(db)
    return sorted(rows, key=lambda row: row.weekday)


def list_date_overrides(db: Session) -> List[models.BusinessDateOverride]:
    return (
        db.query(models.BusinessDateOverride)
        .order_by(models.BusinessDateOverride.target_date.asc())
        .all()
    )


def _weekly_hours_to_out(rows: List[models.BusinessWeeklyHours]) -> List[schemas.BusinessWeeklyHoursOut]:
    return [
        schemas.BusinessWeeklyHoursOut(
            weekday=row.weekday,
            is_open=row.is_open,
            open_hour=row.open_hour,
            close_hour=row.close_hour,
            time_slots=_normalize_time_slots(row.time_slots, row.open_hour, row.close_hour),
        )
        for row in sorted(rows, key=lambda item: item.weekday)
    ]


def _date_override_to_out(row: models.BusinessDateOverride) -> schemas.BusinessDateOverrideOut:
    return schemas.BusinessDateOverrideOut(
        id=row.id,
        target_date=row.target_date.isoformat(),
        is_open=row.is_open,
        open_hour=row.open_hour,
        close_hour=row.close_hour,
        time_slots=_normalize_time_slots(row.time_slots, row.open_hour, row.close_hour) if row.is_open else [],
        note=row.note,
    )


def _holidays_from_overrides(
    overrides: List[models.BusinessDateOverride],
) -> List[schemas.BusinessHolidayOut]:
    return [
        schemas.BusinessHolidayOut(
            id=row.id,
            holiday_date=row.target_date.isoformat(),
            name=row.note,
        )
        for row in overrides
        if not row.is_open
    ]


def _sync_legacy_settings_from_weekly(db: Session, weekly_rows: List[models.BusinessWeeklyHours]):
    settings = get_or_create_business_settings(db)
    open_hour, close_hour, off_weekdays = derive_legacy_fields(weekly_rows)
    settings.open_hour = open_hour
    settings.close_hour = close_hour
    settings.off_weekdays = json.dumps(off_weekdays)
    db.commit()


def business_settings_to_out(db: Session) -> schemas.BusinessSettingsOut:
    row = get_or_create_business_settings(db)
    weekly_rows = list_weekly_hours(db)
    overrides = list_date_overrides(db)
    open_hour, close_hour, off_weekdays = derive_legacy_fields(weekly_rows)

    return schemas.BusinessSettingsOut(
        open_hour=open_hour,
        close_hour=close_hour,
        slot_interval_minutes=row.slot_interval_minutes,
        buffer_minutes=row.buffer_minutes,
        off_weekdays=off_weekdays,
        max_advance_days=row.max_advance_days,
        slot_lock_minutes=row.slot_lock_minutes,
        holidays=_holidays_from_overrides(overrides),
        weekly_hours=_weekly_hours_to_out(weekly_rows),
        date_overrides=[_date_override_to_out(item) for item in overrides],
    )


def update_business_settings(db: Session, data: schemas.BusinessSettingsUpdate):
    row = get_or_create_business_settings(db)
    payload = data.model_dump(exclude_unset=True)
    weekly_rows = list_weekly_hours(db)
    weekly_by_weekday = {item.weekday: item for item in weekly_rows}

    legacy_open = payload.pop("open_hour", None)
    legacy_close = payload.pop("close_hour", None)
    legacy_off = payload.pop("off_weekdays", None)

    if legacy_open is not None or legacy_close is not None or legacy_off is not None:
        open_hour = legacy_open if legacy_open is not None else row.open_hour
        close_hour = legacy_close if legacy_close is not None else row.close_hour
        off_weekdays = (
            legacy_off if legacy_off is not None else parse_off_weekdays(row.off_weekdays)
        )
        if open_hour >= close_hour:
            raise ValueError("開始營業時間須早於結束時間")
        if not isinstance(off_weekdays, list) or any(
            not isinstance(day, int) or day < 0 or day > 6 for day in off_weekdays
        ):
            raise ValueError("休假曜日須為 0–6（週一至週日）的整數陣列")

        for weekday in range(7):
            template = weekly_by_weekday[weekday]
            template.is_open = weekday not in off_weekdays
            template.open_hour = open_hour
            template.close_hour = close_hour
            template.time_slots = _time_slots_to_json([], open_hour, close_hour)

    for field, value in payload.items():
        setattr(row, field, value)

    db.commit()
    _sync_legacy_settings_from_weekly(db, list(weekly_by_weekday.values()))
    return business_settings_to_out(db)


def update_weekly_hours(db: Session, data: schemas.BusinessWeeklyHoursUpdate):
    weekly_rows = list_weekly_hours(db)
    weekly_by_weekday = {item.weekday: item for item in weekly_rows}

    seen = set()
    for item in data.items:
        if item.weekday in seen:
            raise ValueError("每週範本不可有重複的星期")
        seen.add(item.weekday)
        template = weekly_by_weekday.get(item.weekday)
        if template is None:
            template = models.BusinessWeeklyHours(
                weekday=item.weekday,
                time_slots=_time_slots_to_json([], item.open_hour, item.close_hour),
            )
            db.add(template)
            weekly_by_weekday[item.weekday] = template
        template.is_open = item.is_open
        slots = _normalize_time_slots(item.time_slots, item.open_hour, item.close_hour)
        first_open, last_close = _bounds_from_time_slots(slots, item.open_hour, item.close_hour)
        template.open_hour = first_open
        template.close_hour = last_close
        template.time_slots = json.dumps(slots)

    if len(seen) != 7:
        raise ValueError("每週範本須包含 7 天")

    db.commit()
    _sync_legacy_settings_from_weekly(db, list(weekly_by_weekday.values()))
    return business_settings_to_out(db)


def upsert_date_override(db: Session, data: schemas.BusinessDateOverrideCreate):
    try:
        target_date = datetime.strptime(data.target_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式須為 YYYY-MM-DD") from exc

    row = (
        db.query(models.BusinessDateOverride)
        .filter(models.BusinessDateOverride.target_date == target_date)
        .first()
    )
    if row is None:
        row = models.BusinessDateOverride(target_date=target_date)
        db.add(row)

    row.is_open = data.is_open
    if data.is_open:
        slots = _normalize_time_slots(data.time_slots, data.open_hour, data.close_hour)
        first_open, last_close = _bounds_from_time_slots(slots, data.open_hour or 9, data.close_hour or 21)
        row.open_hour = first_open
        row.close_hour = last_close
        row.time_slots = json.dumps(slots)
    else:
        row.open_hour = None
        row.close_hour = None
        row.time_slots = "[]"
    row.note = (data.note or "").strip() or None

    db.commit()
    db.refresh(row)
    return _date_override_to_out(row)


def delete_date_override(db: Session, override_id: int) -> bool:
    row = (
        db.query(models.BusinessDateOverride)
        .filter(models.BusinessDateOverride.id == override_id)
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def validate_appointment_business_hours(db: Session, service_datetime: datetime) -> None:
    settings = get_or_create_business_settings(db)
    target_date = service_datetime.date()
    resolved = resolve_business_hours_for_date(db, target_date)
    if not resolved.is_open:
        raise ValueError("所選日期非營業日")

    time_str = service_datetime.strftime("%H:%M")
    if not is_time_within_resolved_hours(
        resolved,
        time_str,
        slot_interval_minutes=settings.slot_interval_minutes,
    ):
        raise ValueError("所選時間不在營業時段內")


def list_business_holidays(db: Session):
    return [
        override
        for override in list_date_overrides(db)
        if not override.is_open
    ]


def create_business_holiday(db: Session, data: schemas.BusinessHolidayCreate):
    override = upsert_date_override(
        db,
        schemas.BusinessDateOverrideCreate(
            target_date=data.holiday_date,
            is_open=False,
            note=data.name,
        ),
    )
    return schemas.BusinessHolidayOut(
        id=override.id,
        holiday_date=override.target_date,
        name=override.note,
    )


def delete_business_holiday(db: Session, holiday_id: int) -> bool:
    return delete_date_override(db, holiday_id)


def _period_bounds(period: str):
    """Return (start, end) datetimes for stats; end is exclusive. None start = all time."""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    if period == "week":
        start = today_start - timedelta(days=today_start.weekday())
        end = start + timedelta(days=7)
        return start, end
    if period == "month":
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
        return start, end
    return None, None


def _appointment_status(appointment) -> tuple[str, str]:
    if appointment.deleted_at is not None:
        return "cancelled", "已取消"
    if appointment.paid:
        return "confirmed", "已確認"
    if appointment.expired:
        return "cancelled", "已取消"
    if appointment.payment_proof_received:
        return "awaiting_review", "待審核"
    return "pending_payment", "待匯款"


def _appointment_to_stats_row(appointment) -> schemas.AdminStatsAppointmentOut:
    client = appointment.client
    client_name = ""
    if client:
        client_name = f"{client.last_name or ''}{client.first_name or ''}".strip()
    service_names = []
    category_name = None
    for item in appointment.items or []:
        service = item.service
        if not service:
            continue
        service_names.append(service.service_name)
        if category_name is None and service.category:
            category_name = service.category.category_name
    status, status_label = _appointment_status(appointment)
    return schemas.AdminStatsAppointmentOut(
        id=appointment.id,
        client_name=client_name or "—",
        service_date_time=appointment.service_dateTime,
        total_price=appointment.total_price or 0,
        total_duration=appointment.total_duration,
        status=status,
        status_label=status_label,
        category_name=category_name,
        service_names=service_names,
        user_message=(appointment.user_message or "").strip() or None,
        payment_proof_received=bool(appointment.payment_proof_received),
        payment_deadline_at=appointment.payment_deadline_at,
        created_at=appointment.created_at,
    )


def _appointment_query_options():
    return (
        joinedload(models.Appointment.client),
        joinedload(models.Appointment.items)
        .joinedload(models.AppointmentItem.service)
        .joinedload(models.Service.category),
    )


def _appointment_bucket_dt(appointment):
    return appointment.service_dateTime or appointment.created_at


def _build_admin_trend(db: Session, period: str) -> list:
    """Build confirmed/revenue/cancelled series for charts."""
    now = datetime.now()

    if period == "week":
        start, end = _period_bounds("week")
        granularity = "day"
    elif period == "month":
        start, end = _period_bounds("month")
        granularity = "day"
    else:
        # last 12 calendar months including current
        start = datetime(now.year, now.month, 1) - timedelta(days=365)
        start = datetime(start.year, start.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
        granularity = "month"

    rows = (
        db.query(models.Appointment)
        .filter(
            (
                (models.Appointment.service_dateTime >= start)
                & (models.Appointment.service_dateTime < end)
            )
            | (
                models.Appointment.service_dateTime.is_(None)
                & (models.Appointment.created_at >= start)
                & (models.Appointment.created_at < end)
            )
        )
        .all()
    )

    buckets: dict[str, dict] = {}

    def ensure_bucket(key: str, label: str):
        if key not in buckets:
            buckets[key] = {
                "label": label,
                "date": key,
                "confirmed_count": 0,
                "revenue": 0,
                "cancelled_count": 0,
            }

    # Pre-fill empty buckets so the chart has continuous points
    cursor = start
    if granularity == "day":
        while cursor < end:
            key = cursor.date().isoformat()
            ensure_bucket(key, cursor.strftime("%m-%d"))
            cursor += timedelta(days=1)
    else:
        while cursor < end:
            key = f"{cursor.year:04d}-{cursor.month:02d}"
            ensure_bucket(key, key)
            if cursor.month == 12:
                cursor = datetime(cursor.year + 1, 1, 1)
            else:
                cursor = datetime(cursor.year, cursor.month + 1, 1)

    for appt in rows:
        dt = _appointment_bucket_dt(appt)
        if dt is None:
            continue
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.replace(tzinfo=None)
        if granularity == "day":
            key = dt.date().isoformat()
            label = dt.strftime("%m-%d")
        else:
            key = f"{dt.year:04d}-{dt.month:02d}"
            label = key
        if key not in buckets:
            continue
        ensure_bucket(key, label)

        is_cancelled = appt.deleted_at is not None or (
            appt.expired and not appt.paid
        )
        if appt.paid and appt.deleted_at is None:
            buckets[key]["confirmed_count"] += 1
            buckets[key]["revenue"] += appt.total_price or 0
        elif is_cancelled:
            buckets[key]["cancelled_count"] += 1

    return [
        schemas.AdminStatsTrendPoint(**buckets[key])
        for key in sorted(buckets.keys())
    ]


def _build_akashic_service_breakdown(db: Session, paid_appointments) -> list:
    """Count confirmed booking selections per 阿卡西 service item."""
    category = (
        db.query(models.Category)
        .filter(models.Category.category_name.contains("阿卡西"))
        .first()
    )
    if not category:
        return []

    services = (
        db.query(models.Service)
        .filter(models.Service.category_id == category.id)
        .order_by(models.Service.sort_order.asc(), models.Service.id.asc())
        .all()
    )
    if not services:
        return []

    counts = {service.id: 0 for service in services}
    name_by_id = {service.id: service.service_name for service in services}

    for appt in paid_appointments:
        for item in appt.items or []:
            service = item.service
            if not service or service.id not in counts:
                continue
            if service.category_id != category.id:
                continue
            counts[service.id] += 1

    return [
        schemas.AdminStatsServiceItemOut(
            service_name=name_by_id[service_id],
            booking_count=counts[service_id],
        )
        for service_id in sorted(
            counts.keys(),
            key=lambda sid: (-counts[sid], name_by_id[sid]),
        )
    ]


def get_admin_stats(db: Session, period: str = "month") -> schemas.AdminStatsOut:
    if period not in {"week", "month", "all"}:
        period = "month"

    start, end = _period_bounds(period)
    now = datetime.now()

    base = db.query(models.Appointment)
    if start is not None and end is not None:
        # Period metrics use service_dateTime when present, else created_at
        in_period = base.filter(
            (
                (models.Appointment.service_dateTime >= start)
                & (models.Appointment.service_dateTime < end)
            )
            | (
                models.Appointment.service_dateTime.is_(None)
                & (models.Appointment.created_at >= start)
                & (models.Appointment.created_at < end)
            )
        )
    else:
        in_period = base

    confirmed_q = in_period.filter(
        models.Appointment.paid == True,
        models.Appointment.deleted_at.is_(None),
    )
    confirmed_count = confirmed_q.count()
    revenue = (
        confirmed_q.with_entities(
            func.coalesce(func.sum(models.Appointment.total_price), 0)
        ).scalar()
        or 0
    )

    live_pending = db.query(models.Appointment).filter(
        models.Appointment.paid == False,
        models.Appointment.expired == False,
        models.Appointment.deleted_at.is_(None),
    )
    pending_payment_count = live_pending.filter(
        models.Appointment.payment_proof_received == False
    ).count()
    awaiting_review_count = live_pending.filter(
        models.Appointment.payment_proof_received == True
    ).count()

    cancelled_q = in_period.filter(
        (models.Appointment.deleted_at.isnot(None))
        | (
            (models.Appointment.expired == True)
            & (models.Appointment.paid == False)
        )
    )
    cancelled_count = cancelled_q.count()

    upcoming_q = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.paid == True,
            models.Appointment.deleted_at.is_(None),
            models.Appointment.service_dateTime >= now,
        )
        .order_by(models.Appointment.service_dateTime.asc())
    )
    upcoming_count = upcoming_q.count()

    # Category breakdown: distinct appointments per category (avoid double-counting revenue)
    paid_in_period = confirmed_q.options(*_appointment_query_options()).all()
    category_map: dict[str, dict] = {}
    for appt in paid_in_period:
        names = set()
        for item in appt.items or []:
            service = item.service
            if service and service.category and service.category.category_name:
                names.add(service.category.category_name)
        if not names:
            names.add("未分類")
        # Split revenue evenly across categories if multi-category (rare)
        share = (appt.total_price or 0) // max(len(names), 1)
        remainder = (appt.total_price or 0) - share * len(names)
        for i, name in enumerate(sorted(names)):
            bucket = category_map.setdefault(
                name, {"appointment_count": 0, "revenue": 0}
            )
            bucket["appointment_count"] += 1
            bucket["revenue"] += share + (remainder if i == 0 else 0)

    by_category = [
        schemas.AdminStatsCategoryOut(
            category_name=name,
            appointment_count=data["appointment_count"],
            revenue=data["revenue"],
        )
        for name, data in sorted(
            category_map.items(), key=lambda x: (-x[1]["revenue"], x[0])
        )
    ]
    by_akashic_service = _build_akashic_service_breakdown(db, paid_in_period)

    upcoming_appointments = [
        _appointment_to_stats_row(a)
        for a in upcoming_q.options(*_appointment_query_options()).limit(10).all()
    ]

    recent_appointments = list_admin_appointments_for_export(db, period)
    trend = _build_admin_trend(db, period)

    return schemas.AdminStatsOut(
        period=period,
        period_start=start.date().isoformat() if start else None,
        period_end=(end - timedelta(days=1)).date().isoformat() if end else None,
        confirmed_count=confirmed_count,
        revenue=int(revenue),
        pending_payment_count=pending_payment_count,
        awaiting_review_count=awaiting_review_count,
        cancelled_count=cancelled_count,
        upcoming_count=upcoming_count,
        by_category=by_category,
        by_akashic_service=by_akashic_service,
        trend=trend,
        upcoming_appointments=upcoming_appointments,
        recent_appointments=recent_appointments,
    )


def list_admin_appointments_for_export(db: Session, period: str = "month"):
    """All appointments in the selected period for Excel export."""
    if period not in {"week", "month", "all"}:
        period = "month"

    start, end = _period_bounds(period)
    query = db.query(models.Appointment).options(*_appointment_query_options())

    if start is not None and end is not None:
        query = query.filter(
            (
                (models.Appointment.service_dateTime >= start)
                & (models.Appointment.service_dateTime < end)
            )
            | (
                models.Appointment.service_dateTime.is_(None)
                & (models.Appointment.created_at >= start)
                & (models.Appointment.created_at < end)
            )
        )

    rows = query.order_by(models.Appointment.created_at.desc()).all()
    return [_appointment_to_stats_row(a) for a in rows]


# --- Coupons ---

def _parse_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 格式須為 YYYY-MM-DD") from exc


def _coupon_redemption_count(db: Session, coupon_id: int) -> int:
    return (
        db.query(func.count(models.CouponRedemption.id))
        .filter(models.CouponRedemption.coupon_id == coupon_id)
        .scalar()
        or 0
    )


def _coupon_eligibility_count(db: Session, coupon_id: int) -> int:
    return (
        db.query(func.count(models.CouponEligibility.id))
        .filter(models.CouponEligibility.coupon_id == coupon_id)
        .scalar()
        or 0
    )


def list_coupons(db: Session) -> List[models.Coupon]:
    return (
        db.query(models.Coupon)
        .options(joinedload(models.Coupon.category))
        .order_by(models.Coupon.created_at.desc(), models.Coupon.id.desc())
        .all()
    )


def get_coupon_by_id(db: Session, coupon_id: int) -> Optional[models.Coupon]:
    return (
        db.query(models.Coupon)
        .options(joinedload(models.Coupon.category))
        .filter(models.Coupon.id == coupon_id)
        .first()
    )


def get_coupon_by_code(db: Session, code: str) -> Optional[models.Coupon]:
    normalized = normalize_coupon_code(code)
    if not normalized:
        return None
    return (
        db.query(models.Coupon)
        .options(joinedload(models.Coupon.category))
        .filter(models.Coupon.code == normalized)
        .first()
    )


def coupon_to_admin_out(db: Session, coupon: models.Coupon) -> schemas.CouponAdminOut:
    return schemas.CouponAdminOut(
        id=coupon.id,
        name=coupon.name,
        code=coupon.code,
        discount_percent=coupon.discount_percent,
        service_slug=coupon.service_slug,
        category_id=coupon.category_id,
        category_name=coupon.category.category_name if coupon.category else None,
        valid_from=coupon.valid_from.isoformat(),
        valid_to=coupon.valid_to.isoformat(),
        is_active=coupon.is_active,
        max_uses=coupon.max_uses,
        redemption_count=_coupon_redemption_count(db, coupon.id),
        eligibility_count=_coupon_eligibility_count(db, coupon.id),
        created_at=coupon.created_at,
    )


def create_coupon(db: Session, data: schemas.CouponCreate) -> models.Coupon:
    code = normalize_coupon_code(data.code)
    _, service_slug, discount_percent = parse_coupon_code(code)
    valid_from = _parse_date(data.valid_from, "valid_from")
    valid_to = _parse_date(data.valid_to, "valid_to")
    if valid_to < valid_from:
        raise ValueError("有效期限結束日不可早於開始日")

    category = (
        db.query(models.Category).filter(models.Category.id == data.category_id).first()
    )
    if not category:
        raise ValueError("折扣項目不存在")

    existing = get_coupon_by_code(db, code)
    if existing:
        raise ValueError("此優惠碼已存在")

    coupon = models.Coupon(
        name=data.name.strip(),
        code=code,
        discount_percent=discount_percent,
        service_slug=service_slug,
        category_id=data.category_id,
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=data.is_active,
        max_uses=data.max_uses,
    )
    db.add(coupon)
    db.commit()
    return get_coupon_by_id(db, coupon.id)


def update_coupon(
    db: Session, coupon_id: int, data: schemas.CouponUpdate
) -> Optional[models.Coupon]:
    coupon = get_coupon_by_id(db, coupon_id)
    if not coupon:
        return None

    payload = data.model_dump(exclude_unset=True)

    if "name" in payload and payload["name"] is not None:
        coupon.name = payload["name"].strip()

    if "code" in payload and payload["code"] is not None:
        code = normalize_coupon_code(payload["code"])
        _, service_slug, discount_percent = parse_coupon_code(code)
        other = get_coupon_by_code(db, code)
        if other and other.id != coupon.id:
            raise ValueError("此優惠碼已存在")
        coupon.code = code
        coupon.service_slug = service_slug
        coupon.discount_percent = discount_percent

    if "category_id" in payload and payload["category_id"] is not None:
        category = (
            db.query(models.Category)
            .filter(models.Category.id == payload["category_id"])
            .first()
        )
        if not category:
            raise ValueError("折扣項目不存在")
        coupon.category_id = payload["category_id"]

    if "valid_from" in payload and payload["valid_from"] is not None:
        coupon.valid_from = _parse_date(payload["valid_from"], "valid_from")
    if "valid_to" in payload and payload["valid_to"] is not None:
        coupon.valid_to = _parse_date(payload["valid_to"], "valid_to")
    if coupon.valid_to < coupon.valid_from:
        raise ValueError("有效期限結束日不可早於開始日")

    if "is_active" in payload and payload["is_active"] is not None:
        coupon.is_active = payload["is_active"]
    if "max_uses" in payload and payload["max_uses"] is not None:
        coupon.max_uses = payload["max_uses"]

    db.commit()
    return get_coupon_by_id(db, coupon_id)


def delete_coupon(db: Session, coupon_id: int) -> Optional[str]:
    coupon = get_coupon_by_id(db, coupon_id)
    if not coupon:
        return None

    used = _coupon_redemption_count(db, coupon_id)
    if used > 0:
        coupon.is_active = False
        db.commit()
        return "disabled"

    db.delete(coupon)
    db.commit()
    return "deleted"


def _resolve_base_price(
    db: Session, service_items: List[str], fallback_price: int
) -> int:
    if not service_items:
        return fallback_price
    prices = []
    for name in service_items:
        service = (
            db.query(models.Service)
            .filter(models.Service.service_name == name)
            .first()
        )
        if service:
            prices.append(service.price or 0)
    if not prices:
        return fallback_price
    return max(prices)


def _validate_coupon_for_use(
    db: Session,
    *,
    code: str,
    line_user_id: str,
    category: str,
    base_price: int,
):
    """Validate coupon usability. Returns (coupon, discounted_price)."""
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise ValueError("請輸入優惠碼")

    try:
        parse_coupon_code(normalized)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    coupon = get_coupon_by_code(db, normalized)
    if not coupon:
        raise ValueError("找不到此優惠碼")

    if not coupon.is_active:
        raise ValueError("此優惠碼已停用")

    today = date.today()
    if today < coupon.valid_from or today > coupon.valid_to:
        raise ValueError("此優惠碼已過期或尚未生效")

    if not category_matches_coupon(category, coupon):
        raise ValueError("此優惠碼不適用於目前選擇的服務類別")

    eligible = (
        db.query(models.CouponEligibility)
        .filter(
            models.CouponEligibility.coupon_id == coupon.id,
            models.CouponEligibility.line_user_id == line_user_id,
        )
        .first()
    )
    if not eligible:
        raise ValueError("優惠碼無效")

    redemption_count = _coupon_redemption_count(db, coupon.id)
    if redemption_count >= coupon.max_uses:
        raise ValueError("此優惠碼已達使用上限")

    already_used = (
        db.query(models.CouponRedemption)
        .filter(
            models.CouponRedemption.coupon_id == coupon.id,
            models.CouponRedemption.line_user_id == line_user_id,
        )
        .first()
    )
    if already_used:
        raise ValueError("此帳號已使用過此優惠碼")

    discounted = apply_discount(base_price, coupon.discount_percent)
    return coupon, discounted


def validate_coupon(
    db: Session, data: schemas.CouponValidateRequest
) -> schemas.CouponValidateOut:
    coupon, discounted = _validate_coupon_for_use(
        db,
        code=data.code,
        line_user_id=data.line_user_id,
        category=data.category,
        base_price=data.base_price,
    )
    return schemas.CouponValidateOut(
        code=coupon.code,
        name=coupon.name,
        discount_percent=coupon.discount_percent,
        original_price=data.base_price,
        discounted_price=discounted,
        message="套用成功",
    )


def list_admin_clients(db: Session, q: Optional[str] = None) -> List[models.Client]:
    query = db.query(models.Client)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (models.Client.line_user_id.like(like))
            | (models.Client.last_name.like(like))
            | (models.Client.first_name.like(like))
        )
    return query.order_by(models.Client.id.desc()).limit(200).all()


def list_coupon_eligibilities(
    db: Session, coupon_id: int
) -> List[schemas.CouponEligibilityOut]:
    rows = (
        db.query(models.CouponEligibility)
        .filter(models.CouponEligibility.coupon_id == coupon_id)
        .order_by(models.CouponEligibility.created_at.desc())
        .all()
    )
    result = []
    for row in rows:
        client = (
            db.query(models.Client)
            .filter(models.Client.line_user_id == row.line_user_id)
            .first()
        )
        client_name = None
        if client:
            client_name = f"{client.last_name}{client.first_name}"
        result.append(
            schemas.CouponEligibilityOut(
                id=row.id,
                line_user_id=row.line_user_id,
                client_name=client_name,
                created_at=row.created_at,
            )
        )
    return result


def add_coupon_eligibilities(
    db: Session, coupon_id: int, line_user_ids: List[str]
) -> List[schemas.CouponEligibilityOut]:
    coupon = get_coupon_by_id(db, coupon_id)
    if not coupon:
        raise ValueError("找不到優惠碼")

    cleaned = []
    seen = set()
    for raw in line_user_ids:
        uid = (raw or "").strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        cleaned.append(uid)

    if not cleaned:
        raise ValueError("請至少選擇一位客戶")

    existing = {
        row.line_user_id
        for row in db.query(models.CouponEligibility)
        .filter(models.CouponEligibility.coupon_id == coupon_id)
        .all()
    }
    for uid in cleaned:
        if uid in existing:
            continue
        db.add(
            models.CouponEligibility(
                coupon_id=coupon_id,
                line_user_id=uid,
            )
        )
    db.commit()
    return list_coupon_eligibilities(db, coupon_id)


def remove_coupon_eligibility(
    db: Session, coupon_id: int, eligibility_id: int
) -> bool:
    row = (
        db.query(models.CouponEligibility)
        .filter(
            models.CouponEligibility.id == eligibility_id,
            models.CouponEligibility.coupon_id == coupon_id,
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
