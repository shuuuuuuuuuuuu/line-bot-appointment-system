import logging
from core.config import settings 
from fastapi_mail import MessageSchema
from services.mail import fm
from core.security import create_access_token

logger = logging.getLogger("uvicorn")

async def send_owner_notification(appointment_id: int, client_name: str):
    try:
        base_url = settings.BASE_URL

        token = create_access_token(data={"appointment_id": appointment_id})
        
        approve_url = f"{base_url}/approve?token={token}&action=success"
        reject_url = f"{base_url}/approve?&token={token}&action=reject"
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
            recipients=["shuyen.kuo1998@gmail.com"], # 業主信箱
            body=html,
            subtype="html"
        )
        
        await fm.send_message(message)
        
        logger.info(f"成功寄出預約通知信，預約單號: {appointment_id}")
    
    except Exception as e:
        logger.error(f"發送郵件失敗 (ID: {appointment_id}): {e}")