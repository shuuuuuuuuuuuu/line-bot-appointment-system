from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.logging import get_logger
from db import models

logger = get_logger("admin_auth")

ADMIN_TOKEN_TYPE = "admin"
ADMIN_TOKEN_EXPIRE_HOURS = 12
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def create_admin_access_token(
    admin_id: int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)
    )
    payload = {
        "sub": str(admin_id),
        "type": ADMIN_TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def verify_admin_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        logger.warning("管理員 JWT 驗證失敗")
        return None

    if payload.get("type") != ADMIN_TOKEN_TYPE:
        logger.warning("非管理員 token 嘗試存取管理 API")
        return None
    if not payload.get("sub"):
        return None
    return payload


def authenticate_admin(
    db: Session,
    email: str,
    password: str,
) -> Optional[models.Admin]:
    admin = (
        db.query(models.Admin)
        .filter(models.Admin.email == email.lower().strip())
        .first()
    )
    if not admin or not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Admin:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_admin_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        admin_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin = db.query(models.Admin).filter(models.Admin.id == admin_id).first()
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin
