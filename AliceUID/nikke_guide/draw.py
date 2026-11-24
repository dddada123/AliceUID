"""Render Blablalink guide posts into compact long JPEG images via GsCore pytakumi."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import io
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from ..nikke_render.fonts import apply_font_html
from ..nikke_render.language import get_card_language, localize_html
from ..nikke_render.theme import get_card_theme, v2_theme_tokens
from ..nikke_resource.media import media_path
from .source import (
    MAX_IMAGE_BYTES,
    POST_URL,
    download_image_bytes,
    extract_image_urls,
    sanitize_html_for_takumi,
    to_static_data_uri,
)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates'
_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml']),
)
_BJ_TZ = timezone(timedelta(hours=8))


def _format_published(ts_raw) -> str:
    try:
        ts = int(ts_raw or 0)
        if ts <= 0:
            return ''
        return datetime.fromtimestamp(ts, _BJ_TZ).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ''


async def _fetch_post_images(
    urls: list[str],
    *,
    referer: str,
    http: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Download all embedded post images with bounded concurrency and convert to static data URIs."""
    if not urls:
        return {}
    sem = asyncio.Semaphore(4)
    result: dict[str, str] = {}

    async def _one(client: httpx.AsyncClient, url: str):
        async with sem:
            try:
                raw = await download_image_bytes(url, referer=referer, max_bytes=32 * 1024 * 1024, client=client)
                result[url] = to_static_data_uri(raw, max_width=940)
            except Exception:
                pass

    if http is not None:
        await asyncio.gather(*(_one(http, u) for u in urls))
    else:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            await asyncio.gather(*(_one(client, u) for u in urls))
    return result


def _ensure_jpeg_under_limit(data: bytes, *, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    """Guarantee output is a valid JPEG <= max_bytes (stepping down quality if needed)."""
    with Image.open(io.BytesIO(data)) as im:
        if im.format == 'JPEG' and len(data) <= max_bytes:
            im.verify()
            return data
        rgb = im.convert('RGB')
        for q in (95, 90, 85, 78, 70):
            buf = io.BytesIO()
            rgb.save(buf, format='JPEG', quality=q, subsampling=0, optimize=True)
            out = buf.getvalue()
            if len(out) <= max_bytes:
                return out
        # Extreme fallback: scale width slightly if still > 8MB
        scale = (max_bytes / max(1, len(out))) ** 0.5 * 0.9
        resized = rgb.resize(
            (max(320, int(rgb.width * scale)), max(320, int(rgb.height * scale))),
            Image.Resampling.LANCZOS,
        )
        buf = io.BytesIO()
        resized.save(buf, format='JPEG', quality=75, subsampling=0, optimize=True)
        return buf.getvalue()


@lru_cache(maxsize=1)
def _alice_icon_uri() -> str:
    for p in (media_path('assets/ICON.png'), Path(__file__).resolve().parents[2] / 'ICON.png'):
        if p.is_file():
            try:
                return 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
            except OSError:
                pass
    return ''


def _qr_data_uri(url: str) -> str:
    if not url:
        return ''
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#111827', back_color='#ffffff').convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


def render_guide_html(
    *,
    title: str,
    body_html: str,
    author_name: str,
    category_label: str,
    post_url: str,
    published_on: int | str = 0,
    theme: str | None = None,
    language: str | None = None,
    translated_from: str | None = None,
) -> str:
    resolved_theme = get_card_theme(theme, default='light')
    resolved_lang = language or get_card_language()
    ctx = {
        'title': title,
        'body_html': body_html,
        'author_name': author_name,
        'category_label': category_label,
        'post_url': post_url,
        'hero_art': _alice_icon_uri(),
        'qr_uri': _qr_data_uri(post_url),
        'published_text': _format_published(published_on),
        'card_theme': resolved_theme,
        'palette': v2_theme_tokens(None, resolved_theme)['palette'],
        'html_lang': resolved_lang,
        'translated_from': translated_from,
        'font_family': 'MiSans',
        'credit_timestamp': datetime.now(_BJ_TZ).strftime('%Y-%m-%d·%H:%M'),
    }
    raw_html = _ENV.get_template('guide_post.html').render(**ctx)
    localized = localize_html(raw_html, language=resolved_lang)
    return apply_font_html(localized, embed=False)


async def render_post_long_image(
    post: dict,
    *,
    author_name: str,
    category_label: str = '攻略',
    post_url: str | None = None,
    quality: int = 95,
    theme: str | None = None,
    language: str | None = None,
    translated_from: str | None = None,
    http: httpx.AsyncClient | None = None,
    image_map: dict[str, str] | None = None,
) -> bytes:
    """Render a Blablalink post dict into a JPEG long image via GsCore pytakumi."""
    uid = str(post.get('post_uuid') or '').strip()
    url = post_url or (f'{POST_URL}{uid}' if uid else 'https://www.blablalink.com/')
    content_html = str(post.get('content') or '')
    if image_map is None:
        img_urls = extract_image_urls(content_html)
        image_map = await _fetch_post_images(img_urls, referer=url, http=http)
    body_html = sanitize_html_for_takumi(content_html, image_map)
    html = render_guide_html(
        title=str(post.get('title') or ''),
        body_html=body_html,
        author_name=author_name,
        category_label=category_label,
        post_url=url,
        published_on=post.get('created_on') or 0,
        theme=theme,
        language=language,
        translated_from=translated_from,
    )
    from ..nikke_render.render import render_html
    q = quality if type(quality) is int and 0 <= quality <= 100 else 95
    raw_bytes = await render_html(
        html,
        root_width=1040,
        dpi=96,
        image_format='jpeg',
        jpeg_quality=q,
    )
    return _ensure_jpeg_under_limit(raw_bytes)
