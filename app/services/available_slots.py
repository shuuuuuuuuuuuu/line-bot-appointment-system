import redis
from datetime import datetime, timedelta
import pytz
from core.config import settings

# 設定時區
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 連接redis
r = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0, decode_responses=True)

DEFAULT_OFF_WEEKDAYS = [4, 5, 6]


# 取得該日期所有被暫時佔用的時段
def get_pending_slots(date_str):
    
    pattern = f"pending_slot:{date_str}:*"
    keys = r.keys(pattern)
    return [key.split(":")[-1] for key in keys]

# 釋放
def delete_pending_slot(date_str, time_str):
    lock_key = f"pending_slot:{date_str}:{time_str}"
    r.delete(lock_key)

def try_lock_slot(date_str: str, time_str: str, user_id: str, lock_minutes: int = 10):
    
    lock_key = f"pending_slot:{date_str}:{time_str}"
    uid = str(user_id) if user_id else "anonymous"
    ttl = max(int(lock_minutes or 10), 1) * 60
    
    # nx=True: 不存在才設定
    success = r.set(lock_key, uid, ex=ttl, nx=True)
    
    if success:
        return {"success": True, "message": "鎖定成功"}
    
    # 失敗時檢查是否為本人
    current_locker = r.get(lock_key)
    if current_locker == uid:
        r.expire(lock_key, ttl)  # 續期
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


def _format_busy_ranges(busy_slots, buffer_minutes):
    formatted_busy = []
    for busy in busy_slots:
        b_start = datetime.fromisoformat(
            busy['start'].replace('Z', '+00:00')
        ).astimezone(TAIPEI_TZ).replace(tzinfo=None)
        b_end = datetime.fromisoformat(
            busy['end'].replace('Z', '+00:00')
        ).astimezone(TAIPEI_TZ).replace(tzinfo=None) + timedelta(minutes=buffer_minutes)
        formatted_busy.append({'start': b_start, 'end': b_end})
    return formatted_busy


# 提取可提供服務時段
def get_available_slots_logic(
    busy_slots,
    confirmed_slots,
    pending_slots,
    db_pending_slots,
    target_date_str,
    *,
    open_hour=9,
    close_hour=21,
    slot_interval_minutes=60,
    buffer_minutes=60,
    off_weekdays=None,
    holiday_dates=None,
    max_advance_days=None,
):
    off_days = list(off_weekdays) if off_weekdays is not None else list(DEFAULT_OFF_WEEKDAYS)
    holidays = set(holiday_dates or [])
    interval = max(int(slot_interval_minutes or 60), 15)
    buffer = max(int(buffer_minutes or 0), 0)

    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    if target_date_str in holidays or target_dt.weekday() in off_days:
        return []

    if max_advance_days is not None:
        today = datetime.now(TAIPEI_TZ).replace(tzinfo=None).date()
        if target_dt.date() > today + timedelta(days=int(max_advance_days)):
            return []
        if target_dt.date() < today:
            return []

    available_times = []
    current_time = datetime.strptime(
        f"{target_date_str} {int(open_hour):02d}:00", "%Y-%m-%d %H:%M"
    )
    end_of_day = datetime.strptime(
        f"{target_date_str} {int(close_hour):02d}:00", "%Y-%m-%d %H:%M"
    )

    formatted_busy = _format_busy_ranges(
        list(busy_slots or []) + list(confirmed_slots or []) + list(db_pending_slots or []),
        buffer,
    )

    while current_time + timedelta(minutes=interval) <= end_of_day:
        slot_start = current_time
        slot_start_str = slot_start.strftime("%H:%M")
        slot_end = current_time + timedelta(minutes=interval)
        
        is_conflict = (
            any(slot_start < b['end'] and slot_end > b['start'] for b in formatted_busy) or
            (slot_start_str in pending_slots)
        )

        if not is_conflict:
            now_taipei = datetime.now(TAIPEI_TZ).replace(tzinfo=None)
            if slot_start > now_taipei:
                available_times.append(slot_start_str)
        
        current_time += timedelta(minutes=interval)

    return available_times
