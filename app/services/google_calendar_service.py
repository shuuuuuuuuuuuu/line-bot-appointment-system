import os
from datetime import timedelta
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


def _find_placeholder_event(service, client_name, start_dt, category: str = ""):
    # 預留較長搜尋窗，涵蓋靈氣等 90 分鐘服務
    end_dt = start_dt + timedelta(hours=3)
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
        timeMin=_to_rfc3339(start_dt),
        timeMax=_to_rfc3339(end_dt),
        singleEvents=True,
    ).execute()

    for event in events_result.get("items", []):
        if event.get("summary") in target_summaries:
            return event
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
        
        return event_result
    
    except Exception as e:
        logger.error("Google Calendar API 寫入錯誤: %s", e, exc_info=True)
        return None


def confirm_calendar_event(service, client_name, start_dt, category: str = ""):
    """核准時移除 summary 的 (placeholder)，不重複建立事件。"""
    if not service:
        raise Exception("Google Calendar service 不可用，無法更新日曆事件")

    try:
        event = _find_placeholder_event(service, client_name, start_dt, category)
        if not event:
            logger.warning(
                "找不到 placeholder 日曆事件 (client=%s, start=%s, category=%s)",
                client_name,
                start_dt,
                category,
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


def delete_placeholder_calendar_event(service, client_name, start_dt, category: str = ""):
    """取消預約時刪除 placeholder 日曆事件。"""
    if not service:
        raise Exception("Google Calendar service 不可用，無法刪除日曆事件")

    try:
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
        return event
    except Exception as e:
        logger.error("Google Calendar API 刪除錯誤: %s", e, exc_info=True)
        return None
