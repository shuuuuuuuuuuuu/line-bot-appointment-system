import asyncio
import re
from typing import Optional

from linebot import LineBotApi, WebhookHandler
from linebot.models import ImageMessage, MessageEvent, TextMessage, TextSendMessage
from core.config import settings
from core.database import SessionLocal
from core.logging import get_logger
import db.schemas
from db import repository
from common.utils import format_appointment_time, get_full_name
from services.mail_tasks import send_owner_notification
from services.ocr_service import extract_text_from_image, is_payment_screenshot

logger = get_logger("line_service")

line_bot_api = LineBotApi(settings.CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.CHANNEL_SECRET)

LAST_FIVE_WITH_KEYWORD = re.compile(r"(?:後五碼|五碼)[：:\s]*(\d{5})")
SCREENSHOT_LAST_FIVE = "截圖"


def send_line_message(user_id: str, message: str):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
    except Exception as e:
        logger.error("LINE 推播失敗 (user_id=%s): %s", user_id, e, exc_info=True)
        raise


def extract_last_five_digits(text: str) -> Optional[str]:
    stripped = text.strip()
    if re.fullmatch(r"\d{5}", stripped):
        return stripped
    match = LAST_FIVE_WITH_KEYWORD.search(stripped)
    if match:
        return match.group(1)
    return None


def _guess_image_meta(image_bytes: bytes):
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "payment_screenshot.png", "image/png"
    if image_bytes.startswith(b"\xff\xd8"):
        return "payment_screenshot.jpg", "image/jpeg"
    return "payment_screenshot.jpg", "image/jpeg"


def _download_line_image(message_id: str) -> bytes:
    """LINE webhook 只給 message id，需呼叫 Content API 取得圖檔後才能當附件寄出。"""
    message_content = line_bot_api.get_message_content(message_id)
    return b"".join(message_content.iter_content())


def _schedule_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        loop.create_task(coro)


def _reply(event, reply_msg: str):
    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_msg),
        )
    except Exception as e:
        logger.error("LINE 回覆訊息失敗: %s", e, exc_info=True)
        raise


def _notify_owner_payment_proof(
    event,
    last_five_digits: str,
    image_bytes: Optional[bytes] = None,
):
    line_user_id = event.source.user_id
    db = SessionLocal()
    try:
        appointment = repository.get_latest_pending_appointment_by_line_user_id(
            db, line_user_id
        )
        if not appointment:
            _reply(event, "找不到待確認的預約，請先完成預約表單或聯絡客服。")
            return

        full_name = get_full_name(appointment.client)
        kwargs = {
            "appointment_id": appointment.id,
            "client_name": full_name,
            "last_five_digits": last_five_digits,
        }
        if image_bytes:
            filename, content_type = _guess_image_meta(image_bytes)
            kwargs["image_bytes"] = image_bytes
            kwargs["image_filename"] = filename
            kwargs["image_content_type"] = content_type

        repository.mark_payment_proof_received(db, appointment.id)
        _schedule_async(send_owner_notification(**kwargs))
        _reply(event, "已收到您的匯款資訊，我們會盡快確認，謝謝！")
        logger.info(
            "已排程寄送 owner 通知 (appointment_id=%s, last_five=%s, has_image=%s)",
            appointment.id,
            last_five_digits,
            bool(image_bytes),
        )
    except Exception as e:
        logger.error(
            "處理匯款資訊失敗 (user_id=%s): %s",
            line_user_id,
            e,
            exc_info=True,
        )
        raise
    finally:
        db.close()


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text.strip()

    last_five = extract_last_five_digits(text)
    if last_five:
        _notify_owner_payment_proof(event, last_five)


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    try:
        image_bytes = _download_line_image(event.message.id)
        ocr_text = extract_text_from_image(image_bytes)
    except Exception as e:
        logger.error("下載或 OCR 截圖失敗: %s", e, exc_info=True)
        return

    if not is_payment_screenshot(ocr_text):
        logger.info("截圖未含匯款關鍵字，略過通知")
        return

    _notify_owner_payment_proof(
        event,
        SCREENSHOT_LAST_FIVE,
        image_bytes=image_bytes,
    )


def send_payment_instruction(data: db.schemas.AppointmentCreate):
    
    service_text = "、".join(data.service_items)
    
    time_display = format_appointment_time(data.service_dateTime)
    
    message_row = ""
    if data.user_message and data.user_message.strip():
        message_row = f"🔆簡述問題：{data.user_message}\n"

    fee = data.total_price
    if not fee:
        fee = 3333 if "頌缽" in (data.category or "") else 2222

    message = (
        f"嗨～ {data.first_name}，您的預約資料已送出\n"
        "感謝您的預約！\n"
        "\n"
        f"🔆日期時間：{time_display}\n"
        f"🔆預約類別：{data.category}\n"
        f"🔆預約項目：{service_text}\n"
        f"{message_row}"
        "\n"
        "💫 提醒您：\n"
        "請於 1 小時內完成匯款並回覆帳號後五碼，才算預約成功呦 ☑️\n"
        "逾期將自動取消預約。\n"
        "\n"
        "匯款資訊：\n"
        "🔆 銀行：國泰 013\n"
        "🔆 帳號：013560086819\n"
        f"🔆 費用：${fee:,}\n"
    )
    send_line_message(data.line_user_id, message)
