"""Lazy GsCore configuration and shared renderer-safe card theme tokens."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import base64
import io
import threading
from weakref import WeakKeyDictionary

THEME_RANDOM_STRATEGIES = ('纯随机', '交替', '昼夜')
_ALT_LOCK = threading.Lock()
_ALT_NEXT = 'light'
_TASK_ALT_THEME: WeakKeyDictionary = WeakKeyDictionary()
_BJ_TZ = timezone(timedelta(hours=8))


def _configured(key: str, allowed: tuple[str, ...], default: str) -> str:
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(key).data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        value = default
    return value if value in allowed else default


def get_theme_random_strategy() -> str:
    return _configured('AliceUID_ThemeRandomStrategy', THEME_RANDOM_STRATEGIES, '纯随机')


def _day_night_theme(now: datetime | None = None) -> str:
    dt = now.astimezone(_BJ_TZ) if now is not None else datetime.now(_BJ_TZ)
    return 'light' if 6 <= dt.hour < 18 else 'dark'


def _next_alternating_theme() -> str:
    """Advance alternating cursor once per async request task (or per call in sync mode)."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    if task is not None and task in _TASK_ALT_THEME:
        return _TASK_ALT_THEME[task]
    global _ALT_NEXT
    with _ALT_LOCK:
        cur = _ALT_NEXT
        _ALT_NEXT = 'dark' if cur == 'light' else 'light'
    if task is not None:
        _TASK_ALT_THEME[task] = cur
    return cur


def resolve_random_color(*, strategy: str | None = None, now: datetime | None = None) -> str:
    import random
    strat = strategy if strategy in THEME_RANDOM_STRATEGIES else get_theme_random_strategy()
    if strat == '昼夜':
        return _day_night_theme(now)
    if strat == '交替':
        return _next_alternating_theme()
    return random.choice(('light', 'dark'))


def get_card_theme(theme: str | None = None, default: str = 'random') -> str:
    if theme in ('light', 'dark'):
        return theme
    selected = theme if theme == 'random' else get_card_theme_mode(default)
    if selected == 'random':
        return resolve_random_color()
    return selected


def get_card_theme_mode(default='random'):
    """Stable cache identity; resolves concrete light/dark under 交替/昼夜 so dual caches work."""
    raw = _configured('AliceUID_CardTheme', ('light', 'dark', 'random'), default if default in ('light', 'dark', 'random') else 'random')
    if raw == 'random':
        strat = get_theme_random_strategy()
        if strat == '昼夜':
            return _day_night_theme()
        if strat == '交替':
            return _next_alternating_theme()
    return raw


def get_card_style(style: str | None = None) -> str:
    from .layouts import character_layout_keys
    if style in character_layout_keys():
        return style
    return get_character_style()


def card_theme(theme: str | None = None) -> dict:
    resolved = apply_theme({}, theme, with_wallpaper=False)
    return dict(resolved['theme'], card_theme=resolved['card_theme'])


CHARACTER_THEMES = ('纵版亮色', '纵版暗色', '横版亮色', '横版暗色')
LEGACY_STYLE_MAP = {
    'compact_light': '纵版亮色',
    'compact_dark': '纵版暗色',
    'wide_light': '横版亮色',
    'wide_dark': '横版暗色',
}
STYLE_LAYOUT_THEME = {
    '纵版亮色': ('compact', 'light'),
    '纵版暗色': ('compact', 'dark'),
    '横版亮色': ('wide', 'light'),
    '横版暗色': ('wide', 'dark'),
}
CHARACTER_RANDOM_MODES = ('关闭随机', '横版随机', '纵版随机', '全部随机')
LEGACY_RANDOM_MAP = {
    'off': '关闭随机',
    'wide': '横版随机',
    'compact': '纵版随机',
    'all': '全部随机',
}


def normalize_character_style(value: object, *, default: str = '横版亮色') -> str:
    text = str(value or '').strip()
    if text in STYLE_LAYOUT_THEME:
        return text
    return LEGACY_STYLE_MAP.get(text, default)


def normalize_character_random(value: object, *, default: str = '关闭随机') -> str:
    text = str(value or '').strip()
    if text in CHARACTER_RANDOM_MODES:
        return text
    return LEGACY_RANDOM_MAP.get(text, default)


