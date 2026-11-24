"""Anonymous public Blablalink guide fetching, image downloading, and HTML-to-text/Takumi prep."""
from __future__ import annotations

import asyncio
import base64
from html import escape, unescape
from html.parser import HTMLParser
import io
import re
from urllib.parse import urlsplit

import httpx
from PIL import Image

from .registry import GuideAuthor

LIST_URL = 'https://api.blablalink.com/api/ugc/direct/standalonesite/Dynamics/GetUserPostList'
POST_DETAIL_URL = 'https://api.blablalink.com/api/ugc/direct/standalonesite/Dynamics/GetPost'
POST_URL = 'https://www.blablalink.com/post/detail?post_uuid='
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_LIST_BYTES = 4 * 1024 * 1024

_ALLOWED_HOSTS = {
    'sg-cdn.blablalink.com': ('/standalonesite/ugc/public/image/', '/cms/nrft/feeds/pic/'),
    'truth.bahamut.com.tw': ('/s01/',),
}


class GuideError(Exception):
    pass


class PostNotFoundError(GuideError):
    """Raised when a post is confirmed unavailable/deleted on Blablalink."""


def validate_image_url(value: str) -> str:
    parsed = urlsplit(str(value or '').strip())
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise GuideError('攻略图片来源异常。')
    prefixes = _ALLOWED_HOSTS.get(parsed.hostname or '')
    if not prefixes or not any(parsed.path.startswith(p) for p in prefixes):
        raise GuideError('攻略图片来源域名不受信任。')
    return value


def validate_image_bytes(data: bytes, *, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    if not data or len(data) > max_bytes:
        raise GuideError('攻略图片超出发送限制。')
    with Image.open(io.BytesIO(data)) as im:
        if (im.format not in ('JPEG', 'PNG', 'WEBP', 'GIF')
                or im.width < 16 or im.height < 16
                or im.width * im.height > 64_000_000):
            raise GuideError('攻略图片尺寸或格式异常。')
        im.verify()
    return data


def extract_image_urls(content_html: str) -> list[str]:
    urls: list[str] = []
    for raw in re.findall(r'<img\b[^>]*src=["\']([^"\']+)["\']', str(content_html or ''), re.I):
        url = unescape(raw).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def extract_lead_image_url(content_html: str, *, category: str = 'character') -> str | None:
    """Return the first valid static cover image URL if present."""
    urls = extract_image_urls(content_html)
    if not urls:
        return None
    first = urls[0]
    try:
        validate_image_url(first)
    except GuideError:
        return None
    if category == 'character':
        return first
    # For non-character posts, treat first image as lead only when it appears at the top.
    idx = str(content_html or '').lower().find('<img')
    prefix = re.sub(r'<[^>]+>', '', str(content_html or '')[:max(0, idx)]).strip()
    return first if len(prefix) <= 40 else None


async def fetch_author_posts(
    author: GuideAuthor,
    *,
    known_modified: dict[str, int] | None = None,
    full_backfill: bool = False,
    max_pages: int = 40,
    http=None,
) -> tuple[list[dict], bool]:
    """Fetch posts for an author anonymously; stops early on incremental sync when caught up."""
    headers = {
        'Origin': 'https://www.blablalink.com',
        'Referer': author.homepage_url,
        'x-language': 'zh-tw',
        'x-channel-type': '2',
    }
    collected: list[dict] = []
    seen_uuids: set[str] = set()
    seen_cursors: set[str] = set()
    cursor = ''
    reached_end = False

    async def _run(client: httpx.AsyncClient):
        nonlocal cursor, reached_end
        for _ in range(max_pages):
            body: dict = {
                'plate_id': 0,
                'order_by': 1,
                'limit': '10',
                'intl_openid': author.intl_openid,
                'page_type': 0,
            }
            if cursor:
                body['next_page_cursor'] = cursor
            resp = await client.post(LIST_URL, json=body)
            resp.raise_for_status()
            if len(resp.content) > MAX_LIST_BYTES:
                raise GuideError('作者帖子列表超出读取限制。')
            payload = resp.json()
            if payload.get('code') != 0:
                raise GuideError('作者主页暂不可用，请稍后再试。')
            data = payload.get('data') or {}
            rows = data.get('list')
            info = data.get('page_info') or {}
            if not isinstance(rows, list) or not isinstance(info, dict):
                raise GuideError('作者主页数据结构已变化。')

            page_all_known = bool(rows) and not full_backfill and known_modified is not None
            for row in rows:
                uid = str(row.get('post_uuid') or '').strip()
                if not re.fullmatch(r'\d{1,30}', uid) or uid in seen_uuids:
                    continue
                seen_uuids.add(uid)
                collected.append(row)
                if page_all_known:
                    mod = int(row.get('modified_on') or row.get('created_on') or 0)
                    if known_modified.get(uid) != mod:
                        page_all_known = False

            next_cursor = str(info.get('next_page_cursor') or '')
            if not rows or info.get('is_finish') or not next_cursor or next_cursor in seen_cursors:
                reached_end = True
                break
            if page_all_known:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            await asyncio.sleep(0.25)

    if http is not None:
        await _run(http)
    else:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False, headers=headers) as client:
            await _run(client)
    return collected, reached_end


