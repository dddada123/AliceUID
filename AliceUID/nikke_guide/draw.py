"""Render Blablalink guide posts into compact long JPEG images via GsCore pytakumi."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import io
from pathlib import Path
import time

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
    NonRetryableImageError,
    RateLimitedImageError,
    bytes_to_data_uri,
    download_image_for_guide,
    encode_static_image,
    extract_image_urls,
    get_image_pacer,
    sanitize_html_for_takumi,
)

BATCH_IMAGE_TIMEOUT_SECONDS = 60.0

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


def _log_render_event(stage: str, result: str, **metrics):
    try:
        from ..nikke_logs.store import event
        event('攻略长图', stage, result, **metrics)
    except Exception:
        pass


def _url_cache_file(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha256(url.encode('utf-8')).hexdigest() + '.img')


async def _fetch_post_images(
    urls: list[str],
    *,
    referer: str,
    http: httpx.AsyncClient | None = None,
    image_cache_dir: Path | None = None,
    pacer=None,
) -> tuple[dict[str, str], list[str]]:
    """Download/reuse embedded post images via adaptive pacer, 1x retry, and 60s batch timeout."""
    if not urls:
        return {}, []
    t0 = time.monotonic()
    pacer = pacer or get_image_pacer()
    result: dict[str, str] = {}
    pending: list[str] = []
    if image_cache_dir is not None:
        image_cache_dir.mkdir(parents=True, exist_ok=True)
        for u in urls:
            p = _url_cache_file(image_cache_dir, u)
            if p.is_file():
                try:
                    raw = p.read_bytes()
                    if raw:
                        result[u] = bytes_to_data_uri(raw)
                        continue
                except OSError:
                    pass
            pending.append(u)
    else:
        pending = list(urls)

    total_bytes = 0
    retried_count = 0
    gif_early_count = 0
    congestion_count = 0
    fail_details: dict[str, str] = {}

    async def _one(client: httpx.AsyncClient, url: str):
        nonlocal total_bytes, retried_count, gif_early_count, congestion_count
        tail = url.rsplit('/', 1)[-1][:24]
        for attempt, img_timeout in enumerate((25.0, 20.0), 1):
            async with pacer.slot():
                try:
                    dl_res = await download_image_for_guide(
                        url,
                        referer=referer,
                        timeout=img_timeout,
                        client=client,
                    )
                    raw, early = dl_res if isinstance(dl_res, tuple) else (dl_res, False)
                    if early:
                        gif_early_count += 1
                    static_bytes, mime = await asyncio.to_thread(
                        encode_static_image, raw, max_width=920, quality=82
                    )
                    total_bytes += len(raw)
                    if image_cache_dir is not None:
                        try:
                            from ..nikke_resource.cache import atomic_write
                            atomic_write(_url_cache_file(image_cache_dir, url), static_bytes)
                        except Exception:
                            pass
                    result[url] = bytes_to_data_uri(static_bytes, mime)
                    pacer.record_success()
                    fail_details.pop(url, None)
                    return
                except NonRetryableImageError as exc:
                    fail_details[url] = f'{tail}:{exc}'
                    return
                except RateLimitedImageError as exc:
                    pacer.record_throttle()
                    fail_details[url] = f'{tail}:{exc}'
                    if attempt == 2:
                        return
                except Exception as exc:
                    congestion_count += 1
                    if congestion_count >= 2:
                        pacer.record_congestion()
                    fail_details[url] = f'{tail}:{type(exc).__name__}'
                    if attempt == 2:
                        return
            retried_count += 1
            await asyncio.sleep(0.5)

    if pending:
        async def _batch():
            if http is not None:
                await asyncio.gather(*(_one(http, u) for u in pending))
            else:
                limits = httpx.Limits(max_connections=10, max_keepalive_connections=6)
                async with httpx.AsyncClient(timeout=25.0, limits=limits, follow_redirects=False) as client:
                    await asyncio.gather(*(_one(client, u) for u in pending))

        try:
            await asyncio.wait_for(_batch(), timeout=BATCH_IMAGE_TIMEOUT_SECONDS)
        except TimeoutError:
            pass

    failed_urls = [u for u in urls if u not in result]
    err_summary = ','.join(fail_details[u] for u in failed_urls[:4] if u in fail_details)
    _log_render_event(
        'FETCH_IMAGES',
        'PARTIAL' if failed_urls else 'OK',
        count=len(result),
        bytes=total_bytes,
        elapsed_ms=int((time.monotonic() - t0) * 1000),
        reason=(
            f'total={len(urls)},failed={len(failed_urls)},cached={len(urls)-len(pending)},'
            f'conc={pacer.max_concurrency},retried={retried_count},gif_early={gif_early_count}'
            + (f',errs={err_summary}' if err_summary else '')
        ),
    )
    return result, failed_urls


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
    # Localize lightweight title/author/template labels BEFORE inlining multi-MB image data URIs.
    loc_title = localize_html(title, language=resolved_lang)
    loc_author = localize_html(author_name, language=resolved_lang)
    loc_cat = localize_html(category_label, language=resolved_lang)
    ctx = {
        'title': loc_title,
        'body_html': body_html,
        'author_name': loc_author,
        'category_label': loc_cat,
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
    return apply_font_html(raw_html, embed=False, skip_localize=True)


async def render_post_long_image_with_meta(
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
    image_cache_dir: Path | None = None,
) -> tuple[bytes, list[str]]:
    """Render a Blablalink post dict into JPEG long image + failed image URL list."""
    uid = str(post.get('post_uuid') or '').strip()
    url = post_url or (f'{POST_URL}{uid}' if uid else 'https://www.blablalink.com/')
    resolved_lang = language or get_card_language()
    content_html = str(post.get('content') or '')
    failed_urls: list[str] = []
    if image_map is None:
        img_urls = extract_image_urls(content_html)
        image_map, failed_urls = await _fetch_post_images(
            img_urls,
            referer=url,
            http=http,
            image_cache_dir=image_cache_dir,
        )
    # Localize lightweight HTML markup once BEFORE embedding multi-MB base64 data URIs.
    localized_content = localize_html(content_html, language=resolved_lang)
    body_html = sanitize_html_for_takumi(localized_content, image_map)
    html = render_guide_html(
        title=str(post.get('title') or ''),
        body_html=body_html,
        author_name=author_name,
        category_label=category_label,
        post_url=url,
        published_on=post.get('created_on') or 0,
        theme=theme,
        language=resolved_lang,
        translated_from=translated_from,
    )
    from ..nikke_render.render import render_html
    q = quality if type(quality) is int and 0 <= quality <= 100 else 95
    t0 = time.monotonic()
    raw_bytes = await render_html(
        html,
        root_width=1040,
        dpi=96,
        image_format='jpeg',
        jpeg_quality=q,
        skip_localize=True,
        timeout=60.0,
    )
    out = await asyncio.to_thread(_ensure_jpeg_under_limit, raw_bytes)
    _log_render_event(
        'TAKUMI_RENDER',
        'OK',
        bytes=len(out),
        elapsed_ms=int((time.monotonic() - t0) * 1000),
        reason=f'html_len={len(html)}',
    )
    return out, failed_urls


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
    image_cache_dir: Path | None = None,
) -> bytes:
    out, _ = await render_post_long_image_with_meta(
        post,
        author_name=author_name,
        category_label=category_label,
        post_url=post_url,
        quality=quality,
        theme=theme,
        language=language,
        translated_from=translated_from,
        http=http,
        image_map=image_map,
        image_cache_dir=image_cache_dir,
    )
    return out
