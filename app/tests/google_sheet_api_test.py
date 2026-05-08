import argparse
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.database import SessionLocal
from db.models import Category, Service


SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_RANGE = "Service_Config!A2:B"

def get_categories():
    db = SessionLocal()
    try:
        return db.query(category_name).all()
    finally:
        db.close()

def get_categories_and_services():
    db = SessionLocal()
    try:
        return db.query(Service.service_name, Category.category_name).join(Category, Service.category_id == Category.id, isouter=True).all()
    finally:
        db.close()


def get_oauth_credentials(credentials_path: str, token_path: str):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SHEETS_SCOPE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SHEETS_SCOPE)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


def build_sheets_service(credentials_path: str, token_path: str):
    creds = get_oauth_credentials(credentials_path, token_path)
    return build("sheets", "v4", credentials=creds)


def sync_categories(spreadsheet_id: str, target_range: str, credentials_path: str, token_path: str):
    
    values = [[row.category_name, row.service_name] for row in get_categories_and_services()]
    service = build_sheets_service(credentials_path, token_path)

    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=target_range,
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=target_range,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    print(f"Synced {len(values)} categories to {target_range}")

# 參數設定
def parse_args():
    parser = argparse.ArgumentParser(description="Sync DB categories to Google Sheets")
    parser.add_argument(
        "--spreadsheet-id",
        default=os.getenv("GOOGLE_SHEET_ID"),
        help="Google Spreadsheet ID",
    )
    parser.add_argument(
        "--range",
        default=os.getenv("GOOGLE_SHEET_RANGE", DEFAULT_RANGE),
        help=f"Target range, default: {DEFAULT_RANGE}",
    )
    parser.add_argument(
        "--credentials",
        default=os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "credentials.json"),
        help="OAuth client credentials JSON path",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GOOGLE_SHEETS_TOKEN_FILE", "token_sheets.json"),
        help="Path to store OAuth token for sheets",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.spreadsheet_id:
        raise ValueError("Missing spreadsheet id")
    if not os.path.exists(args.credentials):
        raise FileNotFoundError(
            f"Credentials file not found: {args.credentials}. "
            "Use --credentials or set GOOGLE_SERVICE_ACCOUNT_FILE."
        )

    sync_categories(args.spreadsheet_id, args.range, args.credentials, args.token)
