# Line Bot 預約系統 (Line Bot Appointment System)

這是一個為線上或實體服務打造的自動化預約管理系統。後端採用 FastAPI 建立高併發與高效能的 RESTful API，並與 Line Messaging API 深度整合，讓用戶能直接透過 Line Bot 進行服務預約。同時整合了 Google Calendar API 實現日曆同步，自動排程與防呆避免時段重疊，全面優化預約與數據管理流程。

---

## 系統核心架構與技術棧

| 類別 | 技術 |
|------|------|
| **Backend** | FastAPI (Python)、Alembic（資料庫遷移管理） |
| **Frontend** | Vue 3（Vite、Single Page Application） |
| **Database & Cache** | MySQL（資料儲存）、Redis（高併發時段與快取管理） |
| **Third-party Integration** | Line Messaging API、Google Calendar API、Gmail SMTP |
| **Deployment & DevOps** | Docker、Docker Compose |

---

## 專案目錄結構

```
line-bot-appointment-system/
├── app/                        # 後端 FastAPI 核心程式碼
│   ├── alembic/                # 資料庫遷移歷史紀錄
│   ├── common/                 # 共用工具與常數 (utils.py)
│   ├── core/                   # 核心配置、資料庫連線、安全性與請求日誌系統
│   ├── db/                     # 資料庫 Models、Repositories 與 Schemas
│   ├── services/               # 核心業務邏輯（預約管理、空閒時段計算、Line / Google 日曆 / 郵件整合）
│   └── tests/                  # 單元測試與 API 測試（Pytest）
├── frontend/                   # 前端 Vue 3 專案目錄
│   ├── src/                    # 前端原始碼 (App.vue, components, assets)
│   └── public/                 # 靜態資源 (SVG 圖標、Favicon)
├── docker-compose.yml          # 多容器架構部署設定
├── pytest.ini                  # 測試框架設定
└── requirements-dev.txt        # 開發環境依賴套件
```

---

## 主要核心功能

### 1. 智慧預約與空閒時段計算

- 自動串接後端 MySQL 預約資料與 Google Calendar 實體日曆，即時比對並計算出當前真正可用的預約時段。
- 導入 Redis 處理高併發排隊與時段鎖定機制，有效避免多位用戶在同一秒內重複搶佔相同預約時段的併發衝突。

### 2. 雙向 API 自動化整合

- **Line Messaging API**：用戶能透過 Rich Menu 進行預約服務，系統會自動推送預約成功／付款通知。
- **Google Calendar API**：當業主核准預約後，後端會自動在對應的 Google 日曆上建立活動排程，保持行程同步。
- **Email 通知**：新預約建立後，系統會寄送審核信給業主，透過連結確認收款狀態。

### 3. 請求日誌與監控

- 建立 API 請求日誌中介軟體，於生產環境中嚴密紀錄每次請求的 Method、Path、Status Code 以及執行時間。
- **隱私安全去識別化**：日誌系統會自動將敏感的用戶上下文進行脫敏與遮罩處理，確保除錯效率與資安防護。

---

## 環境架構與快速啟動

### 前置需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Line Developers Console 帳號（Channel Secret、Access Token、LIFF ID）
- Google Cloud 專案（Calendar API 憑證）
- Gmail 應用程式密碼（SMTP 寄信）

### 1. 環境變數設定

複製專案根目錄下的 `.env .example` 並命名為 `.env`，填入對應的 Key：

```env
# Database
DB_NAME=line_bot_db
DB_USER=root
DB_ROOT_PASSWORD=your_mysql_root_password
DB_HOST=db

# Line Bot
CHANNEL_SECRET=your_channel_secret_here
CHANNEL_ACCESS_TOKEN=your_channel_access_token_here

# Google Calendar
GOOGLE_APPLICATION_CREDENTIALS=app/credentials.json

# Email (Gmail SMTP)
MAIL_USERNAME=your_gmail_account@gmail.com
MAIL_PASSWORD=your_app_specific_password
MAIL_FROM=your_gmail_account@gmail.com
MAIL_SERVER=smtp.gmail.com

# Security
JWT_SECRET=your_random_jwt_secret_here

# Frontend & Integration
BASE_URL=https://your-domain.com
VITE_LIFF_ID=your_liff_id_here
VITE_API_URL=https://your-domain.com

# Infrastructure
REDIS_HOST=redis
```


### 2. Google Calendar 授權

首次使用需在本機取得 OAuth token：

```bash
cd app
python tests/auth_test.py
```

完成後會產生 `app/token.json`，供 Google Calendar API 使用。

### 3. 使用 Docker Compose 一鍵啟動

專案已完整容器化，可使用 Docker 一鍵拉起後端 API、前端網頁及資料庫環境：

```bash
docker compose up -d --build
```

啟動後可透過以下連接埠存取：

| 服務 | 網址 |
|------|------|
| 前端（Vue / LIFF 預約頁） | http://localhost:5173 |
| 後端 API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| MySQL | localhost:3307 |
| Redis | localhost:6379 |

### 4. 執行單元測試

專案內含測試套件，確保核心預約邏輯與 API 穩定度：

```bash
# 建議在 Docker 容器內執行
docker compose exec web pip install pytest httpx fakeredis pytest-asyncio
docker compose exec web pytest
```

---

## 預約流程概覽

```
用戶 (LINE LIFF)
  → 選擇服務類別 / 項目 / 日期 / 時段
  → Redis 鎖定時段（10 分鐘）
  → 提交預約 → MySQL 寫入
  → LINE 推送付款資訊給用戶
  → Email 通知業主審核
  → 業主點擊核准連結
  → 更新 DB 狀態 + LINE 通知用戶 + Google Calendar 建立事件
```

---

## 開發與除錯

### 查看 API 請求日誌

```bash
docker compose logs -f web | grep "line_bot.access"
```

### 查詢特定用戶操作紀錄

```bash
docker compose logs web | grep "line_user_id=Uxxxx"
```
