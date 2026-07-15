from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from core.config import settings
from core.logging import get_logger
import db.schemas
from common.utils import format_appointment_time

logger = get_logger("line_service")

line_bot_api = LineBotApi(settings.CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.CHANNEL_SECRET)


def send_line_message(user_id: str, message: str):
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
    except Exception as e:
        logger.error("LINE 推播失敗 (user_id=%s): %s", user_id, e, exc_info=True)
        raise

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text.strip()

    if BOOKING_KEYWORD in text:
        reply_msg = "請點選選單中的「預約服務」開始預約。"
    else:
        reply_msg = f"您好！請輸入「{BOOKING_KEYWORD}」開始預約流程。"

    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_msg)
        )
    except Exception as e:
        logger.error("LINE 回覆訊息失敗: %s", e, exc_info=True)
        raise

def send_payment_instruction(data: db.schemas.AppointmentCreate):
    
    service_text = "、".join(data.service_items)
    
    time_display = format_appointment_time(data.service_dateTime)
    
    message_row = ""
    if data.user_message and data.user_message.strip():
        message_row = f"🔆簡述問題：{data.user_message}\n"

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
        "🔆 費用：$2,222\n"
    )
    send_line_message(data.line_user_id, message)
