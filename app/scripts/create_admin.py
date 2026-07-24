"""建立或重設管理員帳號。

用法（在 web 容器或 app 目錄）：
  ADMIN_EMAIL=owner@example.com ADMIN_PASSWORD='your-password' python -m scripts.create_admin

若帳號已存在，會更新密碼並啟用帳號。
"""

import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from core.admin_auth import hash_password
from core.database import SessionLocal
from db import models


def main() -> int:
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or ""

    if not email or not password:
        print("請設定環境變數 ADMIN_EMAIL 與 ADMIN_PASSWORD")
        return 1
    if len(password) < 8:
        print("ADMIN_PASSWORD 至少需要 8 個字元")
        return 1

    db = SessionLocal()
    try:
        existing = (
            db.query(models.Admin)
            .filter(models.Admin.email == email)
            .first()
        )
        password_hash = hash_password(password)
        if existing:
            existing.password_hash = password_hash
            existing.is_active = True
            db.commit()
            print(f"已更新管理員密碼 id={existing.id} email={existing.email}")
            return 0

        admin = models.Admin(
            email=email,
            password_hash=password_hash,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"已建立管理員 id={admin.id} email={admin.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
