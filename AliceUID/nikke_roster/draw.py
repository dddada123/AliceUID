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
    import asyncio,json,time
    from ..nikke_resource.card_meta import prepare_card_icons, prepare_badges
    from ..nikke_resource.display import display_assets
    from ..nikke_resource.identity_card import prepare_portrait
    from ..nikke_logs.store import event
    started=time.monotonic()
    result=dict(context)
    async with display_assets(images) as assets:
        result.update(await prepare_badges(assets))
        result.update(await prepare_portrait(assets,context.get('commander_mapping')))
        roles={}
        async def prepare(item):
            card=dict(item)
            resolved=await assets.resolved_source('icons',card['resource_id'],card['skin_index'])
            card.update(icon_source=resolved.source,actual_skin_index=resolved.skin_index,
                        icon_fallback=resolved.fallback,icon_missing=resolved.missing,icon_hash=resolved.content_hash)
            card['icon_badge']='缺图' if resolved.missing else '基础' if resolved.fallback or not card.get('skin_mapped',True) else ''
            if resolved.missing:card['skin_notice']='头像暂缺，后台补齐'
            elif resolved.fallback:card['skin_notice']='当前皮肤头像暂缺 · 展示基础图标'
            key=json.dumps(card.get('role_spec') or {},sort_keys=True)
            if key not in roles:
                roles[key]=asyncio.create_task(prepare_card_icons(card,assets))
            card.update(await roles[key])
            return card
        # Only two workers are live, including a cold install with hundreds of images.
        cards=list(context['cards']);output=[None]*len(cards);iterator=iter(enumerate(cards))
        async def worker():
            for index,item in iterator:
                output[index]=await prepare(item)
        workers=[asyncio.create_task(worker()) for _ in range(2)]
        try:
            await asyncio.gather(*workers)
        finally:
            for task in [*workers,*roles.values()]:
                if not task.done():task.cancel()
            await asyncio.gather(*workers,*roles.values(),return_exceptions=True)
        result['cards']=output
        missing=sum(c['icon_missing'] for c in output)
        result['_assets_partial']=bool(missing or getattr(assets,'unavailable',0) or (context.get('commander_mapping') and not result.get('commander_avatar_url')))
        if missing:result['preview_notice']=f'{missing}个头像暂缺，后台补齐后再次查询可更新'
        event('完整卡片','素材准备','OK',count=len(output),
              reason=f"local={getattr(assets,'hits',0)} missing={getattr(assets,'misses',0)} deferred={getattr(assets,'deferred',0)}",
              elapsed_ms=round((time.monotonic()-started)*1000))
    return result



def render_roster_html(context):
    width, height = expected_size(context)
    if width * height > MAX_PIXELS:
        raise ValueError('角色数量超出完整长图安全限制，未生成截断图片。')
    from .finish import joined_glass
    prepared=apply_theme(context,context.get("card_theme"),scene_width=width,scene_height=height)
    prepared["join_glass_url"]=joined_glass(prepared["card_theme"])
    return _env.get_template("roster.html").render(**prepared,image_height=height)


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
