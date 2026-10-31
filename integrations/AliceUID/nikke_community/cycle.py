"""Community periods begin at 08:00 Asia/Shanghai (UTC midnight)."""
from datetime import datetime, timedelta, timezone
BJT = timezone(timedelta(hours=8))
RESET_HOUR = 8

def cycle_day(timestamp):
    local = datetime.fromtimestamp(timestamp, BJT)
    return (local - timedelta(hours=RESET_HOUR)).date().isoformat()

def cycle_label(day):
    start = datetime.fromisoformat(day)
    end = start + timedelta(days=1)
    return f'{day} 08:00 ～ {end.date().isoformat()} 08:00（北京时间）'
