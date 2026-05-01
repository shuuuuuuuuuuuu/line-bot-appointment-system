import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    
    # db
    DB_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_ROOT_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}?charset=utf8mb4"
    
    # gmail
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM")
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    
    # LINE Bot
    CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
    CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

    # 預約系統
    BASE_URL = os.getenv("BASE_URL")

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET")
    ALGORITHM = "HS256"

    # google calendar
    GOOGLE_CALENDAR_SCOPES = os.getenv("GOOGLE_CALENDAR_SCOPES", "https://www.googleapis.com/auth/calendar")

    # payment url
    PAYMENT_URL = os.getenv("PAYMENT_URL")

    # redis
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")

settings = Settings()