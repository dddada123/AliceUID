"""Local assets and shared glass; reuse a snapshot's image before random theme."""
import asyncio
import base64
from collections import OrderedDict
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme, get_card_theme_mode, get_card_theme, v2_theme_tokens

PACKAGE = Path(__file__).resolve().parent.parent
ENV = Environment(loader=FileSystemLoader(str(PACKAGE / 'templates')), autoescape=select_autoescape(['html']))
_images = OrderedDict()
_inflight = {}
_epochs = {}
MAX_BYTES = 24 * 1024 * 1024

_RESOURCE_META = {
    '钻石': ('核心抽卡资产', 'gacha'),
    '信用点': ('基础养成货币', ''),
    '黄金积分券': ('里程商店兑换', 'gold'),
    '白银积分券': ('躯体标签兑换', ''),
    '战斗数据辑': ('同步等级升级', ''),
    '芯尘': ('核心突破材料', ''),
    '招募券': ('常规招募道具', ''),
    '高级招募券': ('限定招募道具', 'gacha'),
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


def status_style_key():
    """Presentation changes invalidate the resource ready-image window too."""
    from ..nikke_render.cache import style_version
    return style_version()


def status_html(context, theme=None):
    from ..nikke_render.icon_effects import icon_effect
    from ..nikke_render.fonts import apply_font_html
    context = copy.deepcopy(context)
    resolved_theme = theme or context.get('card_theme')
    if context.get('kind') == 'resources':
        context = apply_theme(context, resolved_theme, scene_width=730, scene_height=680)
        color = context['card_theme']
        accent = '#1565B4' if color == 'light' else '#6BC4FF'
        for item in context.get('items', []):
            from ..nikke_resource.media import media_path
            path = media_path('assets/status') / item['icon_name']
            uri = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
            item['icon_url'] = uri
            item['icon_shadow_url'] = icon_effect(uri, color)
            cat, hl = _RESOURCE_META.get(item.get('name'), ('游戏资源', ''))
            item.setdefault('category', cat)
            item.setdefault('highlight', hl)
        context['palette'] = v2_theme_tokens('Water', color)['palette']
        context['accent'] = accent
        context['background_uri'] = context.get('frost_scene_uri', '')
        context['font_family'] = 'MiSans'
        context['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')

        raw_color = str(context.get('storage_color') or '').lower()
        if not context.get('storage_known'):
            context['storage_badge_text'] = '未知'
            context['storage_badge_color'] = context['palette']['muted']
            context['storage_badge_bg'] = context['palette']['slot_bg']
            context['storage_badge_border'] = context['palette']['sub_border']
            context['storage_fill_gradient'] = accent
        elif raw_color == '#d84b50':
            c = '#D84B50' if color == 'light' else '#FF6E74'
            context['storage_badge_text'] = '即将满仓'
            context['storage_badge_color'] = c
            context['storage_badge_bg'] = 'rgba(216,75,80,0.12)' if color == 'light' else 'rgba(255,110,116,0.16)'
            context['storage_badge_border'] = 'rgba(216,75,80,0.32)' if color == 'light' else 'rgba(255,110,116,0.40)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #D84B50, #FF7A7F)'
        elif raw_color == '#e39327':
            c = '#C97810' if color == 'light' else '#F6B856'
            context['storage_badge_text'] = '较高水位'
            context['storage_badge_color'] = c
            context['storage_badge_bg'] = 'rgba(227,147,39,0.12)' if color == 'light' else 'rgba(246,184,86,0.16)'
            context['storage_badge_border'] = 'rgba(227,147,39,0.32)' if color == 'light' else 'rgba(246,184,86,0.40)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #E39327, #F6C15C)'
        else:
            context['storage_badge_text'] = '充能中'
            context['storage_badge_color'] = accent
            context['storage_badge_bg'] = 'rgba(21,101,180,0.12)' if color == 'light' else 'rgba(107,196,255,0.14)'
            context['storage_badge_border'] = 'rgba(21,101,180,0.32)' if color == 'light' else 'rgba(107,196,255,0.34)'
            context['storage_fill_gradient'] = 'linear-gradient(90deg, #1E7AD4, #4CA5F5)'
        return apply_font_html(ENV.get_template('status.html').render(**context), embed=False)

    height = max(900, 520 + 155 * len(context.get('bosses', [])))
    context = apply_theme(context, resolved_theme, scene_width=1000, scene_height=height)
    return ENV.get_template('status.html').render(**context)


async def draw_status(context, *, owner_key):
    from ..nikke_render.render import render_html
    from ..nikke_render.language import get_card_language
    from ..nikke_render.fonts import resolve_font
    from ..nikke_render.glass_settings import capture_glass
    context = capture_glass(context)
    mode = get_card_theme_mode()
    font = resolve_font()
    stable = dict(
        context, render_version='alice-v1215-bento-status-1', theme_mode=mode,
        language=get_card_language(), font=font.fingerprint, owner=owner_key,
    )
    stable['presentation'] = status_style_key()
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
        root_width = 730 if context.get('kind') == 'resources' else 1000
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
