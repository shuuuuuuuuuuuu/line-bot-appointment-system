import pytest

from services.line_service import extract_last_five_digits
from services.ocr_service import is_payment_screenshot


@pytest.mark.parametrize(
    "text,expected",
    [
        ("12345", "12345"),
        (" 67890 ", "67890"),
        ("後五碼12345", "12345"),
        ("帳號後五碼：98765", "98765"),
        ("五碼 11111", "11111"),
        ("預約", None),
        ("1234", None),
        ("123456", None),
        ("hello", None),
    ],
)
def test_extract_last_five_digits(text, expected):
    assert extract_last_five_digits(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("國泰銀行 轉帳明細", True),
        ("匯款帳號 013560086819", True),
        ("轉帳成功 金額 2222", True),
        ("交易成功", True),
        ("今天天氣很好", False),
        ("", False),
    ],
)
def test_is_payment_screenshot(text, expected):
    assert is_payment_screenshot(text) is expected
