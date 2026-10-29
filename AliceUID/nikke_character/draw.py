"""Character card HTML and resource preparation; rendering has no player writes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme, get_character_style

CARD_WIDTH = 1000
_ENV = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / 'templates')),
                   autoescape=select_autoescape(['html']))

_LABELS = {
    'Attacker': '火力型', 'Defender': '防御型', 'Supporter': '辅助型',
    'Fire': '燃烧', 'Water': '水冷', 'Wind': '风压', 'Electric': '电击', 'Iron': '铁甲',
    'Electronic': '电击', 'Electricity': '电击', 'Missilis': '米西利斯', 'Elysion': '极乐净土',
    'Tetra': '泰特拉', 'Pilgrim': '朝圣者', 'Abnormal': '反常',
    'MISSILIS': '米西利斯', 'ELYSION': '极乐净土', 'TETRA': '泰特拉',
    'PILGRIM': '朝圣者', 'ABNORMAL': '反常',
}


def aggregate_options(gear: list[dict]) -> dict:
    """Sum exact raw values by function and unit; count each line's tier once."""
    groups = {}
    total_level = 0
    known_levels = 0
    unknown_lines = 0
    unparsed_values = 0
    for item in gear:
        if item.get('tier') != 10:
            continue
        for line in item.get('lines', []):
            if line.get('status') == 'empty':
                continue
            level = line.get('level')
            if isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 15:
                total_level += level
                known_levels += 1
            else:
                unknown_lines += 1
            if not line.get('functions'):
                unparsed_values += 1
            for fn in line.get('functions', []):
                key, unit = fn.get('key'), fn.get('value_type')
                group = groups.setdefault((key, unit), {'name': fn.get('name') or key or '未知词条',
                                                        'sum': Decimal(0), 'known': 0, 'unknown': 0})
                try:
                    from .builder import overload_display_number
                    value = overload_display_number(key, fn.get('raw_value'), unit)
                    if value is None:
                        raise InvalidOperation
                    if not value.is_finite() or key is None or unit is None:
                        raise InvalidOperation
                except (InvalidOperation, ValueError, TypeError):
                    group['unknown'] += 1
                else:
                    group['sum'] += value
                    group['known'] += 1
    rows, entries = [], []
    for (key, unit), group in groups.items():
        value = group['sum']
        text = f'{value / 100:.2f}%' if unit == 'Percent' else format(value.normalize(), 'f')
        if not group['known']:
            text = '未知'
        elif group['unknown']:
            text += ' + 未知'
        rows.append({'name': group['name'], 'value': text})
        entries.append(dict(rows[-1], key=key))
    if unparsed_values:
        rows.append({'name': f'未解析词条（{unparsed_values}条）', 'value': '未知'})
        entries.append(dict(rows[-1], key='unknown'))
    return {'rows': rows, 'level': str(total_level) if known_levels else '未知',
            'level_partial': bool(unknown_lines), 'known_lines': known_levels, 'unknown_lines': unknown_lines,
            'entries': entries}


SUMMARY_ORDER = ('StatAtk', 'IncElementDmg', 'StatAmmoLoad', 'StatChargeTime', 'StatCritical', 'StatCriticalDamage')
SUMMARY_NAMES = dict(zip(SUMMARY_ORDER, ('攻击', '优越', '装弹', '蓄速', '暴击', '暴伤')),
                     StatChargeDamage='蓄伤', StatDef='防御', StatHitRate='命中',
                     StatAccuracyCircle='命中', OnHitRatio='命中', StatAmmo='装弹')


def summary_display(aggregate):
    """Limit presentation only; retain every raw aggregate row and its units."""
    order = {key: index for index, key in enumerate(SUMMARY_ORDER)}
    entries = sorted(aggregate['entries'], key=lambda row: order.get(row['key'], 99))
    compact = len(entries) > 3
    return [dict(row, name=SUMMARY_NAMES.get(row['key'], row['name']) if compact else row['name'])
            for row in entries[:6]]


