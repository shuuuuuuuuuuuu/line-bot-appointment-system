from fastapi_mail import MessageSchema
from core.config import settings
from core.logging import get_logger
from services.mail import fm
from core.security import create_access_token

logger = get_logger("mail_tasks")

async def send_owner_notification(appointment_id: int, client_name: str):
    try:
        base_url = settings.BASE_URL

        token = create_access_token(data={"appointment_id": appointment_id})
        
        approve_url = f"{base_url}/approve?token={token}&action=success"
        reject_url = f"{base_url}/approve?token={token}&action=reject"
        html = f"""
        <h3>有新的預約需要審核</h3>
        <p>案主: {client_name}</p>
        <a href="{approve_url}" 
        style="padding:10px; background:green; color:white; text-decoration:none;">收到款項</a>
        <a href="{reject_url}" 
        style="padding:10px; background:red; color:white; text-decoration:none;">未收到款項</a>
        """
        
        message = MessageSchema(
            subject="【系統通知】有新的預約等待審核",
            recipients=["shuyen.kuo1998@gmail.com"],
            body=html,
            subtype="html"
        )
        
        await fm.send_message(message)
        
        logger.info("成功寄出預約通知信，預約單號: %s", appointment_id)
    
    except Exception as e:
        logger.error("發送郵件失敗 (ID: %s): %s", appointment_id, e, exc_info=True)
