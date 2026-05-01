import builtins
import pydantic

# 強制將 SecretStr 注入全域環境
if not hasattr(builtins, 'SecretStr'):
    try:
        from pydantic import SecretStr
    except ImportError:
        from pydantic.types import SecretStr
    builtins.SecretStr = SecretStr

from fastapi_mail import FastMail, ConnectionConfig
from config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=587,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)

fm = FastMail(conf)