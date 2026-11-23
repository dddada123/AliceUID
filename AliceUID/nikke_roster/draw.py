"""Ten/eight/seven-column SI icon sheet, with strict full-height validation."""
from __future__ import annotations

import base64
from functools import lru_cache
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageEnhance, ImageOps

from ..nikke_render.theme import apply_theme

WIDTH = 1400
COLUMNS = 10
ICON = 128
HEADER = 176
FOOTER = 32
ROW = 160
GAP = 8
PADDING_X = 24
TRANSITION_HEIGHT = 52
MAX_PIXELS = 24_000_000
MAX_BYTES = 8 * 1024 * 1024
_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent.parent / 'templates')),
    autoescape=select_autoescape(['html']),
)


@lru_cache(maxsize=256)
def _to_grayscale_uri(source: str) -> str:
    if not isinstance(source, str) or not source.startswith('data:image/') or ';base64,' not in source:
        return source
    try:
        raw = base64.b64decode(source.split(';base64,', 1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as original:
            rgba = original.convert('RGBA')
            alpha = rgba.getchannel('A')
            gray = ImageOps.grayscale(rgba.convert('RGB'))
            gray = ImageEnhance.Brightness(gray).enhance(0.84)
            out_img = Image.merge('RGBA', (gray, gray, gray, alpha))
            buf = io.BytesIO()
            out_img.save(buf, format='PNG', optimize=True)
            return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except (ValueError, OSError, TypeError):
        return source


def grid_columns(context: dict) -> int:
    cols = context.get('columns') or COLUMNS
    return int(cols) if isinstance(cols, int) and cols > 0 else COLUMNS


def expected_size(context):
    cols = grid_columns(context)
    width = cols * ICON + (cols - 1) * GAP + PADDING_X * 2
    owned_rows = max(1, (len(context.get('cards') or []) + cols - 1) // cols)
    owned_h = owned_rows * ROW + max(0, owned_rows - 1) * GAP
    unowned_count = len(context.get('unowned_cards') or [])
    if unowned_count:
        unowned_rows = (unowned_count + cols - 1) // cols
        unowned_h = TRANSITION_HEIGHT + unowned_rows * ROW + max(0, unowned_rows - 1) * GAP
    else:
        unowned_h = 0
    return width, HEADER + FOOTER + owned_h + unowned_h


def _build_unowned_rows(unowned_cards: list[dict], cols: int) -> list[list[dict | None]]:
    if not unowned_cards:
        return []
    rows: list[list[dict | None]] = []
    for start in range(0, len(unowned_cards), cols):
        chunk = list(reversed(unowned_cards[start:start + cols]))
        if len(chunk) < cols:
            chunk = [None] * (cols - len(chunk)) + chunk
        rows.append(chunk)
    return rows


async def prepare_images(context, images):
    import asyncio
    import json
    import time

    from ..nikke_logs.store import event
    from ..nikke_resource.card_meta import prepare_badges, prepare_card_icons
    from ..nikke_resource.display import display_assets
    from ..nikke_resource.identity_card import prepare_portrait

    started = time.monotonic()
    result = dict(context)
    async with display_assets(images) as assets:
        result.update(await prepare_badges(assets))
        result.update(await prepare_portrait(assets, context.get('commander_mapping')))
        roles = {}

        async def prepare(item, *, grayscale: bool = False):
            card = dict(item)
            resolved = await assets.resolved_source('icons', card['resource_id'], card['skin_index'])
            src = _to_grayscale_uri(resolved.source) if (grayscale and not resolved.missing) else resolved.source
            card.update(
                icon_source=src,
                actual_skin_index=resolved.skin_index,
                icon_fallback=resolved.fallback,
                icon_missing=resolved.missing,
                icon_hash=resolved.content_hash,
            )
            card['icon_badge'] = (
                '缺图'
                if resolved.missing
                else '基础'
                if (not grayscale and (resolved.fallback or not card.get('skin_mapped', True)))
                else ''
            )
            if resolved.missing:
                card['skin_notice'] = '头像暂缺，后台补齐'
            elif grayscale:
                card['skin_notice'] = '未解锁妮姬'
            elif resolved.fallback:
                card['skin_notice'] = '当前皮肤头像暂缺 · 展示基础图标'
            key = json.dumps(card.get('role_spec') or {}, sort_keys=True)
            if key not in roles:
                roles[key] = asyncio.create_task(prepare_card_icons(card, assets))
            card.update(await roles[key])
            return card

        async def run_batch(items, *, grayscale: bool = False):
            items_list = list(items)
            output = [None] * len(items_list)
            iterator = iter(enumerate(items_list))

            async def worker():
                for index, item in iterator:
                    output[index] = await prepare(item, grayscale=grayscale)

            workers = [asyncio.create_task(worker()) for _ in range(2)]
            try:
                await asyncio.gather(*workers)
            finally:
                for task in workers:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
            return output

        try:
            result['cards'] = await run_batch(context.get('cards') or [], grayscale=False)
            result['unowned_cards'] = await run_batch(context.get('unowned_cards') or [], grayscale=True)
        finally:
            for task in roles.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*roles.values(), return_exceptions=True)

        all_cards = [*result['cards'], *result['unowned_cards']]
        missing = sum(c['icon_missing'] for c in all_cards)
        result['_assets_partial'] = bool(
            missing
            or getattr(assets, 'unavailable', 0)
            or (context.get('commander_mapping') and not result.get('commander_avatar_url'))
        )
        if missing:
            result['preview_notice'] = f'{missing}个头像暂缺，后台补齐后再次查询可更新'
        event(
            '完整卡片',
            '素材准备',
            'OK',
            count=len(all_cards),
            reason=f"local={getattr(assets, 'hits', 0)} missing={getattr(assets, 'misses', 0)} deferred={getattr(assets, 'deferred', 0)}",
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
    return result


def render_roster_html(context):
    from datetime import datetime, timedelta, timezone

    from ..nikke_render.fonts import apply_font_html
    from ..nikke_render.theme import v2_theme_tokens
    from .finish import joined_glass

    cols = grid_columns(context)
    width, height = expected_size(context)
    if width * height > MAX_PIXELS:
        raise ValueError('角色数量超出完整长图安全限制，未生成截断图片。')
    grid_width = cols * ICON + (cols - 1) * GAP
    prepared = apply_theme(context, context.get('card_theme'), scene_width=width, scene_height=height)
    prepared.update(v2_theme_tokens(None, prepared['card_theme']))
    prepared['font_family'] = 'MiSans'
    prepared['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')
    prepared['join_glass_url'] = joined_glass(prepared['card_theme'])
    prepared['page_width'] = width
    prepared['grid_width'] = grid_width
    prepared['columns'] = cols
    prepared['unowned_rows'] = _build_unowned_rows(list(prepared.get('unowned_cards') or []), cols)
    return apply_font_html(_env.get_template('roster.html').render(**prepared, image_height=height), embed=False)


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

    width, _ = expected_size(context)
    data = await render_html(render_roster_html(context), root_width=width, dpi=96)
    return encode_complete(data, context)
