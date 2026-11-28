"""Local assets and shared glass; reuse a snapshot's image before random theme."""
import asyncio
import base64
from collections import OrderedDict
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
import hashlib
import io
import json
import math
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFilter
from ..nikke_render.theme import apply_theme, get_card_theme_mode, get_card_theme, v2_theme_tokens

PACKAGE = Path(__file__).resolve().parent.parent
ENV = Environment(loader=FileSystemLoader(str(PACKAGE / 'templates')), autoescape=select_autoescape(['html']))
_images = OrderedDict()
_inflight = {}
_epochs = {}
MAX_BYTES = 24 * 1024 * 1024

_RESOURCE_META = {
    '钻石': ('核心抽卡资产', 'blue'),
    '芯尘': ('核心突破材料', 'red'),
    '高级招募券': ('限定招募道具', 'rainbow'),
    '招募券': ('常规招募道具', 'blue'),
    '信用点': ('基础养成货币', 'gold'),
    '战斗数据辑': ('同步等级升级', 'blue'),
    '黄金积分券': ('里程商店兑换', 'gold'),
    '白银积分券': ('躯体标签兑换', 'silver'),
}


@lru_cache(maxsize=2)
def _chevron_pattern_uri() -> str:
    """Crisp repeating '>' charge chevrons (22x14) for the storage progress fill."""
    w, h = 22, 14
    im = Image.new('RGBA', (w * 3, h * 3), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    pts = [(6, 4), (24, h * 3 // 2), (6, h * 3 - 4)]
    draw.line(pts, fill=(255, 255, 255, 210), width=6, joint='curve')
    out = im.resize((w, h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@lru_cache(maxsize=32)
def _crisp_icon_uri(path_str: str, css_px: int, dpr: float = 1.5) -> str:
    """Pre-sample small resource icons to physical pixels with light unsharp mask."""
    target = round(css_px * dpr)
    with Image.open(path_str) as src:
        im = src.convert('RGBA')
        scale = min(target / im.width, target / im.height)
        nw = max(1, round(im.width * scale))
        nh = max(1, round(im.height * scale))
        resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (target, target), (0, 0, 0, 0))
        canvas.paste(resized, ((target - nw) // 2, (target - nh) // 2))
        canvas = canvas.filter(ImageFilter.UnsharpMask(radius=0.8, percent=75, threshold=2))
    buf = io.BytesIO()
    canvas.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@lru_cache(maxsize=16)
def _micro_icon_uri(kind: str, hex_color: str, size: int = 16) -> str:
    s = 3
    W = size * s
    im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    rgb = tuple(int(hex_color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    lw = max(3, round(1.5 * s))
    if kind == 'globe':
        draw.ellipse((2 * s, 2 * s, 14 * s, 14 * s), outline=rgb, width=lw)
        draw.line((2.5 * s, 8 * s, 13.5 * s, 8 * s), fill=rgb, width=lw)
        draw.arc((5 * s, 2 * s, 11 * s, 14 * s), start=0, end=360, fill=rgb, width=lw)
    elif kind == 'id':
        draw.rounded_rectangle((2 * s, 3.5 * s, 14 * s, 12.5 * s), radius=2 * s, outline=rgb, width=lw)
        draw.line((4.5 * s, 6.8 * s, 11.5 * s, 6.8 * s), fill=rgb, width=lw)
        draw.line((4.5 * s, 9.5 * s, 9.2 * s, 9.5 * s), fill=rgb, width=lw)
    elif kind == 'battery':
        draw.rounded_rectangle((2 * s, 4 * s, 12.5 * s, 12 * s), radius=2 * s, outline=rgb, width=lw)
        draw.rounded_rectangle((12.5 * s, 6.4 * s, 14.5 * s, 9.6 * s), radius=s, fill=rgb)
        draw.line((5 * s, 6.5 * s, 5 * s, 9.5 * s), fill=rgb, width=lw)
        draw.line((7.6 * s, 6.5 * s, 7.6 * s, 9.5 * s), fill=rgb, width=lw)
    out = im.resize((size, size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _optical_ring_uri(
    percent: float | None,
    start_rgb: tuple[int, int, int],
    end_rgb: tuple[int, int, int],
    theme: str,
    size: int = 112,
) -> str:
    """3x supersampled optical sweep-gradient ring with groove, glow, and 90% tick."""
    dark = theme == 'dark'
    ring_disc = (16, 28, 48, 210) if dark else (255, 255, 255, 210)
    ring_disc_edge = (176, 208, 242, 75) if dark else (255, 255, 255, 240)
    ring_track = (255, 255, 255, 28) if dark else (20, 42, 72, 26)
    ring_groove = (0, 6, 16, 90) if dark else (15, 35, 62, 34)
    ring_tick = (255, 255, 255, 115) if dark else (20, 42, 72, 95)

    s = 3
    W = size * s
    im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    cx = cy = W / 2.0
    outer_r = round(size * 0.445) * s
    stroke = round(size * 0.088) * s
    inner_r = outer_r - stroke
    disc_r = inner_r - 2 * s

    disc = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse(
        (cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r),
        fill=ring_disc, outline=ring_disc_edge, width=s,
    )
    im = Image.alpha_composite(im, disc)

    track = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    td = ImageDraw.Draw(track)
    td.ellipse((cx - outer_r - s, cy - outer_r - s, cx + outer_r + s, cy + outer_r + s), fill=ring_groove)
    td.ellipse((cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r), fill=ring_track)
    td.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r), fill=(0, 0, 0, 0))
    im = Image.alpha_composite(im, track)

    tick_rad = math.radians(234.0)
    t_in, t_out = inner_r - s, outer_r + s
    ImageDraw.Draw(im).line(
        (cx + t_in * math.cos(tick_rad), cy + t_in * math.sin(tick_rad),
         cx + t_out * math.cos(tick_rad), cy + t_out * math.sin(tick_rad)),
        fill=ring_tick, width=2 * s,
    )

    if percent is not None and percent > 0:
        clamped = max(0.0, min(100.0, float(percent)))
        start_deg = -90.0
        span_deg = 360.0 * clamped / 100.0
        end_deg = start_deg + span_deg

        glow = Image.new('RGBA', (W, W), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        mid_rgb = tuple((a + b) // 2 for a, b in zip(start_rgb, end_rgb))
        if clamped >= 99.95:
            gd.ellipse((cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r), fill=mid_rgb + (80,))
        else:
            gd.pieslice((cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r), start=start_deg, end=end_deg, fill=mid_rgb + (80,))
        gd.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r), fill=(0, 0, 0, 0))
        im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(4 * s)))

        arc_layer = Image.new('RGBA', (W, W), (0, 0, 0, 0))
        ad = ImageDraw.Draw(arc_layer)
        steps = max(24, int(span_deg / 2.5))
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            a0 = start_deg + span_deg * t0
            a1 = start_deg + span_deg * t1 + 0.6
            tm = (t0 + t1) * 0.5
            rgb = tuple(round(start_rgb[c] + (end_rgb[c] - start_rgb[c]) * tm) for c in range(3)) + (255,)
            ad.pieslice((cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r), start=a0, end=a1, fill=rgb)
        ad.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r), fill=(0, 0, 0, 0))

        if clamped < 99.95:
            center_r = (outer_r + inner_r) / 2.0
            cap_r = stroke / 2.0
            for deg, cap_rgb in ((start_deg, start_rgb), (end_deg, end_rgb)):
                rad = math.radians(deg)
                px, py = cx + center_r * math.cos(rad), cy + center_r * math.sin(rad)
                ad.ellipse((px - cap_r, py - cap_r, px + cap_r, py + cap_r), fill=cap_rgb + (255,))
            end_rad = math.radians(end_deg)
            ex, ey = cx + center_r * math.cos(end_rad), cy + center_r * math.sin(end_rad)
            hr = cap_r * 0.45
            ad.ellipse((ex - hr, ey - hr, ex + hr, ey + hr), fill=(255, 255, 255, 190))

        im = Image.alpha_composite(im, arc_layer)

    out = im.resize((size, size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _liquid_resource_palette(color: str, palette: dict) -> dict:
    if color == 'dark':
        return {
            'page_bg': palette['page_bg'],
            'ink': palette['ink'],
            'ink_soft': palette['credit_ink'],
            'muted': palette['muted'],
            'glass_grad': palette['glass_bg'],
            'glass_border': palette['glass_border'],
            'glass_shadow': palette['glass_shadow'],
            'avatar_bg': 'rgba(8,16,30,0.46)',
            'avatar_border': 'rgba(166,198,232,0.58)',
            'avatar_inset_top': 'rgba(255,255,255,0.28)',
            'micro_pill_bg': 'rgba(10,20,36,0.62)',
            'micro_pill_border': 'rgba(176,208,242,0.26)',
            'dashed_line': 'rgba(176,208,242,0.22)',
            'dashed_soft': 'rgba(176,208,242,0.12)',
            'icon_stage_bg': 'rgba(255,255,255,0.10)',
            'icon_stage_border': 'rgba(176,208,242,0.24)',
            'track_bg': 'rgba(255,255,255,0.09)',
            'est_glass_bg': 'rgba(255,255,255,0.07)',
            'est_glass_border': 'rgba(176,208,242,0.22)',
        }
    return {
        'page_bg': palette['page_bg'],
        'ink': palette['ink'],
        'ink_soft': '#2B3F57',
        'muted': palette['muted'],
        'glass_grad': palette['glass_bg'],
        'glass_border': palette['glass_border'],
        'glass_shadow': palette['glass_shadow'],
        'avatar_bg': 'rgba(255,255,255,0.40)',
        'avatar_border': 'rgba(255,255,255,0.92)',
        'avatar_inset_top': 'rgba(255,255,255,0.75)',
        'micro_pill_bg': 'rgba(255,255,255,0.68)',
        'micro_pill_border': 'rgba(255,255,255,0.92)',
        'dashed_line': 'rgba(25,50,82,0.18)',
        'dashed_soft': 'rgba(25,50,82,0.10)',
        'icon_stage_bg': 'rgba(255,255,255,0.48)',
        'icon_stage_border': 'rgba(255,255,255,0.88)',
        'track_bg': 'rgba(20,42,72,0.09)',
        'est_glass_bg': 'rgba(255,255,255,0.40)',
        'est_glass_border': 'rgba(255,255,255,0.80)',
    }


def _resource_store():
    try:
        from ..nikke_config.config import MAIN_PATH
    except (ImportError, AttributeError, RuntimeError):
        return None
    from ..nikke_character.cache import PanelCache
    return PanelCache(MAIN_PATH / 'cache' / 'resource_images')


def invalidate_status_images(owner_key):
    owner = hashlib.sha256(json.dumps(owner_key, sort_keys=True, default=str).encode()).hexdigest()
    _epochs[owner] = _epochs.get(owner, 0) + 1
    _images.clear()
    store = _resource_store()
    if store is not None:
        store.purge(owner)


def status_style_key(*, layout=None):
    """Presentation changes invalidate the resource ready-image window too."""
    from ..nikke_render.cache import style_version
    from ..nikke_render.glass_settings import get_resource_card_layout
    return dict(style_version(), resource_layout=get_resource_card_layout(layout))


def status_html(context, theme=None):
    from ..nikke_render.fonts import apply_font_html
    from ..nikke_render.glass_settings import get_resource_card_layout
    context = copy.deepcopy(context)
    resolved_theme = theme or context.get('card_theme')
    if context.get('kind') == 'resources':
        resource_layout = get_resource_card_layout(context.get('resource_layout'))
        scene_h = 626 if resource_layout == '详细' else 492
        context = apply_theme(context, resolved_theme, scene_width=730, scene_height=scene_h)
        color = context['card_theme']
        accent = '#1565B4' if color == 'light' else '#6BC4FF'
        palette = v2_theme_tokens('Water', color, opacity=context.get('card_opacity'))['palette']
        lq = _liquid_resource_palette(color, palette)
        by_name = {}
        from .builder import compact_number
        from ..nikke_resource.media import media_path
        for item in context.get('items', []):
            path = media_path('assets/status') / item['icon_name']
            uri = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
            item['icon_url'] = uri
            item['crisp_24_url'] = _crisp_icon_uri(str(path), 24, 1.5)
            item['crisp_22_url'] = _crisp_icon_uri(str(path), 22, 1.5)
            cat, hl = _RESOURCE_META.get(item.get('name'), ('游戏资源', ''))
            item.setdefault('category', cat)
            item.setdefault('highlight', hl)
            if item.get('known') and item.get('exact'):
                try:
                    raw_val = int(str(item['exact']).replace(',', ''))
                    item['compact_game_value'] = compact_number(raw_val)
                except ValueError:
                    item['compact_game_value'] = item.get('value', '—')
            else:
                item['compact_game_value'] = item.get('value', '—')
            by_name[item.get('name')] = item

        context['resource_layout'] = resource_layout
        context['left_items'] = [by_name[n] for n in ('钻石', '高级招募券', '招募券', '黄金积分券', '白银积分券') if n in by_name]
        context['outpost_items'] = [by_name[n] for n in ('芯尘', '信用点', '战斗数据辑') if n in by_name]
        context['palette'] = palette
        context['lq'] = lq
        context['accent'] = accent
        context['background_uri'] = context.get('frost_scene_uri', '')
        context['font_family'] = 'MiSans'
        context['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')
        context['chevron_pattern_uri'] = _chevron_pattern_uri()
        context['icon_region_uri'] = _micro_icon_uri('globe', lq['ink_soft'], 11)
        context['icon_uid_uri'] = _micro_icon_uri('id', lq['ink_soft'], 11)
        context['icon_battery_uri'] = _micro_icon_uri('battery', accent, 16)

        raw_color = str(context.get('storage_color') or '').lower()
        if not context.get('storage_known'):
            context['storage_badge_text'] = '未知'
            context['storage_badge_color'] = lq['muted']
            context['storage_badge_bg'] = lq['est_glass_bg']
            context['storage_badge_border'] = lq['est_glass_border']
            context['storage_fill_gradient'] = accent
            context['storage_ring_uri'] = _optical_ring_uri(0.0, (99, 200, 255), (29, 114, 210), color, size=112)
            context['ring_sub_text'] = '未知'
            context['est_90_color'] = lq['ink']
            context['est_full_color'] = lq['ink']
        elif raw_color == '#d84b50':
            c = '#D84B50' if color == 'light' else '#FF6E74'
            context['storage_badge_text'] = '即将满仓'
            context['storage_badge_color'] = c
            context['storage_badge_bg'] = 'rgba(216,75,80,0.12)' if color == 'light' else 'rgba(255,110,116,0.16)'
            context['storage_badge_border'] = 'rgba(216,75,80,0.34)' if color == 'light' else 'rgba(255,110,116,0.40)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #D84B50, #FF7A7F)'
            pct = float(Decimal(context['storage_width']))
            context['storage_ring_uri'] = _optical_ring_uri(pct, (255, 148, 152), (216, 67, 78), color, size=112)
            context['ring_sub_text'] = '已满仓' if pct >= 100 else '即将满仓'
            context['est_90_color'] = c
            context['est_full_color'] = c
        elif raw_color == '#e39327':
            c = '#C97810' if color == 'light' else '#F6B856'
            context['storage_badge_text'] = '较高水位'
            context['storage_badge_color'] = c
            context['storage_badge_bg'] = 'rgba(227,147,39,0.12)' if color == 'light' else 'rgba(246,184,86,0.16)'
            context['storage_badge_border'] = 'rgba(227,147,39,0.32)' if color == 'light' else 'rgba(246,184,86,0.40)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #E39327, #F6C15C)'
            pct = float(Decimal(context['storage_width']))
            context['storage_ring_uri'] = _optical_ring_uri(pct, (246, 193, 92), (227, 147, 39), color, size=112)
            context['ring_sub_text'] = '较高水位'
            context['est_90_color'] = c
            context['est_full_color'] = lq['ink']
        else:
            context['storage_badge_text'] = '充能中'
            context['storage_badge_color'] = accent
            context['storage_badge_bg'] = 'rgba(21,101,180,0.12)' if color == 'light' else 'rgba(107,196,255,0.14)'
            context['storage_badge_border'] = 'rgba(21,101,180,0.32)' if color == 'light' else 'rgba(107,196,255,0.34)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #1E7AD4, #4CA5F5)'
            pct = float(Decimal(context['storage_width']))
            context['storage_ring_uri'] = _optical_ring_uri(pct, (99, 200, 255), (29, 114, 210), color, size=112)
            context['ring_sub_text'] = '充能中'
            context['est_90_color'] = lq['ink']
            context['est_full_color'] = lq['ink']
        return apply_font_html(ENV.get_template('status.html').render(**context), embed=False)

    height = max(760, 440 + 118 * len(context.get('bosses', [])))
    context = apply_theme(context, resolved_theme, scene_width=800, scene_height=height)
    context.update(v2_theme_tokens(None, context['card_theme'], opacity=context.get('card_opacity')))
    context['font_family'] = 'MiSans'
    context['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')
    return apply_font_html(ENV.get_template('status.html').render(**context), embed=False)


async def draw_status(context, *, owner_key):
    from ..nikke_render.render import render_html
    from ..nikke_render.language import get_card_language
    from ..nikke_render.fonts import resolve_font
    from ..nikke_render.glass_settings import capture_glass, get_resource_card_layout
    context = capture_glass(context)
    mode = get_card_theme_mode()
    font = resolve_font()
    resource_layout = get_resource_card_layout(context.get('resource_layout')) if context.get('kind') == 'resources' else None
    stable = dict(
        context, render_version='alice-v1403-liquid-status-1', theme_mode=mode,
        language=get_card_language(), font=font.fingerprint, owner=owner_key,
    )
    stable['presentation'] = status_style_key(layout=resource_layout)
    key = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    store = _resource_store() if context.get('kind') == 'resources' else None
    owner = hashlib.sha256(json.dumps(owner_key, sort_keys=True, default=str).encode()).hexdigest()
    epoch = _epochs.get(owner, 0)
    if key in _images:
        _images.move_to_end(key)
        return _images[key]
    if store is not None:
        cached = store.image(owner, 'resources', key)
        if cached is not None:
            return cached

    async def render():
        root_width = 730 if context.get('kind') == 'resources' else 800
        png = await render_html(status_html(context, get_card_theme(mode)), root_width=root_width)
        if _epochs.get(owner, 0) != epoch:
            raise ValueError('绑定已更新，旧状态图已失效。')
        if store is not None:
            store.save_image(owner, 'resources', key, png)
        _images[key] = png
        while sum(map(len, _images.values())) > MAX_BYTES and _images:
            _images.popitem(last=False)
        return png

    task = _inflight.get(key)
    if task is None:
        task = asyncio.create_task(render())
        _inflight[key] = task

        def done(finished):
            if _inflight.get(key) is finished:
                _inflight.pop(key, None)
            if not finished.cancelled():
                finished.exception()

        task.add_done_callback(done)
    return await asyncio.shield(task)
