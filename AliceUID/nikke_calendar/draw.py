"""Render high-fidelity official Blablalink activity calendar into PNG via GsCore pytakumi."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import base64
from pathlib import Path
import time

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..nikke_render.fonts import apply_font_html
from ..nikke_render.language import get_card_language, localize_html
from ..nikke_render.theme import apply_theme, get_card_theme, v2_theme_tokens
from ..nikke_resource.media import media_path
from ..version import VERSION
from .assets import avatar_url, banner_url, prepare_calendar_assets, reward_icon_url


@lru_cache(maxsize=1)
def _alice_icon_uri() -> str:
    for p in (media_path('assets/ICON.png'), Path(__file__).resolve().parents[2] / 'ICON.png'):
        if p.is_file():
            try:
                return 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
            except OSError:
                pass
    return ''

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates'
_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml']),
)
_BJ_TZ = timezone(timedelta(hours=8))


def _int_ts(val) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_range(start_ts: int, end_ts: int) -> str:
    s = datetime.fromtimestamp(start_ts, _BJ_TZ).strftime('%y/%m/%d %H:%M')
    e = datetime.fromtimestamp(end_ts, _BJ_TZ).strftime('%m/%d %H:%M')
    return f'{s} ~ {e}'


def _fmt_full_range(start_ts: int, end_ts: int) -> str:
    s = datetime.fromtimestamp(start_ts, _BJ_TZ).strftime('%Y-%m-%d %H:%M')
    e = datetime.fromtimestamp(end_ts, _BJ_TZ).strftime('%Y-%m-%d %H:%M')
    return f'{s} ~ {e}'


def _fmt_remain_short(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours = rem // 3600
    if days > 0:
        return f'{days}天{hours}小时'
    mins = (rem % 3600) // 60
    if hours > 0:
        return f'{hours}小时{mins}分'
    return f'{max(1, mins)}分钟'


def _status_info(start_ts: int, end_ts: int, now: int) -> tuple[str, str, str]:
    if start_ts > now:
        return 'upcoming', '即将开启', f'距开启 {_fmt_remain_short(start_ts - now)}'
    remain = end_ts - now
    if remain <= 3 * 86400:
        return 'ending', '即将结束', f'剩余 {_fmt_remain_short(remain)}'
    return 'active', '进行中', f'剩余 {_fmt_remain_short(remain)}'


def _skin_source_label(row: dict) -> str:
    t = str(row.get('type') or '')
    name = str(row.get('name') or '')
    if t == 'SeasonPass' or 'PASS' in name.upper():
        return '妮姬 PASS'
    if '簽到' in name or '签到' in name or 'LOGIN' in str(row.get('banner') or '').upper():
        return '签到赠送'
    return '时装抽取'


def build_calendar_context(
    payload: dict,
    *,
    assets: dict[str, str] | None = None,
    now: float | None = None,
    theme: str | None = None,
    language: str | None = None,
) -> dict:
    cur_now = int(now if now is not None else time.time())
    assets = assets or {}
    data = payload.get('data') if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}

    # 1. character_gacha (Plan A: top avatar strip + ALL active 3:1 banners below)
    char_items = []
    for idx, row in enumerate(((data.get('character_gacha') or {}).get('items') or [])):
        st, ed = _int_ts(row.get('start_time')), _int_ts(row.get('end_time'))
        if ed <= 0 or ed < cur_now:
            continue
        chars = [c for c in (row.get('characters') or []) if isinstance(c, dict)]
        lead_char = chars[0] if chars else {}
        av_key = avatar_url(lead_char.get('resource_id', ''), 0)
        b_key = banner_url(row.get('banner', ''), row.get('type'))
        status, status_label, remain_text = _status_info(st, ed, cur_now)
        char_names = ' / '.join(str(c.get('name') or '').strip() for c in chars if c.get('name'))
        char_items.append({
            'active_first': idx == 0,
            'title': char_names or str(row.get('name') or '队员招募'),
            'pool_type': str(row.get('name') or '特殊招募'),
            'avatar_uri': assets.get(av_key, ''),
            'banner_uri': assets.get(b_key, ''),
            'short_remain': _fmt_remain_short((st - cur_now) if st > cur_now else (ed - cur_now)),
            'status': status,
            'status_label': status_label,
            'remain_text': remain_text,
            'time_range': _fmt_range(st, ed),
            'description': ' '.join(str(row.get('description') or '').split())[:90],
        })

    # 2. skin_gacha (top avatar strip for all + 1 featured 3:1 banner + adaptive compact grid for rest)
    skin_items = []
    raw_skins = [
        r for r in ((data.get('skin_gacha') or {}).get('items') or [])
        if _int_ts(r.get('end_time')) >= cur_now
    ]
    raw_skins.sort(key=lambda r: (0 if r.get('type') != 'SeasonPass' else 1, _int_ts(r.get('end_time'))))
    for idx, row in enumerate(raw_skins):
        st, ed = _int_ts(row.get('start_time')), _int_ts(row.get('end_time'))
        av_key = avatar_url(row.get('resource_id', ''), row.get('costume_index', 0))
        if row.get('type') == 'SeasonPass':
            b_key = f"skin_banner:{row.get('banner')}:{row.get('resource_id')}:{row.get('costume_index', 0)}"
        else:
            b_key = banner_url(row.get('banner', ''), row.get('type'))
        status, status_label, remain_text = _status_info(st, ed, cur_now)
        skin_items.append({
            'active_first': idx == 0,
            'title': str(row.get('costume_name') or row.get('name') or '最新时装'),
            'source_tag': _skin_source_label(row),
            'avatar_uri': assets.get(av_key, ''),
            'banner_uri': assets.get(b_key, ''),
            'short_remain': _fmt_remain_short((st - cur_now) if st > cur_now else (ed - cur_now)),
            'status': status,
            'status_label': status_label,
            'remain_text': remain_text,
            'time_range': _fmt_range(st, ed),
            'description': ' '.join(str(row.get('description') or '').split())[:90],
        })
    featured_skin = skin_items[0] if skin_items else None
    other_skins = skin_items[1:] if len(skin_items) > 1 else []

    # 3. version_event
    event_items = []
    for row in (data.get('version_event') or {}).get('items') or []:
        st, ed = _int_ts(row.get('start_time')), _int_ts(row.get('end_time'))
        if ed <= 0 or ed < cur_now:
            continue
        status, status_label, remain_text = _status_info(st, ed, cur_now)
        r_icons = [
            assets[u] for rw in (row.get('rewards') or [])[:5]
            if (u := reward_icon_url(rw)) and u in assets
        ]
        event_items.append({
            'title': str(row.get('name') or '版本活动'),
            'subtitle': ' '.join(str(row.get('description') or '').split())[:52],
            'time_range': _fmt_range(st, ed),
            'short_remain': _fmt_remain_short((st - cur_now) if st > cur_now else (ed - cur_now)),
            'status': status,
            'status_label': status_label,
            'rewards': r_icons,
        })

    # 4. raid
    raid_items = []
    for row in (data.get('raid') or {}).get('items') or []:
        st, ed = _int_ts(row.get('start_time')), _int_ts(row.get('end_time'))
        if ed <= 0 or ed < cur_now:
            continue
        status, status_label, remain_text = _status_info(st, ed, cur_now)
        raid_items.append({
            'title': str(row.get('name') or '突袭活动'),
            'time_range': _fmt_range(st, ed),
            'short_remain': _fmt_remain_short((st - cur_now) if st > cur_now else (ed - cur_now)),
            'status': status,
            'status_label': status_label,
        })

    # 5. simulation_room (merge main season + active 2-week buff reset cycle)
    sim_rows = [
        r for r in ((data.get('simulation_room') or {}).get('items') or [])
        if _int_ts(r.get('end_time')) >= cur_now
    ]
    sim_card = None
    if sim_rows:
        # Longest span with rewards is the season wrapper; shortest active span is the current buff cycle
        season_row = max(sim_rows, key=lambda r: (_int_ts(r.get('end_time')) - _int_ts(r.get('start_time')), len(r.get('rewards') or [])))
        active_cycles = [r for r in sim_rows if _int_ts(r.get('start_time')) <= cur_now <= _int_ts(r.get('end_time'))]
        buff_row = min(active_cycles, key=lambda r: _int_ts(r.get('end_time'))) if active_cycles else season_row
        s_st, s_ed = _int_ts(season_row.get('start_time')), _int_ts(season_row.get('end_time'))
        b_ed = _int_ts(buff_row.get('end_time'))
        sim_rewards = [
            assets[u] for rw in (season_row.get('rewards') or [])[:6]
            if (u := reward_icon_url(rw)) and u in assets
        ]
        sim_card = {
            'title': str(season_row.get('name') or '超频赛季'),
            'time_range': _fmt_range(s_st, s_ed),
            'rewards': sim_rewards,
            'season_remain': _fmt_remain_short(s_ed - cur_now),
            'buff_remain': _fmt_remain_short(b_ed - cur_now),
        }

    # 6. arena (main 3 arenas + Champion Arena Promotion & Championship sub-schedules)
    arena_main = []
    promo_rows = []
    champ_rows = []
    _PROMO_MAP = {'ArenaCheerRound': '应援', 'Top64': 'Top 64', 'Top32': 'Top 32', 'Top16': 'Top 16'}
    _CHAMP_MAP = {'Top8': 'Top 8', 'Top4': 'Top 4', 'Final': '决赛'}

    for row in (data.get('arena') or {}).get('items') or []:
        st, ed = _int_ts(row.get('start_time')), _int_ts(row.get('end_time'))
        atype = str(row.get('arena_type') or '')
        name = str(row.get('name') or atype)
        if atype in ('ArenaRookieSeason', 'ArenaSpecialSeason', 'ArenaChampionSeason'):
            if ed >= cur_now:
                status, status_label, _ = _status_info(st, ed, cur_now)
                arena_main.append({
                    'title': name,
                    'time_range': _fmt_range(st, ed),
                    'short_remain': _fmt_remain_short((st - cur_now) if st > cur_now else (ed - cur_now)),
                    'status': status,
                })
        elif atype in ('ArenaPromotionRound', 'Top64', 'Top32', 'Top16') or name in ('64強', '32強', '16強'):
            label = 'Top 64' if '64' in name else ('Top 32' if '32' in name else ('Top 16' if '16' in name else name))
            state_txt = '已结束' if ed < cur_now else (f'进行中 · {_fmt_remain_short(ed - cur_now)}' if st <= cur_now else _fmt_full_range(st, ed))
            promo_rows.append({'label': label, 'state': state_txt, 'active': st <= cur_now <= ed, '_st': st})
        elif atype in ('Top8', 'Top4', 'Final', 'ArenaChampionshipRound') or name in ('8強', '4強', '決賽', '决赛'):
            label = 'Top 8' if '8' in name else ('Top 4' if '4' in name else ('决赛' if ('決' in name or '决' in name) else name))
            state_txt = '已结束' if ed < cur_now else (f'进行中 · {_fmt_remain_short(ed - cur_now)}' if st <= cur_now else _fmt_full_range(st, ed))
            champ_rows.append({'label': label, 'state': state_txt, 'active': st <= cur_now <= ed, '_st': st})

    promo_rows.sort(key=lambda r: r['_st'])
    champ_rows.sort(key=lambda r: r['_st'])

    resolved_theme = get_card_theme(theme, default='random')
    resolved_lang = language or get_card_language()
    themed = apply_theme({}, resolved_theme, scene_width=960, scene_height=2400)
    return {
        'char_items': char_items,
        'skin_items': skin_items,
        'featured_skin': featured_skin,
        'other_skins': other_skins,
        'event_items': event_items,
        'raid_items': raid_items,
        'sim_card': sim_card,
        'arena_main': arena_main,
        'promo_rows': promo_rows,
        'champ_rows': champ_rows,
        'captured_text': datetime.fromtimestamp(cur_now, _BJ_TZ).strftime('%Y-%m-%d %H:%M'),
        'hero_art': _alice_icon_uri(),
        'app_version': VERSION,
        'card_theme': resolved_theme,
        'frost_scene_uri': themed.get('frost_scene_uri', ''),
        'palette': v2_theme_tokens(None, resolved_theme)['palette'],
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
    assets_cache_dir: Path | None = None,
    now: float | None = None,
    theme: str | None = None,
    language: str | None = None,
    assets: dict[str, str] | None = None,
) -> bytes:
    from ..nikke_render.render import render_html
    if assets is None:
        if assets_cache_dir is None:
            from ..nikke_config.config import CACHE_PATH
            assets_cache_dir = CACHE_PATH / 'calendar' / 'assets'
        assets = await prepare_calendar_assets(payload, assets_cache_dir, now=now)
    ctx = build_calendar_context(payload, assets=assets, now=now, theme=theme, language=language)
    html = render_calendar_html(ctx)
    return await render_html(html, root_width=960, dpi=144)
