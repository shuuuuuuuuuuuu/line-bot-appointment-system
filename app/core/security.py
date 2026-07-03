from datetime import datetime, timedelta
from jose import jwt, JWTError
from core.config import settings
from core.logging import get_logger

logger = get_logger("security")

SECRET_KEY = settings.JWT_SECRET

# email確認付款狀態
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        logger.warning("JWT 驗證失敗")
        return None
