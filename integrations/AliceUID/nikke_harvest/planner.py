"""Pure Beijing-time planning and text, independent of Core and renderers."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import re

TZ = timezone(timedelta(hours=8))
DEFAULT_QUIET = '00:00-08:00'


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def account_key(bind):
    return digest(str(bind.bot_id), str(bind.user_id), str(bind.game_id), str(bind.intl_open_id), int(bind.area_id))


def revision(bind):
    return digest(str(bind.game_id), str(bind.intl_open_id), int(bind.area_id), bind.cookie_enc)


def route_from_event(ev):
    group = str(getattr(ev, 'group_id', '') or '')
    kind = 'group' if group else 'direct'
    route = dict(user=str(ev.user_id), bot=str(ev.bot_id), self_id=str(getattr(ev, 'bot_self_id', '') or ''),
                 ws=str(getattr(ev, 'WS_BOT_ID', '') or ''), kind=kind, target=group or str(ev.user_id))
    if not all(route.values()):
        raise ValueError('当前会话缺少可靠机器人路由，暂不能开启收菜提醒。')
    route['pm'] = getattr(ev, 'user_pm', 6)
    route['id'] = digest(route['bot'], route['self_id'], route['user'], kind, route['target'])
    return route


def quiet_value(value):
    if value == '关闭':
        return ''
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}-\d{2}:\d{2}', value, flags=re.ASCII):
        raise ValueError('格式：00:00-08:00，或“关闭”；全部按北京时间。')
    start, end = value.split('-')
    for part in (start, end):
        h, m = map(int, part.split(':'))
        if h > 23 or m > 59:
            raise ValueError('时间须在00:00～23:59之间。')
    if start == end:
        raise ValueError('起止时间不能相同；如需取消免打扰，请输入“关闭”。')
    return value


def minutes(text):
    h, m = map(int, text.split(':'))
    return h * 60 + m


def quiet(now, value):
    if not value:
        return False
    dt = datetime.fromtimestamp(now, TZ)
    minute = dt.hour * 60 + dt.minute
    start, end = map(minutes, value.split('-'))
    return start <= minute < end if start < end else minute >= start or minute < end


def at_next(now, minute):
    dt = datetime.fromtimestamp(now, TZ)
    result = dt.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
    if result.timestamp() <= now:
        result += timedelta(days=1)
    return result.timestamp()


def night_next(now):
    return at_next(now, 23 * 60)


def pre_next(now, value):
    return at_next(now, (minutes(value.split('-')[0]) - 60) % 1440) if value else None


def bedtime(now, full_at, value):
    if not value or quiet(now, value):
        return False
    start, end = map(minutes, value.split('-'))
    begin = at_next(now, start)
    length = (end - start) % 1440 * 60
    return 0 <= begin - now <= 3600 and begin <= full_at < begin + length


def snapshot(context):
    if not context.get('storage_known'):
        raise ValueError('社区未提供有效保管箱容量，暂不能安排收菜提醒。')
    p = Decimal(context['storage_width'])
    if not p.is_finite() or not 0 <= p <= 100:
        raise ValueError('保管箱容量异常。')
    t = float(context['fetched_at_epoch'])
    return dict(p=str(p), at=t, t90=t + math.ceil(max(Decimal(0), 90-p)*864),
                full=t + math.ceil(max(Decimal(0), 100-p)*864))


def percent(snap):
    raw = Decimal(snap['p'])
    rounded = raw.quantize(Decimal('0.1'))
    if raw < 100 and rounded == 100:
        rounded = Decimal('99.9')
    value = format(rounded, 'f')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def moment(value, now):
    dt, today = datetime.fromtimestamp(value, TZ), datetime.fromtimestamp(now, TZ).date()
    day = '今天' if dt.date() == today else '明天' if dt.date() == today + timedelta(days=1) else f'{dt:%m月%d日}'
    return f'{day}{dt:%H点%M分}'


def title(kind):
    return '[AliceUID]' + {'normal':'收菜提醒', 'full':'满仓提醒', 'bed':'睡前收菜提醒',
                           'stop':'收菜提醒已自动关闭'}[kind]


def body(kind, snap, now):
    if kind == 'stop':
        return '指挥官，您的资源保管箱在连续两天23点检查时均为MAX，已自动关闭该账号在所有会话中的收菜提醒，并停止后台检查。'
    if kind == 'full':
        return '指挥官，您的资源保管箱容量已达到MAX，请及时上线收取资源。'
    text = f'指挥官，您的资源保管箱{"当前容量为" if kind == "bed" else "容量已达到"}{percent(snap)}%，预计{moment(snap["full"], now)}达到MAX'
    return text + ('。' if kind == 'bed' else '，请及时上线收取资源。')


def footer(kind, quiet_period, prefix):
    if kind == 'stop':
        return f'如需恢复，请在需要接收提醒的群聊或私聊中发送“{prefix}开启收菜提醒”。'
    if kind == 'bed':
        return f'收菜提醒免打扰时段：北京时间{quiet_period.replace("-", "—")}。\n建议睡前上线收取资源。'
    return ''
