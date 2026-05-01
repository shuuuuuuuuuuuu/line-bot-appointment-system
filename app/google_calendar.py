import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import settings  

def get_calendar_service():

    creds = None
    token_path = 'token.json'
    
    # list
    scopes = [settings.GOOGLE_CALENDAR_SCOPES]

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    
    # 檢查並更新過期的 Token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        else:
            raise Exception("Google Calendar Token 已失效，請重新在本機執行 auth_test.py 取得 token.json")

    service = build('calendar', 'v3', credentials=creds)
    try:
        yield service
    finally:
        pass