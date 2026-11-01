"""Display/diagnostic times only. Never use formatted values for scheduling or TTLs."""
from __future__ import annotations

from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo('Asia/Shanghai')
DISPLAY_VERSION = '1.1.15-beijing'
# Regional civil time for diagnostics, NOT a game reset/season timezone.
# Japan is the reviewed baseline. Do not guess the other servers' timezones.
REGION_TIMEZONES = {81: 'Asia/Tokyo'}


def beijing_text(epoch, *, seconds=True, label=True):
    """Format the same instant in Beijing; never parse a local wall-clock string."""
    fmt = '%Y-%m-%d %H:%M:%S' if seconds else '%Y-%m-%d %H:%M'
    text = datetime.fromtimestamp(epoch, BEIJING).strftime(fmt)
    return text + '（北京时间）' if label else text


def time_metadata(epoch, area_id=None):
    """Additive JSON metadata; the original numeric timestamp stays authoritative."""
    if type(epoch) not in (int, float) or not math.isfinite(epoch):
        return {}
    try:
        instant = datetime.fromtimestamp(epoch, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return {}
    try:
        area = int(area_id) if area_id is not None else None
    except (TypeError, ValueError, OverflowError):
        area = None
    zone = REGION_TIMEZONES.get(area)
    return dict(epoch=epoch, utc=instant.isoformat(),
                beijing=instant.astimezone(BEIJING).isoformat(), area_id=area,
                region_timezone=zone,
                region_time=instant.astimezone(ZoneInfo(zone)).isoformat() if zone else None)
