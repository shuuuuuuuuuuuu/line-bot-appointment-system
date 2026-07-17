from io import BytesIO

import pytesseract
from PIL import Image, ImageOps

from core.logging import get_logger

logger = get_logger("ocr")

PAYMENT_SCREENSHOT_KEYWORDS = ("銀行", "帳號", "轉帳成功", "交易成功")


def extract_text_from_image(image_bytes: bytes) -> str:
    """使用本機 Tesseract OCR 讀取截圖文字。"""
    if not image_bytes:
        return ""

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            # 灰階與自動對比能提高銀行截圖中文字的辨識率。
            processed = ImageOps.autocontrast(ImageOps.grayscale(image))
            return pytesseract.image_to_string(
                processed,
                lang="chi_tra+eng",
                config="--psm 6",
            ).strip()
    except Exception as e:
        logger.error("Tesseract OCR 失敗: %s", e, exc_info=True)
        raise


def is_payment_screenshot(ocr_text: str) -> bool:
    """截圖文字需含匯款相關關鍵字才視為有效證明。"""
    if not ocr_text:
        return False
    return any(keyword in ocr_text for keyword in PAYMENT_SCREENSHOT_KEYWORDS)
