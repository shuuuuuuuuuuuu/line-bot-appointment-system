"""add message_templates table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-24 14:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAYMENT_INSTRUCTION = """嗨～ {first_name}，您的預約資料已送出
感謝您的預約！

🔆日期時間：{time_display}
🔆預約類別：{category}
🔆預約項目：{service_text}
{message_row}
💫 提醒您：
請於 1 小時內完成匯款並回覆帳號後五碼，才算預約成功呦 ☑️
逾期將自動取消預約。

匯款資訊：
🔆 銀行：國泰 013
🔆 帳號：013560086819
🔆 費用：${fee}"""

APPROVAL_SUCCESS_AKASHIC = """預約成功！已收到您的款項
我們 {time_display} 線上見😊

🪐幾個注意事項：

1. 閱讀前 24 小時不要飲酒、實用安眠藥或娛樂性藥物。解讀時要保持清醒以達到最佳療癒效果。

2. 解讀過程輕鬆像聊天，也可能在過程中延伸其他問題進行療癒。只需要敞開內心接受宇宙最直接的指引😇

3. 我們會用 Line 語音通話方式進行，請確保閱讀過程在安靜、不受干擾且有良好網路收訊的環境。

4. 可以錄音或做筆記：閱讀過程中會有許多訊息與指引，建議可以透過錄音或筆記記錄下來，之後也能反覆回顧與整理。

希望這場對話可以讓懿敏感受到靈魂深處的智慧與啟發，還有來自宇宙無條件的愛與支持💫🤍"""

APPROVAL_SUCCESS_SINGING = """收到款項了～我們 {time_display} 見😊

地點在露西森林七樓（台北車站 M2 出口）。

🪐幾個注意事項：

1. 當天不需要提早抵達，準時到就好～

2. 閱讀前 24 小時盡量不要飲酒、使用安眠藥或娛樂性藥物，才能達到最佳療癒效果。

3. 準備好水壺，療癒前後都需要補充很多水。

4. 帶著放鬆與信任的心前來：當天的目的就是讓自己好好放鬆享受波音的療癒與音頻震動的按摩，所以只需要帶著一顆放鬆與信任的心前來就好呦。

希望這場頌缽療癒可以讓{first_name}好好放鬆，獲得身心靈的洗滌與療癒。😇✨"""

APPROVAL_SUCCESS_REIKI = """收到款項了～我們 {time_display} 遠端見😊

療癒前的準備：

💛 舒適衣著，建議換上寬鬆、無束縛的居家服，讓身體能完全放鬆。
💛 可以提早 5-10 分鐘，將手機調至靜音或飛航模式，給自己一段完全不受打擾的時光。
💛 平常心，不需要刻意努力去感覺，只需要帶著一顆開放的心、把自己當作一顆準備充電的電池就好。
💛 水分補充，靈氣療癒前後都可以喝一點溫開水，幫助能量流動與代謝。

【溫馨提醒】靈氣屬於輔助性方式，非醫療行為，不涉及診斷與療效。若有身體不適或病理症狀，請務必以正規醫療與醫師的醫囑為主。

流程說明

💛 療癒前：靈療師會撥打 Line Audio 說明流程與介紹靈氣

💛 療癒中：結束通話，開始療癒。請被療癒者採舒服靜坐姿勢或躺著放鬆也可以，過程約 60 分鐘。

💛 療癒後：靈療會再次撥打 Line Audio，屆時彼此分享療癒結果與感受。

線上見😊"""


def upgrade() -> None:
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.UniqueConstraint("key", "category_id", name="uq_message_template_key_category"),
    )
    op.create_index("ix_message_templates_key", "message_templates", ["key"])

    conn = op.get_bind()
    categories = {
        row[1]: row[0]
        for row in conn.execute(
            sa.text("SELECT id, category_name FROM categories")
        ).fetchall()
    }

    def cat_id(*keywords):
        for name, cid in categories.items():
            if any(k in name for k in keywords):
                return cid
        return None

    seeds = [
        (
            "payment_instruction",
            "預約送出／匯款說明",
            None,
            PAYMENT_INSTRUCTION,
            "可用變數：{first_name} {time_display} {category} {service_text} {message_row} {fee}",
        ),
        (
            "payment_reminder",
            "匯款提醒",
            None,
            "匯款後請務必提供匯款資訊，才算預約成功呦！",
            "無變數",
        ),
        (
            "payment_expired",
            "匯款逾期取消",
            None,
            "收款逾期，您的預約已取消。請重新預約。",
            "無變數",
        ),
        (
            "approval_reject",
            "審核拒絕／取消",
            None,
            "您的預約已取消。請重新預約。",
            "無變數",
        ),
        (
            "approval_success",
            "審核通過（阿卡西）",
            cat_id("阿卡西"),
            APPROVAL_SUCCESS_AKASHIC,
            "可用變數：{time_display} {first_name} {full_name}",
        ),
        (
            "approval_success",
            "審核通過（頌缽）",
            cat_id("頌缽"),
            APPROVAL_SUCCESS_SINGING,
            "可用變數：{time_display} {first_name} {full_name}",
        ),
        (
            "approval_success",
            "審核通過（靈氣）",
            cat_id("靈氣"),
            APPROVAL_SUCCESS_REIKI,
            "可用變數：{time_display} {first_name} {full_name}",
        ),
    ]

    for key, name, category_id, body, description in seeds:
        conn.execute(
            sa.text(
                "INSERT INTO message_templates "
                "(`key`, name, category_id, body, description, is_active) "
                "VALUES (:key, :name, :category_id, :body, :description, 1)"
            ),
            {
                "key": key,
                "name": name,
                "category_id": category_id,
                "body": body,
                "description": description,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_message_templates_key", table_name="message_templates")
    op.drop_table("message_templates")
