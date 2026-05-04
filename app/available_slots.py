import redis
from datetime import datetime, timedelta
import pytz
from config import settings

# 設定時區
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 連接redis
r = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0, decode_responses=True)

# 取得該日期所有被暫時佔用的時段
def get_pending_slots(date_str):
    
    pattern = f"pending_slot:{date_str}:*"
    keys = r.keys(pattern)
    return [key.split(":")[-1] for key in keys]

# 釋放
def delete_pending_slot(date_str, time_str):
    lock_key = f"pending_slot:{date_str}:{time_str}"
    r.delete(lock_key)

def try_lock_slot(date_str: str, time_str: str, user_id: str):
    
    lock_key = f"pending_slot:{date_str}:{time_str}"
    uid = str(user_id) if user_id else "anonymous"
    
    # nx=True: 不存在才設定, ex=600: 10分鐘過期
    success = r.set(lock_key, uid, ex=600, nx=True)
    
    if success:
        return {"success": True, "message": "鎖定成功"}
    
    # 失敗時檢查是否為本人
    current_locker = r.get(lock_key)
    if current_locker == uid:
        r.expire(lock_key, 600)  # 續期
        return {"success": True, "message": "續期成功"}
    
    return {"success": False, "message": "該時段已被佔用"}
    
# 取得google calendar busy status
def get_busy_slots(service, date_str):
    
    # 台灣時區 +8
    time_min = f"{date_str}T00:00:00+08:00"
    time_max = f"{date_str}T23:59:59+08:00"

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": "primary"}]
    }

    freebusy_result = service.freebusy().query(body=body).execute()
    busy_slots = freebusy_result['calendars']['primary']['busy']
    
    return busy_slots 

# 提取可提供服務時段
def get_available_slots_logic(busy_slots, confirmed_slots, pending_slots, db_pending_slots, target_date_str):
    
    # 定義營業範圍 -> 未來後台系統input
    OPEN_HOUR = 9
    CLOSE_HOUR = 21
    DURATION_MINUTES = 60
    BUFFER = 60
    OFF_DAYS = [4, 5, 6] # 不提供服務 (五、六、日)
    
    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    if target_dt.weekday() in OFF_DAYS:
        return [] 

    available_times = []
    # 可選時段 (每小時一個)
    current_time = datetime.strptime(f"{target_date_str} {OPEN_HOUR:02d}:00", "%Y-%m-%d %H:%M")
    end_of_day = datetime.strptime(f"{target_date_str} {CLOSE_HOUR:02d}:00", "%Y-%m-%d %H:%M")

    # busy_slots time format
    formatted_busy = []
    for busy in busy_slots:
        # Google 回傳的是 ISO 格式，例如 2026-05-16T12:00:00Z
        b_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00')).astimezone(TAIPEI_TZ).replace(tzinfo=None)
        # 還有加 buffer time
        b_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00')).astimezone(TAIPEI_TZ).replace(tzinfo=None)+ timedelta(minutes=BUFFER)

        formatted_busy.append({'start': b_start, 'end': b_end})

    # 逐一檢查時段是否衝突
    while current_time + timedelta(minutes=DURATION_MINUTES) <= end_of_day:
        slot_start = current_time
        slot_start_str = slot_start.strftime("%H:%M")
        slot_end = current_time + timedelta(minutes=DURATION_MINUTES)
        
        # 檢查衝突 google calendar, redis, db
        is_conflict = (
            any(slot_start < b['end'] and slot_end > b['start'] for b in formatted_busy) or
            (slot_start_str in pending_slots) or
            (slot_start_str in confirmed_slots) or
            (slot_start_str in db_pending_slots)
        )

        if not is_conflict:
            # 檢查今天的時間是否已過去
            now_taipei = datetime.now(TAIPEI_TZ).replace(tzinfo=None)
            if slot_start > now_taipei:
                available_times.append(slot_start_str)
        
        # 移動到下一個時段 (這裡設定 1 小時跳一次)
        current_time += timedelta(minutes=DURATION_MINUTES)

    return available_times
