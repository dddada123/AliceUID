"""Persistent public image cache; no player credentials are accepted here.

Keys are (kind, resource_id, skin_index). Images and sidecars are atomically
replaced, stale good files survive outages, and failed requests have a persisted
cooldown. Embedded data URIs also work with remote HTML renderers.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import base64
import hashlib
import io
import json
import logging
import math
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from ..nikke_api.resource import RESOURCE_TYPES, character_resource_url, validate_resource_key, obfuscate_path

PUBLIC_ICON_TYPES = {
    'equipment': ('equipment/icons', '/icon/equip/'),
    'skills': ('skills/icons', '/icon/skill/char_skill/'),
    'favorites': ('collections/icons', '/icon/favoriteitem/'),
    'cubes': ('cubes/icons', '/icon/equip/'),
    'attributes': ('rolemeta/icons', '/icon/atlas_common_class/'),
    'corporations': ('corporations', '/icon/atlas_common_corp/'),
}

log = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
PLACEHOLDER_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
                   '<rect width="256" height="256" rx="20" fill="#e8e3f4"/>'
                   '<circle cx="128" cy="86" r="36" fill="#b6accb"/>'
                   '<path d="M52 232v-28a76 76 0 0 1 152 0v28" fill="#b6accb"/>'
                   '</svg>')
PLACEHOLDER = 'data:image/svg+xml;base64,' + base64.b64encode(PLACEHOLDER_SVG.encode()).decode()


@asynccontextmanager
async def public_stream(http, url: str, headers=None):
    safe_headers = {key: value for key, value in (headers or {}).items()
                    if key.lower() in {'user-agent', 'referer', 'if-none-match', 'if-modified-since', 'accept'}}
    if callable(getattr(http, 'build_request', None)) and callable(getattr(http, 'send', None)):
        request = http.build_request('GET', url, headers=safe_headers)
        for name in ('cookie', 'authorization', 'proxy-authorization'):
            request.headers.pop(name, None)
        response = await http.send(request, stream=True, auth=None, follow_redirects=False)
        try:
            yield response
        finally:
            await response.aclose()
    else:
        # The database adapter enforces its own pacing/byte budgets and strips credentials.
        async with http.stream('GET', url, headers=safe_headers) as response:
            yield response


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_metadata(path: Path) -> dict:
    try:
        meta = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(meta, dict):
        return {}
    for field in ('checked_at', 'retry_after'):
        try:
            value = float(meta.get(field, 0))
            meta[field] = value if math.isfinite(value) and value >= 0 else 0
        except (TypeError, ValueError, OverflowError):
            meta[field] = 0
    etag = meta.get('etag')
    if not isinstance(etag, str) or len(etag) > 1024 or '\r' in etag or '\n' in etag:
        meta.pop('etag', None)
    return meta


def validate_image(data: bytes) -> None:
    if not data or len(data) > MAX_BYTES:
        raise ValueError('image byte limit')
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > MAX_PIXELS:
            raise ValueError('image format or pixel limit')
        image.verify()


def normalize_png(data: bytes) -> bytes:
    """Keep cache .png names truthful even when the CDN negotiates WebP/JPEG."""
    validate_image(data)
    with Image.open(io.BytesIO(data)) as image:
        if image.format == 'PNG':
            return data
        output = io.BytesIO()
        image.convert('RGBA').save(output, format='PNG', optimize=True)
    normalized = output.getvalue()
    validate_image(normalized)
    return normalized


def image_data_uri(data: bytes, size: tuple[int, int] = (600, 900), *, trim_alpha=False) -> str:
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert('RGBA')
        if trim_alpha:
            box = image.getchannel('A').getbbox()
            if box:
                image = image.crop(box)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.convert('RGBA').save(output, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


@dataclass(frozen=True)
class ResolvedImage:
    source: str
    requested_skin_index: int
    skin_index: int | None
    fallback: bool
    missing: bool
    content_hash: str | None


class ImageCache:
    def __init__(self, root: Path, *, ttl: int = 7 * 86400, cooldown: int = 1800,
                 http: httpx.AsyncClient | None = None, clock=time.time):
        self.root = Path(root)
        self.ttl = max(3600, int(ttl))
        self.cooldown = max(60, int(cooldown))
        self.http = http
        self.clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._base_retry_after = 0
        self._base_request_time = None
        self._base_gate = asyncio.Lock()
        self._slots = asyncio.Semaphore(2)
        for resource_type in RESOURCE_TYPES.values():
            (self.root / resource_type.directory).mkdir(parents=True, exist_ok=True)
        for directory, _ in PUBLIC_ICON_TYPES.values():
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def _path(self, kind: str, resource_id: int, skin_index: int) -> Path:
        if not isinstance(kind, str) or kind not in RESOURCE_TYPES:
            raise ValueError('unsupported resource kind')
        resource_id, skin_index = validate_resource_key(resource_id, skin_index)
        return self.root / RESOURCE_TYPES[kind].directory / f'c{resource_id:03d}_{skin_index:02d}.png'

    async def get(self, kind: str, resource_id: int, skin_index: int = 0, *, refresh: bool = False) -> bytes | None:
        try:
            resource_id, skin_index = validate_resource_key(resource_id, skin_index)
            path = self._path(kind, resource_id, skin_index)
        except (TypeError, ValueError):
            return None
        return await self._get_cached(path, character_resource_url(kind, resource_id, skin_index),
                                      kind, resource_id, refresh=refresh)

    def local_base_icon(self, kind: str, key: str) -> bytes | None:
        """Read only a fixed catalogue entry with matching source and digest."""
        from .base_icons import base_icon_spec
        spec = base_icon_spec(kind, key)
        if spec is None:
            return None
        path = self.root / spec.directory / (spec.key + '.png')
        meta = read_metadata(path.with_suffix('.json'))
        try:
            data = path.read_bytes()
            if meta.get('url') != spec.url or meta.get('sha256') != hashlib.sha256(data).hexdigest():
                return None
            return normalize_png(data)
        except (OSError, ValueError, Image.DecompressionBombError):
            return None

    async def _pace_base_http(self):
        # Database adapters already apply the same interval across JSON and PNG.
        if getattr(self.http, 'public_resource_paced', False):
            return
        async with self._base_gate:
            if self._base_request_time is not None:
                delay = max(0, 2.0 - (time.monotonic() - self._base_request_time))
                await asyncio.sleep(delay)
            self._base_request_time = time.monotonic()

    def base_icon_retry_after(self) -> float:
        return max(self._base_retry_after,
                   read_metadata(self.root / 'rolemeta' / 'base-icons-cooldown.json').get('retry_after', 0))

    async def get_badge(self, key: str, *, refresh: bool = False) -> bytes | None:
        from .badges import load_badge
        return await load_badge(self, key, refresh=refresh)

    async def get_base_icon(self, kind: str, key: str) -> bytes | None:
        from .base_icons import base_icon_spec
        spec = base_icon_spec(kind, key)
        if spec is None:
            return None
        local = self.local_base_icon(kind, key)
        if local is not None:
            return local
        if self.clock() < self.base_icon_retry_after():
            return None
        path = self.root / spec.directory / (spec.key + '.png')
        return await self._get_cached(path, spec.url, kind, spec.key, immutable=True)

    async def get_asset(self, kind: str, key: str, logical_path: str, *, refresh: bool = False) -> bytes | None:
        if kind == 'weapons':
            from .base_icons import base_icon_spec
            spec = base_icon_spec(kind, key)
            if spec is None or logical_path != spec.url:
                return None
            return await self.get_base_icon(kind, key)
        if not isinstance(kind, str) or kind not in PUBLIC_ICON_TYPES or isinstance(key, bool) or not isinstance(key, (str, int)):
            return None
        key = str(key)
        directory, prefix = PUBLIC_ICON_TYPES[kind]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', key):
            return None
        if not isinstance(logical_path, str) or not logical_path.startswith(prefix):
            return None
        filename = logical_path[len(prefix):]
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.png', filename):
            return None
        path = self.root / directory / f'{key}.png'
        return await self._get_cached(path, obfuscate_path(logical_path), kind, key, refresh=refresh)

    async def asset_source(self, kind: str, key: str, logical_path: str) -> str:
        data = await self.get_asset(kind, key, logical_path)
        return image_data_uri(data, (256, 256)) if data else PLACEHOLDER

    async def _get_cached(self, path: Path, url: str, kind: str, resource_id, *, refresh=False, immutable=False):
        key = str(path)
        async with self._locks.setdefault(key, asyncio.Lock()):
            meta_path = path.with_suffix('.json')
            meta = read_metadata(meta_path)
            cached = None
            try:
                raw = path.read_bytes()
                cached = normalize_png(raw)
                if immutable and (meta.get('url') != url or meta.get('sha256') != hashlib.sha256(raw).hexdigest()):
                    cached = None
            except (OSError, ValueError, Image.DecompressionBombError):
                cached = None
            if cached is not None:
                # Format repair is local: preserve freshness, ETag, URL and outage cooldown.
                digest = hashlib.sha256(cached).hexdigest()
                try:
                    if cached != raw:
                        atomic_write(path, cached)
                    if meta.get('sha256') != digest:
                        meta['sha256'] = digest
                        atomic_write(meta_path, json.dumps(meta, ensure_ascii=False).encode())
                except OSError:
                    log.warning('AliceUID could not persist local PNG repair kind=%s id=%s', kind, resource_id)
            now = self.clock()
            # A force refresh never overrides outage cooldown; avoids command-driven retry storms.
            source_matches = meta.get('url', url) == url
            if now < float(meta.get('retry_after', 0)) and meta.get('retry_url', meta.get('url', url)) == url:
                return cached if source_matches else None
            if cached and source_matches and not refresh and (immutable or 0 <= now - float(meta.get('checked_at', 0)) < self.ttl):
                return cached
            headers = {'User-Agent': 'AliceUID-resource-cache/0.3', 'Referer': 'https://www.blablalink.com/'}
            if cached and source_matches and meta.get('etag'):
                headers['If-None-Match'] = meta['etag']
            try:
                async with self._slots:
                    if immutable:
                        await self._pace_base_http()
                        if self.clock() < self.base_icon_retry_after():
                            return cached if source_matches else None
                    if self.http is not None:
                        data, etag = await self._download(self.http, url, headers, cached if source_matches else None)
                    else:
                        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as http:
                            data, etag = await self._download(http, url, headers, cached if source_matches else None)
                if data != cached:
                    atomic_write(path, data)
                meta = {'checked_at': now, 'etag': etag, 'sha256': hashlib.sha256(data).hexdigest(), 'url': url}
                atomic_write(meta_path, json.dumps(meta, ensure_ascii=False).encode())
                return data
            except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError) as exc:
                blocked_source = immutable and isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {403, 429}
                if blocked_source:
                    self._base_retry_after = now + self.cooldown
                meta['retry_after'] = now + self.cooldown
                meta['retry_url'] = url
                try:
                    if blocked_source:
                        atomic_write(self.root / 'rolemeta' / 'base-icons-cooldown.json', json.dumps({
                            'retry_after': now + self.cooldown, 'status': exc.response.status_code, 'url': url}).encode())
                    atomic_write(meta_path, json.dumps(meta, ensure_ascii=False).encode())
                except OSError:
                    pass
                log.warning('AliceUID resource unavailable kind=%s id=%s error=%s', kind, resource_id, type(exc).__name__)
                return cached if source_matches else None

    @staticmethod
    async def _download(http, url, headers, cached):
        async with public_stream(http, url, headers) as response:
            if response.status_code == 304 and cached:
                return cached, response.headers.get('etag', headers.get('If-None-Match', ''))
            response.raise_for_status()
            if not response.headers.get('content-type', '').lower().startswith('image/'):
                raise ValueError('non-image response')
            chunks = bytearray()
            async for part in response.aiter_bytes():
                chunks.extend(part)
                if len(chunks) > MAX_BYTES:
                    raise ValueError('image exceeds byte limit')
            data = normalize_png(bytes(chunks))
            return data, response.headers.get('etag', '')

    async def resolved_source(self, kind: str, resource_id: int, skin_index: int = 0, *, refresh: bool = False) -> ResolvedImage:
        requested = skin_index
        try:
            resource_id, skin_index = validate_resource_key(resource_id, skin_index)
            self._path(kind, resource_id, skin_index)
        except (TypeError, ValueError):
            return ResolvedImage(PLACEHOLDER, requested, None, False, True, None)
        data = await self.get(kind, resource_id, skin_index, refresh=refresh)
        actual = skin_index if data else None
        # Fallback stays within kind. Hash describes original cached PNG bytes,
        # before thumbnailing/alpha trimming, just like the on-disk sidecar.
        if not data and skin_index:
            data = await self.get(kind, resource_id, 0, refresh=refresh)
            actual = 0 if data else None
        if not data:
            return ResolvedImage(PLACEHOLDER, skin_index, None, False, True, None)
        return ResolvedImage(
            image_data_uri(data, RESOURCE_TYPES[kind].embed_size, trim_alpha=kind == 'full'),
            skin_index, actual, actual != skin_index, False, hashlib.sha256(data).hexdigest(),
        )

    async def source(self, kind: str, resource_id: int, skin_index: int = 0, *, refresh: bool = False) -> str:
        return (await self.resolved_source(kind, resource_id, skin_index, refresh=refresh)).source

    async def refresh_cached(self) -> dict[str, int]:
        """Refresh only existing files, including full art; never enumerate a remote library."""
        result = {'checked': 0, 'available': 0}
        for kind, resource_type in RESOURCE_TYPES.items():
            for path in sorted((self.root / resource_type.directory).glob('c*_*.png')):
                try:
                    rid, skin = map(int, path.stem[1:].split('_'))
                except ValueError:
                    continue
                result['checked'] += 1
                if await self.get(kind, rid, skin, refresh=True):
                    result['available'] += 1
        return result
