import os
from datetime import datetime, timedelta
from typing import Optional
import pytz
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from core.logging import get_logger

logger = get_logger("google_calendar")

TAIPEI_TZ = pytz.timezone("Asia/Taipei")
PLACEHOLDER_SUFFIX = "(placeholder)"


def get_calendar_service():

    creds = None
    token_path = 'token.json'
    
    GOOGLE_CALENDAR_SCOPES=["https://www.googleapis.com/auth/calendar"]

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, GOOGLE_CALENDAR_SCOPES)
    
    # 檢查並更新過期的 Token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                logger.info("Google OAuth token 已自動 refresh")
            except RefreshError as e:
                # invalid_grant 代表 refresh token 已被撤銷或失效
                logger.error("Google token refresh 失敗: %s", e, exc_info=True)
                raise Exception("Google Calendar Token 已過期或被撤銷，請重新授權取得 token.json")
        else:
            raise Exception("Google Calendar Token 已過期或不存在，請重新授權取得 token.json")

    service = build('calendar', 'v3', credentials=creds)
    try:
        yield service
    finally:
        pass


def _event_label(category: str = "") -> str:
    if category and "頌缽" in category:
        return "頌缽"
    if category and "靈氣" in category:
        return "靈氣"
    return "阿卡西"


def _event_summary(client_name: str, category: str = "", *, placeholder: bool = False) -> str:
    base = f"{_event_label(category)}（{client_name}）"
    return f"{base}{PLACEHOLDER_SUFFIX}" if placeholder else base


def _to_rfc3339(dt):
    if dt.tzinfo is None:
        dt = TAIPEI_TZ.localize(dt)
    return dt.isoformat()


def _parse_event_start(event) -> Optional[datetime]:
    start = (event.get("start") or {}).get("dateTime")
    if not start:
        return None
    try:
        # Google 回傳如 2026-07-28T14:00:00+08:00
        return datetime.fromisoformat(start.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _find_placeholder_event(service, client_name, start_dt, category: str = ""):
    """以整日範圍搜尋，優先精準 summary，否則用案主名 + placeholder + 開始時間比對。"""
    day_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    if category:
        target_summaries = {_event_summary(client_name, category, placeholder=True)}
    else:
        target_summaries = {
            _event_summary(client_name, "阿卡西", placeholder=True),
            _event_summary(client_name, "頌缽", placeholder=True),
            _event_summary(client_name, "靈氣", placeholder=True),
        }

    events_result = service.events().list(
        calendarId="primary",
        timeMin=_to_rfc3339(day_start),
        timeMax=_to_rfc3339(day_end),
        singleEvents=True,
        maxResults=250,
    ).execute()
    items = events_result.get("items", [])

    for event in items:
        if event.get("summary") in target_summaries:
            return event

    # 後備：summary 含案主名與 (placeholder)，且開始時間誤差 < 2 分鐘
    for event in items:
        summary = event.get("summary") or ""
        if client_name not in summary or PLACEHOLDER_SUFFIX not in summary:
            continue
        event_start = _parse_event_start(event)
        if event_start is None:
            continue
        if abs((event_start - start_dt).total_seconds()) <= 120:
            return event

    if items:
        logger.warning(
            "placeholder 搜尋有結果但未匹配 (client=%s, start=%s, category=%s, summaries=%s)",
            client_name,
            start_dt,
            category,
            [e.get("summary") for e in items],
        )
    return None


def create_calendar_event(
    service,
    client_name,
    start_dt,
    category: str = "",
    duration_minutes: int = 60,
):
    if not service:
        # 依需求：Calendar 不可用應視為失敗（不允許跳過）
        raise Exception("Google Calendar service 不可用，無法建立日曆事件")

    duration = duration_minutes if duration_minutes and duration_minutes > 0 else 60
    end_dt = start_dt + timedelta(minutes=duration)
    
    event_body = {
        'summary': _event_summary(client_name, category, placeholder=True),
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Asia/Taipei',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Asia/Taipei',
        },
        'colorId': '5',
        'status': 'confirmed',
        'transparency': 'opaque',
    }

    try:
        event_result = service.events().insert(
            calendarId='primary', 
            body=event_body
        ).execute()
        logger.info(
            "已建立 placeholder 日曆事件 (event_id=%s, summary=%s)",
            event_result.get("id"),
            event_result.get("summary"),
        )
        return event_result
    
    except Exception as e:
        logger.error("Google Calendar API 寫入錯誤: %s", e, exc_info=True)
        return None


def create_and_store_calendar_event(
    appointment_id: int,
    service,
    client_name,
    start_dt,
    category: str = "",
    duration_minutes: int = 60,
):
    """建立 placeholder 事件並把 event id 寫回預約。"""
    from core.database import SessionLocal
    from db import repository

    event_result = create_calendar_event(
        service,
        client_name,
        start_dt,
        category,
        duration_minutes,
    )
    event_id = (event_result or {}).get("id")
    if not event_id:
        logger.error("建立日曆事件後無 event id (appointment_id=%s)", appointment_id)
        return event_result

    db = SessionLocal()
    try:
        repository.set_google_event_id(db, appointment_id, event_id)
    finally:
        db.close()
    return event_result


def _get_event_by_id(service, event_id: str):
    try:
        return service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as e:
        logger.warning("依 event_id 取得日曆事件失敗 (event_id=%s): %s", event_id, e)
        return None


def confirm_calendar_event(
    service,
    client_name,
    start_dt,
    category: str = "",
    event_id: Optional[str] = None,
):
    """核准時移除 summary 的 (placeholder)，不重複建立事件。"""
    if not service:
        raise Exception("Google Calendar service 不可用，無法更新日曆事件")

    try:
        event = _get_event_by_id(service, event_id) if event_id else None
        if not event:
            event = _find_placeholder_event(service, client_name, start_dt, category)
        if not event:
            logger.warning(
                "找不到 placeholder 日曆事件 (client=%s, start=%s, category=%s, event_id=%s)",
                client_name,
                start_dt,
                category,
                event_id,
            )
            return None

        event["summary"] = _event_summary(client_name, category, placeholder=False)
        return service.events().update(
            calendarId="primary",
            eventId=event["id"],
            body=event,
        ).execute()
    except Exception as e:
        logger.error("Google Calendar API 更新錯誤: %s", e, exc_info=True)
        return None


def delete_placeholder_calendar_event(
    service,
    client_name,
    start_dt,
    category: str = "",
    event_id: Optional[str] = None,
):
    """取消預約時刪除 placeholder 日曆事件。"""
    if not service:
        raise Exception("Google Calendar service 不可用，無法刪除日曆事件")

    try:
        if event_id:
            try:
                service.events().delete(
                    calendarId="primary",
                    eventId=event_id,
                ).execute()
                logger.info("已刪除 placeholder 日曆事件 (event_id=%s)", event_id)
                return {"id": event_id}
            except Exception as e:
                logger.warning(
                    "依 event_id 刪除失敗，改搜尋 placeholder (event_id=%s): %s",
                    event_id,
                    e,
                )

        event = _find_placeholder_event(service, client_name, start_dt, category)
        if not event:
            logger.warning(
                "找不到可刪除的 placeholder 日曆事件 (client=%s, start=%s, category=%s)",
                client_name,
                start_dt,
                category,
            )
            return None

        service.events().delete(
            calendarId="primary",
            eventId=event["id"],
        ).execute()
        logger.info("已刪除 placeholder 日曆事件 (event_id=%s)", event["id"])
        return event
    except Exception as e:
        logger.error("Google Calendar API 刪除錯誤: %s", e, exc_info=True)
        return None
