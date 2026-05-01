from datetime import datetime, timedelta
from jose import jwt, JWTError
from config import settings

SECRET_KEY = settings.JWT_SECRET # 假設統一用這個

# email確認付款狀態
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7) # 預設 7 天過期
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 生成付款連結
def create_payment_token(appointment_id: int):
    expire = datetime.utcnow() + timedelta(minutes=10)
    # 這裡的 payload 建議也包成 dict 格式以利 verify_token 通用
    to_encode = {"appointment_id": appointment_id, "exp": expire, "scope": "payment"}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
