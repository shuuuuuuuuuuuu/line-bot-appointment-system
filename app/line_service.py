from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from config import settings
from auth import create_payment_token

line_bot_api = LineBotApi(settings.CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.CHANNEL_SECRET)

# 回傳預約成功與否的訊息
def send_line_message(user_id: str, message: str):\
    line_bot_api.push_message(user_id, TextSendMessage(text=message))

# 「我要預約」被觸發 要轉跳到「預約系統」
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text.strip()
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

def send_payment_instruction(line_user_id: str, appointment_id: int):
    
    token = create_payment_token(appointment_id)
    # payment_url = f"{settings.PAYMENT_URL}/payment?token={token}"
    payment_url = "https://drive.google.com/file/d/1xfL9YduhCGqP-JWKgrF203XhHyHOUS-s/view?usp=drive_link"
    message = (
        "✅ 預約資料已送出！\n"
        "\n"
        "請於 10 分鐘內完成付款，連結將於 10 分鐘後失效：\n"
        f"{payment_url}"
        "\n"
    )
    send_line_message(line_user_id, message)