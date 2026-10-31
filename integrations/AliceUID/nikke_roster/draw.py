"""Complete ten-column SI icon sheet, with strict full-height validation."""
from __future__ import annotations
import io
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme
from PIL import Image

WIDTH = 1400
COLUMNS = 10
ICON = 128
HEADER = 176
FOOTER = 32
ROW = 160
GAP = 8
MAX_PIXELS = 24_000_000
MAX_BYTES = 8 * 1024 * 1024
_env = Environment(loader=FileSystemLoader(str(Path(__file__).parent.parent / 'templates')),
                   autoescape=select_autoescape(['html']))


def expected_size(context):
    rows = (len(context['cards']) + COLUMNS - 1) // COLUMNS
    return WIDTH, HEADER + FOOTER + rows * ROW + max(0, rows - 1) * GAP


async def prepare_images(context, images):
    from ..nikke_resource.card_meta import prepare_card_icons, prepare_badges
    result = dict(context)
    result.update(await prepare_badges(images))
    cards = []
    # ImageCache has its own persistent public-request cooldown and two slots.
    # Resolve serially here: no 203-task request burst at first use.
    for item in context['cards']:
        card = dict(item)
        resolved = await images.resolved_source('icons', card['resource_id'], card['skin_index'])
        card.update(icon_source=resolved.source, actual_skin_index=resolved.skin_index,
            icon_fallback=resolved.fallback, icon_missing=resolved.missing,
            icon_hash=resolved.content_hash)
        card['icon_badge'] = '缺图' if resolved.missing else '基础' if resolved.fallback or not card.get('skin_mapped', True) else ''
        if resolved.missing:
            card['skin_notice'] = 'SI图标素材缺失'
        elif resolved.fallback:
            card['skin_notice'] = '当前皮肤SI缺失 · 展示基础图标'
        card.update(await prepare_card_icons(card, images))
        cards.append(card)
    result['cards'] = cards
    return result


def render_roster_html(context):
    width, height = expected_size(context)
    if width * height > MAX_PIXELS:
        raise ValueError('角色数量超出完整长图安全限制，未生成截断图片。')
    return _env.get_template('roster.html').render(**apply_theme(context, context.get("card_theme"), scene_width=width, scene_height=height), image_height=height)


def encode_complete(data, context):
    expected = expected_size(context)
    with Image.open(io.BytesIO(data)) as image:
        if image.size != expected or image.width * image.height > MAX_PIXELS:
            raise ValueError('渲染未返回完整尺寸，已拒绝发送残图。')
        image = image.convert('RGB')
        for quality in (90, 85, 78, 70):
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True, subsampling=0)
            if len(output.getvalue()) <= MAX_BYTES:
                return output.getvalue()
    raise ValueError('完整图片超过8MiB安全限制，未发送截断图片。')


async def draw_roster(context):
    from ..nikke_render.render import render_html
    data = await render_html(render_roster_html(context), root_width=WIDTH, dpi=96)
    return encode_complete(data, context)
