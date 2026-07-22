from fastapi import APIRouter, HTTPException, Request
from linebot.exceptions import InvalidSignatureError

from core.logging import get_logger
from services.line_service import handler

router = APIRouter(tags=["webhooks"])
logger = get_logger("api.webhooks")


@router.post("/callback")
async def callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = await request.body()
    body_str = body.decode("utf-8")
    logger.info("LINE webhook received: %s", body_str)

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError as exc:
        logger.warning("LINE webhook signature 驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature") from exc
    except Exception as exc:
        logger.error("LINE webhook 處理失敗: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook handler error") from exc

    return "OK"
