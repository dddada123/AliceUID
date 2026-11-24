"""Render official Blablalink activity calendar JSON into PNG via GsCore pytakumi."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..nikke_render.fonts import apply_font_html
from ..nikke_render.language import get_card_language, localize_html
from ..nikke_render.theme import get_card_theme

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates'
_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml']),
)
_BJ_TZ = timezone(timedelta(hours=8))

_SECTION_DEFS = (
    ('version_event', '版本活动与签到', 'VERSION EVENTS', '当前暂无公开版本活动排期'),
    ('character_gacha', '角色招募卡池', 'CHARACTER RECRUIT', '当前暂无公开招募卡池'),
    ('skin_gacha', '时装与 PASS', 'COSTUMES & PASS', '当前暂无公开时装活动'),
    ('raid', '联盟 / 单人突袭', 'RAID SCHEDULE', '当前无排期突袭活动'),
    ('simulation_room', '超频模拟室', 'SIMULATION OVERCLOCK', '当前暂无超频赛程'),
    ('arena', '竞技场日程', 'ARENA SCHEDULE', '当前暂无竞技场赛程'),
)


def _int_ts(val) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, _BJ_TZ).strftime('%m/%d %H:%M')


def _fmt_remain(seconds: int, prefix: str) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours = rem // 3600
    if days > 0:
        return f'{prefix} {days} 天 {hours} 小时'
    mins = (rem % 3600) // 60
    if hours > 0:
        return f'{prefix} {hours} 小时 {mins} 分'
    return f'{prefix} {max(1, mins)} 分钟'


def _status_fields(start_ts: int, end_ts: int, now: int) -> tuple[str, str, str]:
    if start_ts > now:
        return 'upcoming', '即将开启', _fmt_remain(start_ts - now, '距开启')
    remain = end_ts - now
    if remain <= 3 * 86400:
        return 'ending', '即将结束', _fmt_remain(remain, '剩余')
    return 'active', '进行中', _fmt_remain(remain, '剩余')


def build_calendar_context(
    payload: dict,
    *,
    now: float | None = None,
    theme: str | None = None,
    language: str | None = None,
) -> dict:
    cur_now = int(now if now is not None else time.time())
    data = payload.get('data') if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}

    sections = []
    total_items = 0
    for key, title, en_title, empty_text in _SECTION_DEFS:
        mod = data.get(key) or {}
        raw_items = mod.get('items') if isinstance(mod, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []

        parsed_items = []
        for row in raw_items:
            if not isinstance(row, dict):
                continue
            start_ts = _int_ts(row.get('start_time'))
            end_ts = _int_ts(row.get('end_time'))
            if end_ts <= 0 or end_ts < cur_now:
                continue

            item_title = str(row.get('name') or row.get('costume_name') or row.get('arena_type') or '活动').strip()
            subtitle = ''
            if key == 'character_gacha':
                chars = [str(c.get('name') or '').strip() for c in (row.get('characters') or []) if isinstance(c, dict) and c.get('name')]
                if chars:
                    subtitle = 'UP 角色：' + ' / '.join(chars)
            elif key == 'skin_gacha':
                cname = str(row.get('costume_name') or '').strip()
                if cname:
                    subtitle = f'时装：{cname}'
            elif key in ('version_event', 'simulation_room'):
                desc = ' '.join(str(row.get('description') or '').split())
                if desc:
                    subtitle = desc[:48] + ('…' if len(desc) > 48 else '')

            # For simulation_room, skip duplicate long season wrapper if sub-cycles exist
            status, status_label, remain_text = _status_fields(start_ts, end_ts, cur_now)
            parsed_items.append({
                'title': item_title,
                'subtitle': subtitle,
                'time_range': f'{_fmt_ts(start_ts)} ～ {_fmt_ts(end_ts)}',
                'status': status,
                'status_label': status_label,
                'remain_text': remain_text,
                '_start': start_ts,
                '_end': end_ts,
            })

        # Keep arena & simulation concise: active items first, then upcoming (cap at 6 per section)
        parsed_items.sort(key=lambda x: (0 if x['_start'] <= cur_now else 1, x['_end'], x['_start']))
        if len(parsed_items) > 6:
            parsed_items = parsed_items[:6]

        total_items += len(parsed_items)
        sections.append({
            'key': key,
            'title': title,
            'en_title': en_title,
            'empty_text': empty_text,
            'items': parsed_items,
        })

    resolved_theme = get_card_theme(theme, default='dark')
    resolved_lang = language or get_card_language()
    return {
        'sections': sections,
        'total_items': total_items,
        'captured_text': datetime.fromtimestamp(cur_now, _BJ_TZ).strftime('%Y-%m-%d %H:%M'),
        'card_theme': resolved_theme,
        'html_lang': resolved_lang,
        'font_family': 'MiSans',
        'credit_timestamp': datetime.fromtimestamp(cur_now, _BJ_TZ).strftime('%Y-%m-%d·%H:%M'),
    }


def render_calendar_html(context: dict) -> str:
    html = _ENV.get_template('calendar.html').render(**context)
    localized = localize_html(html, language=context.get('html_lang'))
    return apply_font_html(localized, embed=False)


async def render_calendar_png(
    payload: dict,
    *,
    now: float | None = None,
    theme: str | None = None,
    language: str | None = None,
) -> bytes:
    from ..nikke_render.render import render_html
    ctx = build_calendar_context(payload, now=now, theme=theme, language=language)
    html = render_calendar_html(ctx)
    return await render_html(html, root_width=1040, dpi=144)
