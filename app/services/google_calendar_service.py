import os
from datetime import timedelta
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from core.logging import get_logger

logger = get_logger("google_calendar")

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

def create_calendar_event(service, client_name, start_dt):
    if not service:
        # 依需求：Calendar 不可用應視為失敗（不允許跳過）
        raise Exception("Google Calendar service 不可用，無法建立日曆事件")

    # 預設時長為 1 小時
    end_dt = start_dt + timedelta(hours=1)
    
    event_body = {
        'summary': f'阿卡西（{client_name}）',
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
