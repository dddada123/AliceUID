"""Verified public badge downloads with restart-safe cache and bundled fallback."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import httpx
from PIL import Image
from .base_icons import STATIC_BADGES
from .cache import atomic_write, read_metadata, validate_image, image_data_uri

FIXED_BADGE_URLS = frozenset(item['url'] for item in STATIC_BADGES.values())
FALLBACK_ORIGIN = 'reviewed_official_bundled_fallback'

def badge_path(images, key):
    return (images.root / 'rolemeta/power/team_combat.png' if key == 'power'
            else images.root / 'rolemeta/breakthrough' / (key + '.png'))

def local_badge(images, key, *, allow_fallback=False):
    spec = STATIC_BADGES.get(key) if isinstance(key, str) else None
    if spec is None:
        return None
    path = badge_path(images, key)
    meta = read_metadata(path.with_suffix('.json'))
    try:
        raw = path.read_bytes()
        validate_image(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if (digest != spec['sha256'] or meta.get('sha256') != digest or meta.get('url') != spec['url']
                or (not allow_fallback and meta.get('origin') == FALLBACK_ORIGIN)):
            return None
        return raw
    except (OSError, ValueError, Image.DecompressionBombError):
        return None

async def load_badge(images, key, *, refresh=False):
    spec = STATIC_BADGES.get(key) if isinstance(key, str) else None
    if spec is None:
        return None
    path = badge_path(images, key)
    from .cache import record_asset
    record_asset(path)
    async with images._locks.setdefault(str(path), asyncio.Lock()):
        meta_path = path.with_suffix('.json')
        meta = read_metadata(meta_path)
        cached = local_badge(images, key, allow_fallback=True)
        now = images.clock()
        good = cached is not None and meta.get('origin') != FALLBACK_ORIGIN
        if good and not refresh:
            # Hashed filenames are immutable. The stable core URL is revalidated
            # weekly; importing an audited legacy sidecar starts its local TTL.
            if key != 'core':
                return cached
            if not meta.get('checked_at'):
                meta['checked_at'] = now
                try:
                    atomic_write(meta_path, json.dumps(meta).encode())
                except OSError:
                    pass
                return cached
            if 0 <= now - meta['checked_at'] < images.ttl:
                return cached
        retry = max(meta.get('retry_after', 0) if meta.get('retry_url', spec['url']) == spec['url'] else 0,
                    images.base_icon_retry_after())
        if now >= retry:
            try:
                async with images._slots:
                    await images._pace_base_http()
                    if images.clock() < images.base_icon_retry_after():
                        retry = images.base_icon_retry_after()
                    else:
                        headers = {'User-Agent': 'AliceUID-resource-cache/1.0.02', 'Referer': 'https://www.blablalink.com/'}
                        if good and meta.get('etag'):
                            headers['If-None-Match'] = meta['etag']
                        if images.http is not None:
                            data, etag = await images._download(images.http, spec['url'], headers, cached if good else None)
                        else:
                            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as http:
                                data, etag = await images._download(http, spec['url'], headers, cached if good else None)
                        digest = hashlib.sha256(data).hexdigest()
                        if digest != spec['sha256']:
                            raise ValueError('public badge digest differs from reviewed source')
                        result = {'url': spec['url'], 'sha256': digest, 'source_sha256': digest,
                                  'etag': etag, 'checked_at': now, 'origin': 'community_download',
                                  'registry_version': 'badges-v102-1', 'contains_value': False}
                        atomic_write(path, data)
                        atomic_write(meta_path, json.dumps(result).encode())
                        return data
            except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError) as exc:
                retry = now + images.cooldown
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {403, 429}:
                    images._base_retry_after = retry
                    try:
                        atomic_write(images.root / 'rolemeta/base-icons-cooldown.json', json.dumps({
                            'retry_after': retry, 'status': exc.response.status_code, 'url': spec['url']}).encode())
                    except OSError:
                        pass
        retry = max(retry, now + images.cooldown) if retry <= now else retry
        data = cached or base64.b64decode(spec['base64'], validate=True)
        if hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise ValueError('bundled badge digest mismatch')
        result = dict(meta if good else {}, url=spec['url'], sha256=spec['sha256'], source_sha256=spec['sha256'],
                      origin=meta.get('origin', 'community_download') if good else FALLBACK_ORIGIN,
                      registry_version='badges-v102-1', retry_url=spec['url'], retry_after=retry, contains_value=False)
        try:
            if data != cached:
                atomic_write(path, data)
            atomic_write(meta_path, json.dumps(result).encode())
        except OSError:
            pass
        return data

async def badge_sources(images, keys=('star_active', 'star_inactive', 'core')):
    result, hashes = {}, {}
    for key in keys:
        # Real ImageCache always implements get_badge; light test adapters can use the audited fallback.
        load = getattr(images, 'get_badge', None)
        raw = await load(key) if callable(load) else base64.b64decode(STATIC_BADGES[key]['base64'])
        if raw:
            result[key] = image_data_uri(raw, (128, 128))
            hashes[key] = hashlib.sha256(raw).hexdigest()
    return result, hashes
