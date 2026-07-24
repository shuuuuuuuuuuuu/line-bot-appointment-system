from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import admin, public, webhooks
from core.database import engine
from core.logging import setup_logging, get_logger
from core.request_logging import RequestLoggingMiddleware
from db.models import Base
from services.payment_followup_service import resume_payment_followups

setup_logging()
logger = get_logger("main")

# 自動建立資料表 (若資料庫中尚不存在)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Line Bot Appointment API")


@app.on_event("startup")
async def on_startup():
    resume_payment_followups()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(public.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "service": "Line Bot Appointment API",
        "docs": "/docs",
        "admin_ui": "http://localhost:5174",
        "admin_login_api": "POST /api/admin/login",
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.error(
        "未處理的錯誤 %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