def portrait_placement(source, kind, width, height):
    """Read source size without changing cached art; contain the complete portrait."""
    if kind != 'portraits':
        return ''
    try:
        import base64, io
        from PIL import Image
        if not source.startswith('data:image/') or ';base64,' not in source:
            return ''
        with Image.open(io.BytesIO(base64.b64decode(source.split(';base64,', 1)[1], validate=True))) as image:
            if image.width*image.height > 8_000_000:
                return ''
            bounds = image.convert('RGBA').getchannel('A').getbbox()
            if not bounds:
                return ''
            # Exact source aspect, without additional headroom or body crop.
            scale = min(width/image.width, height/image.height)
            w, h = image.width*scale, image.height*scale
            left = (width-w)/2
            top = (height-h)/2
            return f'width:{w:.2f}px;height:{h:.2f}px;left:{left:.2f}px;top:{top:.2f}px'
    except (ValueError, OSError, TypeError):
        return ''



def upper_body_placement(source, width=540, height=810, *, full_bounds=None, crop_top_pixels=850, anchor_x=None, anchor_y=None, head_top=None, canvas_width=1228):
    """Frame the upper body from high resolution art without rewriting its pixels."""
    try:
        import base64, io
        from PIL import Image
        if not source or not source.startswith('data:image/'):
            return ''
        with Image.open(io.BytesIO(base64.b64decode(source.split(';base64,',1)[1],validate=True))) as im:
            if im.width*im.height > 8_000_000:
                return ''
            bounds=im.convert('RGBA').getchannel('A').getbbox()
            if not bounds:
                return ''
            x,y,right,bottom=bounds
            if full_bounds and len(full_bounds) == 4:
                # Full embeds are alpha-trimmed. Discard the transparent header,
                # leave 50 CSS px above visible pixels, then show 850 native px.
                native_top, native_bottom = full_bounds[1], full_bounds[3]
                scale = (height-50)/min(crop_top_pixels, native_bottom-native_top) * (native_bottom-native_top)/im.height
                left=(width-im.width*scale)/2
                top=50
            else:
                scale=max((width-24)/(right-x),(height-18)/((bottom-y)*.65))
                left=(width-(right-x)*scale)/2-x*scale
                top=18-y*scale
            # Preserve the approved close-up scale. Only horizontal translation uses
            # the head anchor; weapons extend beneath the information surface.
            focus = anchor_x*im.width if isinstance(anchor_x,(int,float)) and .08<anchor_x<.92 else im.width/2
            left = width/2-focus*scale
            # Tall props (e.g. a parasol) can sit above the head. Keep the
            # matched head region within the upper third without shrinking art.
            if isinstance(head_top,(int,float)) and 0<=head_top<.5:
                # Preserve small head accessories; only correct a substantial prop gap.
                if head_top*im.height*scale>80:
                    top = 50-head_top*im.height*scale
            elif isinstance(anchor_y,(int,float)) and -.05<anchor_y<.65 and top+anchor_y*im.height*scale>180:
                top = 180-anchor_y*im.height*scale
            return f'width:{im.width*scale:.2f}px;height:{im.height*scale:.2f}px;left:{left:.2f}px;top:{top:.2f}px' 
    except (ValueError,OSError,TypeError,IndexError):
        return ''


def _equipment_info(context: dict, prepared_key: str, raw_key: str, label: str) -> dict:
    prepared = context.get(prepared_key) or {}
    raw = context.get(raw_key) or {}
    tid = raw.get('tid')
    name = prepared.get('name') or ('未装备' if tid == 0 else f'{label}信息未知')
    level = prepared.get('display_level')
    if level is None:
        level = '—' if tid == 0 else '等级未知' if prepared else f"Lv.{raw['lv']}" if raw.get('lv') is not None else '等级未知'
    elif isinstance(level, (int, float)):
        level = f'Lv.{level}'
    return dict(prepared, name=name, display_level=level,
                notice=prepared.get('notice') or ('标识未知' if tid is None else f'ID {tid}' if tid else ''),
                rarity=prepared.get('rarity') or '')