def character_presentation_mode():
    try:
        from ..nikke_config.config import AliceUIDConfig
        fixed_raw = AliceUIDConfig.get_config('AliceUID_CharacterCardStyle').data
        random_raw = AliceUIDConfig.get_config('AliceUID_CharacterRandomTheme').data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        fixed_raw, random_raw = '横版亮色', '关闭随机'
    fixed = normalize_character_style(fixed_raw)
    rnd = normalize_character_random(random_raw)
    result = dict(fixed=fixed, random=rnd)
    if rnd != '关闭随机':
        strat = get_theme_random_strategy()
        if strat in ('交替', '昼夜'):
            result['strategy'] = strat
            result['resolved_color'] = resolve_random_color(strategy=strat)
    return result


def get_character_style(default='wide'):
    fixed = character_presentation_mode()['fixed']
    return STYLE_LAYOUT_THEME.get(fixed, (default, 'light'))[0]


def resolve_character_presentation(style=None, theme=None):
    """Choose once per new paint; the image cache keys the stable mode, not a random draw."""
    import random
    from .layouts import character_layout_keys
    mode = character_presentation_mode()
    if style in STYLE_LAYOUT_THEME:
        layout, color = STYLE_LAYOUT_THEME[style]
    elif style in LEGACY_STYLE_MAP:
        layout, color = STYLE_LAYOUT_THEME[LEGACY_STYLE_MAP[style]]
    elif style in character_layout_keys():
        layout = style
        color = STYLE_LAYOUT_THEME[mode['fixed']][1]
    elif style:
        layout = 'compact'
        color = STYLE_LAYOUT_THEME[mode['fixed']][1]
    else:
        if mode['random'] == '关闭随机':
            layout, color = STYLE_LAYOUT_THEME[mode['fixed']]
        elif mode['random'] == '横版随机':
            layout = 'wide'
            color = mode.get('resolved_color') or resolve_random_color()
        elif mode['random'] == '纵版随机':
            layout = 'compact'
            color = mode.get('resolved_color') or resolve_random_color()
        else:  # 全部随机
            layout = random.choice(('wide', 'compact'))
            color = mode.get('resolved_color') or resolve_random_color()
    if theme in ('light', 'dark'):
        color = theme
    elif theme == 'random':
        color = resolve_random_color()
    return layout, color


V2_UNIFIED_ACCENTS = {
    'light': '#D43D51',
    'dark': '#F6C15C',
    'soft_light': 'rgba(212,61,81,0.12)',
    'soft_dark': 'rgba(246,193,92,0.16)',
    'border_light': 'rgba(212,61,81,0.32)',
    'border_dark': 'rgba(246,193,92,0.38)',
}

V2_PALETTES = {
    'light': {
        'page_bg': '#E9EFF6',
        'ink': '#152233',
        'muted': '#4A5E78',
        'line': 'rgba(30,52,82,0.14)',
        'glass_bg': 'rgba(252,254,255,0.78)',
        'glass_border': 'rgba(255,255,255,0.92)',
        'glass_shadow': '0 6px 20px rgba(15,35,62,0.11)',
        'inner_top': 'rgba(255,255,255,0.75)',
        'slot_bg': 'rgba(18,38,68,0.055)',
        'empty_slot_bg': 'rgba(18,38,68,0.025)',
        'icon_stage_bg': 'rgba(255,255,255,0.22)',
        'portrait_stage_bg': 'rgba(252,254,255,0.52)',
        'sub_border': 'rgba(25,50,82,0.11)',
        'pill_bg': 'rgba(252,254,255,0.82)',
        'pill_inner_bg': 'rgba(18,38,68,0.065)',
        'line_normal_bg': 'rgba(255,255,255,0.58)',
        'line_normal_border': 'rgba(25,50,82,0.09)',
        'stage_tag': '#1C304A',
        'credit_ink': '#364A63',
    },
    'dark': {
        'page_bg': '#0B1320',
        'ink': '#F1F6FD',
        'muted': '#A6BCD4',
        'line': 'rgba(170,200,235,0.18)',
        'glass_bg': 'rgba(8,16,30,0.78)',
        'glass_border': 'rgba(166,198,232,0.28)',
        'glass_shadow': '0 8px 24px rgba(2,6,14,0.42)',
        'inner_top': 'rgba(255,255,255,0.14)',
        'slot_bg': 'rgba(255,255,255,0.06)',
        'empty_slot_bg': 'rgba(255,255,255,0.025)',
        'icon_stage_bg': 'rgba(255,255,255,0.075)',
        'portrait_stage_bg': 'rgba(8,16,30,0.56)',
        'sub_border': 'rgba(170,200,235,0.16)',
        'pill_bg': 'rgba(8,16,30,0.76)',
        'pill_inner_bg': 'rgba(255,255,255,0.08)',
        'line_normal_bg': 'rgba(255,255,255,0.055)',
        'line_normal_border': 'rgba(170,200,235,0.12)',
        'stage_tag': '#DCE8F7',
        'credit_ink': '#BDCCE0',
    },
}


