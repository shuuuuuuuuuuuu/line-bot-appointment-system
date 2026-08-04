"""Coupon code parsing and category matching helpers."""

from __future__ import annotations

import re
from typing import Optional, Tuple

# code 格式：YYYYMMDD_項目_折扣趴數，例 20260802_soundhealing_50
COUPON_CODE_PATTERN = re.compile(
    r"^(\d{8})_([a-zA-Z0-9]+)_(100|[1-9]\d?)$"
)


def parse_coupon_code(code: str) -> Tuple[str, str, int]:
    """Parse code into (date_prefix, service_slug, discount_percent).

    discount_percent 為應付比例（50 → 應付原價 50%）。
    """
    normalized = (code or "").strip()
    match = COUPON_CODE_PATTERN.match(normalized)
    if not match:
        raise ValueError(
            "優惠碼格式錯誤，應為「年月日_項目_折扣趴數」，例如 20260802_soundhealing_50"
        )
    date_prefix, slug, percent_str = match.groups()
    percent = int(percent_str)
    if percent < 1 or percent > 100:
        raise ValueError("折扣趴數須介於 1–100")
    return date_prefix, slug.lower(), percent


def category_matches_coupon(category_name: str, coupon) -> bool:
    """Booking category must match the coupon's selected category."""
    expected = ""
    if getattr(coupon, "category", None) is not None:
        expected = coupon.category.category_name or ""
    if not expected:
        return False
    booking = (category_name or "").strip()
    if not booking:
        return False
    # Exact or contains either way（類別名可能是「頌缽」或「頌缽療癒」）
    return expected == booking or expected in booking or booking in expected


def apply_discount(base_price: int, discount_percent: int) -> int:
    """Compute payable amount: base_price * discount_percent / 100 (rounded)."""
    if base_price < 0:
        raise ValueError("價格不可為負")
    if discount_percent < 1 or discount_percent > 100:
        raise ValueError("折扣趴數須介於 1–100")
    return int(round(base_price * discount_percent / 100))


def normalize_coupon_code(code: Optional[str]) -> str:
    return (code or "").strip()
