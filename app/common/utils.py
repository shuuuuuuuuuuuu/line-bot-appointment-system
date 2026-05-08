from datetime import datetime

def format_appointment_time(dt):
    
    if not dt:
        return ""
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    weekday_str = weekdays[dt.weekday()]
    return dt.strftime(f"%m/%d ({weekday_str}) %H:%M")
    
def get_full_name(obj) -> str:
    
    if not obj:
        return "未知客戶"

    last = getattr(obj, "last_name", "")
    first = getattr(obj, "first_name", "")
    return f"{last}{first}"