def v2_theme_tokens(element_key: str | None = None, theme: str = 'light') -> dict:
    """Return unified Bento v2 palette and theme accent tokens (gold on dark, crimson on light)."""
    color = 'dark' if theme == 'dark' else 'light'
    acc = V2_UNIFIED_ACCENTS
    return {
        'palette': V2_PALETTES[color],
        'element_accent': acc[color],
        'element_accent_soft': acc[f'soft_{color}'],
        'element_accent_border': acc[f'border_{color}'],
    }


@lru_cache(maxsize=1)
def light_texture_uri() -> str:
    """Tiny deterministic abstract texture; no downloaded material."""
    from PIL import Image
    image = Image.new('RGBA', (96, 96))
    image.putdata([(80, 102, 130, 5 if (x * 17 + y * 29) % 11 == 0 else 0)
                   for y in range(96) for x in range(96)])
    output = io.BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def apply_theme(context: dict, theme: str | None = None, *, scene_width=1000, scene_height=1400, with_wallpaper=True) -> dict:
    """Return a context copy with card_theme name, theme tokens and texture URI."""
    from .glass_settings import capture_glass,blur_radius
    from ..nikke_commands import command_prefix
    context=capture_glass(context)
    theme = theme if theme in ('light', 'dark') else get_card_theme()
    dark = theme == 'dark'
    tokens = dict(page='#141c28' if dark else '#e9eef4',
                  ink='#f1f5fc' if dark else '#182536',
                  muted='#bdcce0' if dark else '#35475d',
                  accent='#81c8ff' if dark else '#124c77',
                  line='#4b5e76' if dark else '#ced8e3',
                  panel='#263448' if dark else '#f6f8fb',
                  glass='rgba(31,44,62,.91)' if dark else 'rgba(250,253,255,.88)',
                  surface_glass='rgba(20,32,50,.80)' if dark else 'rgba(248,251,255,.80)',
                  container_glass='rgba(20,32,50,.30)' if dark else 'rgba(248,251,255,.30)',
                  soft='#334359' if dark else '#e6edf5',
                  texture_uri=light_texture_uri())
    from .glass import image_uri
    if with_wallpaper:
        from .wallpaper import wallpaper_scene
        scene=wallpaper_scene(scene_width,scene_height,theme)
        from PIL import ImageFilter
        photo_uri=image_uri(scene.filter(ImageFilter.GaussianBlur(blur_radius(context['glass_strength']))))

    else:
        photo_uri=''
    return dict(context, command_prefix=command_prefix(), card_theme=theme, theme=tokens, texture_uri=tokens['texture_uri'],
                frost_scene_uri=photo_uri, frost_panel_uri='',
                background_source='local-card-bg',background_scene_width=scene_width,background_scene_height=scene_height)


WIDE_ART_BASE_SCALE = 0.825
WIDE_ART_SCALE_KEY = 'AliceUID_WideArtScaleOffset'


def parse_wide_art_scale_offset(value) -> int:
    """Parse a wide-card portrait scale offset percentage in [-100, 100]."""
    import re
    if isinstance(value, bool):
        raise ValueError('缩放微调不能为布尔值')
    if isinstance(value, int):
        offset = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith('%'):
            text = text[:-1].strip()
        if not re.fullmatch(r'[+-]?\d+', text):
            raise ValueError('请输入 -100 到 +100 之间的整数百分比')
        offset = int(text)
    else:
        raise ValueError('请输入 -100 到 +100 之间的整数百分比')
    if not -100 <= offset <= 100:
        raise ValueError('缩放微调范围须在 -100 到 +100 之间')
    return offset


def normalize_wide_art_scale_offset(value) -> str:
    try:
        return str(parse_wide_art_scale_offset(value))
    except ValueError:
        return '0'


def get_wide_art_scale_offset() -> int:
    try:
        from ..nikke_config.config import AliceUIDConfig
        raw = AliceUIDConfig.get_config(WIDE_ART_SCALE_KEY).data
        return parse_wide_art_scale_offset(raw)
    except (ImportError, AttributeError, KeyError, TypeError, ValueError):
        return 0