async def fetch_post_detail(
    post_uuid: str,
    *,
    target_lang: str = 'zh',
    referer: str | None = None,
    http=None,
) -> dict | None:
    """Fetch post detail anonymously with Blablalink auto-translation (`zh` / `zh-TW`)."""
    lang_header = 'zh-TW' if target_lang == 'zh-TW' else 'zh'
    headers = {
        'Origin': 'https://www.blablalink.com',
        'Referer': referer or f'{POST_URL}{post_uuid}',
        'x-language': lang_header,
        'x-channel-type': '2',
    }
    body = {'post_uuid': str(post_uuid), 'browse_post': 2, 'original_content': 0}

    async def _run(client: httpx.AsyncClient):
        resp = await client.post(POST_DETAIL_URL, json=body, headers=headers)
        if resp.status_code in (404, 410):
            raise PostNotFoundError('攻略原帖不可访问或已下架。')
        resp.raise_for_status()
        payload = resp.json()
        if payload.get('code') != 0:
            return None
        data = payload.get('data')
        return data if isinstance(data, dict) and data.get('content') else None

    if http is not None:
        return await _run(http)
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers=headers) as client:
        return await _run(client)


async def download_image_bytes(
    url: str,
    *,
    referer: str = 'https://www.blablalink.com/',
    max_bytes: int = MAX_IMAGE_BYTES,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    clean_url = validate_image_url(url)

    async def _get(c: httpx.AsyncClient) -> bytes:
        async with c.stream('GET', clean_url, headers={'Referer': referer}) as resp:
            resp.raise_for_status()
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise GuideError('攻略图片体积超出限制。')
                chunks.append(chunk)
        return validate_image_bytes(b''.join(chunks), max_bytes=max_bytes)

    if client is not None:
        return await _get(client)
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as c:
        return await _get(c)


def _try_extract_gif_first_frame(buf: bytes) -> bytes | None:
    """Try decoding frame 0 from a partial GIF byte stream (appending ';' trailer)."""
    if not (buf.startswith(b'GIF87a') or buf.startswith(b'GIF89a')):
        return None
    candidate = buf if buf.endswith(b';') else (buf + b';')
    try:
        with Image.open(io.BytesIO(candidate)) as im:
            if im.width < 16 or im.height < 16 or im.width * im.height > 64_000_000:
                return None
            im.seek(0)
            im.load()
        return candidate
    except Exception:
        return None


async def download_image_for_guide(
    url: str,
    *,
    referer: str = 'https://www.blablalink.com/',
    timeout: float = 15.0,
    max_bytes: int = 20 * 1024 * 1024,
    gif_max_bytes: int = 4 * 1024 * 1024,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    """Download image with hard total timeout and early-stop GIF frame-0 extraction."""
    clean_url = validate_image_url(url)

    async def _get(c: httpx.AsyncClient) -> bytes:
        req_timeout = httpx.Timeout(timeout, connect=8.0, read=10.0)
        async with c.stream('GET', clean_url, headers={'Referer': referer}, timeout=req_timeout) as resp:
            resp.raise_for_status()
            ctype = (resp.headers.get('content-type') or '').lower()
            clen = resp.headers.get('content-length')
            is_gif_hint = 'gif' in ctype or clean_url.lower().endswith('.gif')
            if clen and clen.isdigit() and not is_gif_hint and int(clen) > max_bytes:
                raise GuideError('攻略图片体积超出限制。')

            chunks: list[bytes] = []
            size = 0
            is_gif = False
            next_probe = 64 * 1024

            async for chunk in resp.aiter_bytes():
                if not chunk:
                    continue
                chunks.append(chunk)
                size += len(chunk)
                if not is_gif and size >= 6:
                    head = chunks[0][:6] if len(chunks[0]) >= 6 else b''.join(chunks)[:6]
                    is_gif = head in (b'GIF87a', b'GIF89a')

                if is_gif:
                    # Probe first complete frame periodically; abort stream immediately once ready.
                    if size >= next_probe:
                        merged = b''.join(chunks)
                        if _try_extract_gif_first_frame(merged) is not None:
                            return merged
                        next_probe = size + 256 * 1024
                    if size >= gif_max_bytes:
                        merged = b''.join(chunks)
                        extracted = _try_extract_gif_first_frame(merged)
                        if extracted is not None:
                            return extracted
                        raise GuideError('GIF首帧超出读取限制。')
                elif size > max_bytes:
                    raise GuideError('攻略图片体积超出限制。')

            data = b''.join(chunks)
            if is_gif:
                extracted = _try_extract_gif_first_frame(data)
                if extracted is not None:
                    return extracted
            return validate_image_bytes(data, max_bytes=max_bytes)

    async def _run() -> bytes:
        if client is not None:
            return await _get(client)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as c:
            return await _get(c)

    return await asyncio.wait_for(_run(), timeout=timeout)


def encode_static_image(raw: bytes, *, max_width: int = 920, quality: int = 82) -> tuple[bytes, str]:
    """Convert PNG/JPEG/WEBP/GIF (frame 0) to compact static image bytes + mime type."""
    with Image.open(io.BytesIO(raw)) as im:
        has_alpha = 'A' in im.getbands() and im.convert('RGBA').getchannel('A').getextrema()[0] < 255
        if getattr(im, 'is_animated', False) or im.format == 'GIF':
            im.seek(0)
        frame = im.convert('RGBA' if has_alpha else 'RGB')
        if frame.width > max_width:
            new_h = max(1, round(frame.height * max_width / frame.width))
            frame = frame.resize((max_width, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if has_alpha:
            frame.save(buf, format='PNG')
            return buf.getvalue(), 'image/png'
        frame.save(buf, format='JPEG', quality=quality, subsampling=0)
        return buf.getvalue(), 'image/jpeg'


def bytes_to_data_uri(data: bytes, mime: str | None = None) -> str:
    if not mime:
        mime = 'image/png' if data.startswith(b'\x89PNG') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')


def to_static_data_uri(raw: bytes, *, max_width: int = 920) -> str:
    """Convert PNG/JPEG/WEBP/GIF (frame 0) to compact static PNG/JPEG data URI for pytakumi."""
    data, mime = encode_static_image(raw, max_width=max_width)
    return bytes_to_data_uri(data, mime)


class _PlainTextParser(HTMLParser):
    """Deterministic HTML-to-plaintext extractor marking 【镇楼图】 and 【图1】【图2】."""

    def __init__(self, *, has_lead_image: bool = False):
        super().__init__(convert_charrefs=True)
        self.has_lead_image = has_lead_image
        self.img_index = 0
        self.parts: list[str] = []
        self._skip_ql_ui = 0
        self._list_stack: list[tuple[str, int]] = []

    def _ensure_newline(self):
        if self.parts and not self.parts[-1].endswith('\n'):
            self.parts.append('\n')

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_map = dict(attrs)
        cls = attr_map.get('class', '')
        if self._skip_ql_ui > 0:
            self._skip_ql_ui += 1
            return
        if tag == 'span' and 'ql-ui' in cls:
            self._skip_ql_ui = 1
            return
        if tag == 'br':
            self.parts.append('\n')
        elif tag in ('ol', 'ul'):
            self._list_stack.append((tag, 0))
            self._ensure_newline()
        elif tag == 'li':
            self._ensure_newline()
            if attr_map.get('data-list') == 'bullet' or (self._list_stack and self._list_stack[-1][0] == 'ul'):
                self.parts.append('• ')
            elif self._list_stack:
                kind, count = self._list_stack[-1]
                count += 1
                self._list_stack[-1] = (kind, count)
                self.parts.append(f'{count}. ')
            else:
                self.parts.append('• ')
        elif tag in ('div', 'p', 'h1', 'h2', 'h3', 'h4', 'tr'):
            self._ensure_newline()
        elif tag == 'img':
            self._ensure_newline()
            self.img_index += 1
            if self.has_lead_image and self.img_index == 1:
                label = '【镇楼图】'
            else:
                num = self.img_index - (1 if self.has_lead_image else 0)
                label = f'【图{num}】'
            self.parts.append(f'{label}\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._skip_ql_ui > 0:
            self._skip_ql_ui -= 1
            return
        if tag in ('ol', 'ul') and self._list_stack:
            self._list_stack.pop()
            self._ensure_newline()
        elif tag in ('div', 'p', 'h1', 'h2', 'h3', 'h4', 'li', 'tr'):
            self._ensure_newline()

    def handle_data(self, data):
        if self._skip_ql_ui > 0:
            return
        text = data.replace('\xa0', ' ')
        if text:
            self.parts.append(text)


def html_to_plain_text(content_html: str, *, has_lead_image: bool = False) -> str:
    parser = _PlainTextParser(has_lead_image=has_lead_image)
    parser.feed(str(content_html or ''))
    parser.close()
    raw = ''.join(parser.parts)
    lines = [line.rstrip() for line in raw.splitlines()]
    cleaned = '\n'.join(lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def split_text_chunks(text: str, *, footer: str = '', limit: int = 2800) -> list[str]:
    """Split long plain text on paragraph/line boundaries so QQ forward nodes stay intact."""
    full = f'{text}\n\n{footer}'.strip() if footer else text.strip()
    if not full:
        return []
    if len(full) <= limit:
        return [full]
    chunks: list[str] = []
    current = ''
    for para in full.split('\n'):
        candidate = f'{current}\n{para}' if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
                current = ''
            while len(para) > limit:
                chunks.append(para[:limit])
                para = para[limit:]
            current = para
    if current.strip():
        chunks.append(current.strip())
    return chunks


class _TakumiHtmlSanitizer(HTMLParser):
    """Rewrite Blablalink Quill HTML into clean takumi-safe markup with local image data URIs."""

    _SAFE_STYLE_PROPS = {'color', 'background-color', 'font-weight', 'text-align'}

    def __init__(self, image_map: dict[str, str]):
        super().__init__(convert_charrefs=False)
        self.image_map = image_map
        self.parts: list[str] = []
        self._skip_ql_ui = 0
        self._list_stack: list[tuple[str, int]] = []

    def _clean_style(self, raw_style: str) -> str:
        kept = []
        for item in raw_style.split(';'):
            if ':' not in item:
                continue
            prop, val = item.split(':', 1)
            p = prop.strip().lower()
            v = val.strip()
            if p in self._SAFE_STYLE_PROPS and v and 'url(' not in v.lower():
                # Strip pure white background-color from Quill spans so dark/light paper stays clean
                if p == 'background-color' and v.replace(' ', '') in ('rgb(255,255,255)', '#ffffff', 'white'):
                    continue
                kept.append(f'{p}: {v}')
        return '; '.join(kept)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_map = dict(attrs)
        if self._skip_ql_ui > 0:
            self._skip_ql_ui += 1
            return
        if tag == 'span' and 'ql-ui' in attr_map.get('class', ''):
            self._skip_ql_ui = 1
            return
        if tag in ('script', 'style', 'iframe', 'video'):
            self._skip_ql_ui = 1
            return
        if tag == 'img':
            src = unescape(attr_map.get('src', '')).strip()
            resolved = self.image_map.get(src)
            if resolved:
                self.parts.append(f'<div class="post-img-wrap"><img class="post-img" src="{escape(resolved, quote=True)}" /></div>')
            else:
                self.parts.append('<div class="post-img-missing">[图片加载失败]</div>')
            return
        if tag in ('ol', 'ul'):
            self._list_stack.append((tag, 0))
            self.parts.append('<div class="post-list">')
            return
        if tag == 'li':
            is_bullet = attr_map.get('data-list') == 'bullet' or (self._list_stack and self._list_stack[-1][0] == 'ul')
            if is_bullet:
                prefix = '•'
            elif self._list_stack:
                kind, idx = self._list_stack[-1]
                idx += 1
                self._list_stack[-1] = (kind, idx)
                prefix = f'{idx}.'
            else:
                prefix = '•'
            self.parts.append(f'<div class="post-li"><span class="post-li-mark">{prefix}</span><div class="post-li-body">')
            return
        if tag == 'br':
            self.parts.append('<br />')
            return
        allowed_tags = {'div', 'p', 'span', 'strong', 'b', 'em', 'i', 'h1', 'h2', 'h3', 'h4', 'a', 'table', 'tbody', 'thead', 'tr', 'td', 'th'}
        if tag not in allowed_tags:
            return
        style = self._clean_style(attr_map.get('style', ''))
        style_attr = f' style="{escape(style, quote=True)}"' if style else ''
        self.parts.append(f'<{tag}{style_attr}>')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._skip_ql_ui > 0:
            self._skip_ql_ui -= 1
            return
        if tag in ('ol', 'ul'):
            if self._list_stack:
                self._list_stack.pop()
            self.parts.append('</div>')
        elif tag == 'li':
            self.parts.append('</div></div>')
        elif tag in {'div', 'p', 'span', 'strong', 'b', 'em', 'i', 'h1', 'h2', 'h3', 'h4', 'a', 'table', 'tbody', 'thead', 'tr', 'td', 'th'}:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if self._skip_ql_ui > 0:
            return
        self.parts.append(escape(data, quote=False))

    def handle_entityref(self, name):
        if self._skip_ql_ui <= 0:
            self.parts.append(f'&{name};')

    def handle_charref(self, name):
        if self._skip_ql_ui <= 0:
            self.parts.append(f'&#{name};')


def sanitize_html_for_takumi(content_html: str, image_map: dict[str, str]) -> str:
    parser = _TakumiHtmlSanitizer(image_map)
    parser.feed(str(content_html or ''))
    parser.close()
    html = ''.join(parser.parts)
    try:
        from gsuid_core.utils.html_render.table_rewrite import rewrite_tables_for_takumi
        if '<table' in html.lower():
            html = rewrite_tables_for_takumi(html)
    except Exception:
        pass
    return html