def render_character_html(context: dict, style: str | None = None, theme: str | None = None) -> str:
    from .builder import normalize_overload_context
    context = normalize_overload_context(context)
    from ..nikke_render.layouts import resolve_character_layout
    from ..nikke_render.theme import resolve_character_presentation
    style,theme = resolve_character_presentation(style,theme)
    layout = resolve_character_layout(style)
    style = layout.key
    context = apply_theme(context, theme, with_wallpaper=False)
    context.setdefault('generated_at', datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M'))
    try:
        generated = datetime.fromisoformat(str(context['generated_at']))
        if generated.tzinfo is not None:
            generated = generated.astimezone(timezone(timedelta(hours=8)))
    except (ValueError, TypeError):
        generated = datetime.now(timezone(timedelta(hours=8)))
    context['credit_timestamp'] = generated.strftime('%Y-%m-%d·%H:%M')
    context['core_text'] = '未知' if context.get('core') is None else 'MAX' if context['core'] >= 7 else f"+{context['core']}"
    context['card_width'] = CARD_WIDTH
    context.setdefault('bond', None)
    import base64
    bond_path=Path(__file__).resolve().parents[2]/'assets/status/bond-heart.png'
    context['bond_icon_url']='data:image/png;base64,'+base64.b64encode(bond_path.read_bytes()).decode('ascii')
    for key in ('char_class', 'element', 'corporation'):
        value = context.get(key)
        context[key + '_label'] = _LABELS.get(value, value or '未知')
    context['burst_label'] = {1: 'Ⅰ', 2: 'Ⅱ', 3: 'Ⅲ', '1': 'Ⅰ', '2': 'Ⅱ', '3': 'Ⅲ'}.get(context.get('burst'), str(context.get('burst') or '未知'))
    context['aggregate'] = aggregate_options(context.get('gear', []))
    context['aggregate']['display_rows'] = summary_display(context['aggregate'])
    context['aggregate']['columns'] = 2 if len(context['aggregate']['display_rows']) > 3 else 1
    context['aggregate']['hidden_count'] = max(0, len(context['aggregate']['rows'])-6)
    context['collection_display'] = _equipment_info(context, 'collection', 'favorite', '收藏品')
    context['cube_display'] = _equipment_info(context, 'cube_info', 'cube', '魔方')
    context['commander_name'] = context.get('commander_name') or context.get('nickname') or '昵称未知'
    context['commander_uid'] = context.get('commander_uid') or context.get('uid') or '未知'
    context['commander_region'] = context.get('commander_region') or context.get('area_label') or '区服未知'
    if style == 'compact':
        import unicodedata
        title_em=sum(1 if unicodedata.east_asian_width(ch) in ('W','F') else .6 for ch in str(context.get('name') or ''))
        context['compact_name_font_size']=min(27,max(16,int(360/max(1,title_em))))
        from ..nikke_render.card_background import compact_geometry, compact_backdrop
        from ..nikke_resource.cache import PLACEHOLDER
        geometry = compact_geometry(len(context['aggregate']['rows']))
        context.update(compact_backdrop(context['card_theme'], geometry,context['glass_strength']))
        context['card_width'] = geometry.width
        use_current_icon = (context.get('portrait_fallback', False)
                            and not context.get('character_icon_fallback', False)
                            and not context.get('character_icon_missing', False)
                            and context.get('character_icon_url'))
        if context.get('portrait_url') and not context.get('portrait_missing', False) and not use_current_icon:
            context['compact_portrait_url'] = context['portrait_url']
            context['compact_image_kind'] = 'portraits'
        else:
            context['compact_portrait_url'] = context.get('character_icon_url') or PLACEHOLDER
            context['compact_image_kind'] = 'icons'
        context['portrait_style'] = portrait_placement(context['compact_portrait_url'], context['compact_image_kind'], 318, geometry.portrait_height-2)
    if style == 'wide':
        from ..nikke_render.card_background import wide_backdrop
        context.update(wide_backdrop(context['card_theme'], context['glass_strength'],
                                     background_name=context.get('wide_background_name')))
        context['card_width'] = layout.width
        # prepare_character already resolves reported costumes against this character.
        # Prefer selected-skin art when FULL is missing instead of unrelated base FULL.
        exact_full = not context.get('full_missing', True) and not context.get('full_fallback', False)
        context['wide_art_url'] = context.get('full_url') if exact_full else context.get('art_url')
        context['wide_art_kind'] = 'full' if exact_full else context.get('art_kind', 'icons')
        context['wide_art_notice'] = '' if exact_full else context.get('art_hint', '立绘暂不可用')
        context['wide_art_style'] = upper_body_placement(context['wide_art_url'], full_bounds=context.get('full_alpha_bounds') if exact_full else None, anchor_x=(context.get('wide_anchor') or {}).get('x') if (context.get('wide_anchor') or {}).get('matched') else None, anchor_y=(context.get('wide_anchor') or {}).get('y') if (context.get('wide_anchor') or {}).get('matched') else None, head_top=(context.get('wide_anchor') or {}).get('head_top') if (context.get('wide_anchor') or {}).get('matched') else None)
        count = len(context['aggregate']['display_rows'])
        visible_rows = max(3, count if count <= 3 else (count+1)//2)
        context['wide_row_height'] = min(28, max(18, 140//max(1,visible_rows))) if visible_rows > 5 else 28
        context['wide_tools_top'] = 350 + visible_rows*context['wide_row_height']
    from ..nikke_render.icon_effects import apply_icon_effects
    context = apply_icon_effects(context)
    from ..nikke_render.icon_effects import portrait_shadow
    if style == 'wide':
        context['art_shadow_url'],context['art_shadow_style'] = portrait_shadow(context['wide_art_url'],context['wide_art_style'],glow=context['card_theme']=='dark')
    elif style == 'compact':
        context['art_shadow_url'],context['art_shadow_style'] = portrait_shadow(context['compact_portrait_url'],context['portrait_style'])
    template = layout.template
    from ..nikke_render.fonts import apply_font_html
    return apply_font_html(_ENV.get_template(template).render(**context), embed=False)


_render_locks = {}


async def draw_character(context: dict, style: str | None = None, theme: str | None = None) -> bytes:
    """Reuse the exact bound-account PNG before theme selection or rendering."""
    import asyncio, hashlib, json
    from ..nikke_render.glass_settings import capture_glass
    context=capture_glass(context)
    identity=context.get('_cache_identity')
    if not identity:
        return await _draw_uncached(context,style,theme)
    from .cache import get_panel_cache
    from ..nikke_render.theme import character_presentation_mode
    from ..nikke_render.cache import content_context, style_version, resource_version
    from ..nikke_resource.service import get_resources
    try:
        resources = get_resources()
    except ImportError:
        resources = None  # Pure offline adapters can supply their own painter.
    stable=content_context(context)
    stable.update(render_version='alice-v1110-wide-translucency-1',
                  theme=theme,style=style,presentation_mode=character_presentation_mode(),
                  presentation=style_version())
    code=context['name_code']
    store=get_panel_cache()
    from ..nikke_resource.cache import read_metadata
    dependencies = read_metadata(store.path(identity,f'render-{code}.json')).get('dependencies')
    def image_key():
        return hashlib.sha256(json.dumps([stable, resource_version(resources, dependencies)],ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    async with _render_locks.setdefault((identity,code),asyncio.Lock()):
        cached=store.image(identity,code,image_key())
        if cached is not None: return cached
        before = resource_version(resources, dependencies)
        image=await _draw_uncached(context,style,theme)
        stamp=context.get('_snapshot_saved_at')
        dependencies = context.get('_prepared_dependencies', dependencies)
        prepared = context.get('_prepared_resources', before)
        if ((stamp is None or store.read(identity).get('saved_at') == stamp)
                and prepared == resource_version(resources, dependencies)):
            store.save_image(identity,code,image_key(),image,dependencies=dependencies)
        return image


async def _draw_uncached(context: dict, style: str | None = None, theme: str | None = None) -> bytes:
    from ..nikke_resource.service import get_resources
    from ..nikke_render.render import render_html
    resources = get_resources()
    from ..nikke_resource.cache import track_assets
    from ..nikke_render.layouts import resolve_character_layout
    from ..nikke_render.theme import resolve_character_presentation
    style,theme = resolve_character_presentation(style,theme)
    layout = resolve_character_layout(style)
    with track_assets() as paths:
        prepared = await resources.prepare_character(context, framing=True) if layout.key == 'wide' else await resources.prepare_character(context)
    from ..nikke_render.cache import resource_version
    context['_prepared_dependencies'] = sorted(paths)
    context['_prepared_resources'] = resource_version(resources, context['_prepared_dependencies'])
    from ..nikke_render.layouts import resolve_character_layout
    layout = resolve_character_layout(style)
    return await render_html(render_character_html(prepared, layout.key, theme), root_width=layout.width)
