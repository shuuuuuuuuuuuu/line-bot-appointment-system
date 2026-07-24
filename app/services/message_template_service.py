"""Resolve and render LINE message templates."""

from string import Formatter
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.logging import get_logger
from db import models, repository

logger = get_logger("message_template")

# 找不到 DB 範本時的後備文案
FALLBACKS = {
    "payment_reminder": "匯款後請務必提供匯款資訊，才算預約成功呦！",
    "payment_expired": "收款逾期，您的預約已取消。請重新預約。",
    "approval_reject": "您的預約已取消。請重新預約。",
}


def render_template(body: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """以 str.format_map 渲染；缺少的變數保留原佔位符。"""
    variables = variables or {}

    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    # 只替換 body 中實際出現的欄位，避免多餘 KeyError
    used = {
        field_name
        for _, field_name, _, _ in Formatter().parse(body)
        if field_name
    }
    data = _Safe({key: variables.get(key, "{" + key + "}") for key in used})
    for key in used:
        if key in variables:
            data[key] = variables[key]
    try:
        return body.format_map(data)
    except Exception as exc:
        logger.error("訊息範本渲染失敗: %s", exc, exc_info=True)
        return body


def get_rendered_message(
    db: Session,
    key: str,
    *,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    fallback: Optional[str] = None,
) -> str:
    template = repository.get_message_template(
        db,
        key=key,
        category_id=category_id,
        category_name=category_name,
    )
    if template and template.body:
        return render_template(template.body, variables)

    text = fallback or FALLBACKS.get(key)
    if text:
        return render_template(text, variables)

    logger.warning("找不到訊息範本 key=%s category_id=%s", key, category_id)
    return fallback or ""
