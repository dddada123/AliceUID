"""Bounded card asset preparation: local pixels first, refresh off the paint path."""
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import time
import httpx
from .cache import (ImageCache, ResolvedImage, PLACEHOLDER, normalize_png,
                    read_metadata, image_data_uri, record_asset, track_assets)
from ..nikke_api.resource import character_resource_url, RESOURCE_TYPES, obfuscate_path


def pooled_cache(images, http):
    cache = ImageCache(images.root, cooldown=images.cooldown,
                       http=http, clock=images.clock)
    cache.ttl = images.ttl
    cache._locks, cache._slots = images._locks, images._slots
    cache._base_gate = images._base_gate
    return cache


class RefreshQueue:
    def __init__(self, images):
        self.images = images
        self.loop = asyncio.get_running_loop()
        self.jobs = asyncio.Queue(maxsize=512)
        self.pending = set()
        self.task = None

    def add(self, job):
        if job in self.pending or self.jobs.full():
            return
        self.pending.add(job)
        self.jobs.put_nowait(job)
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())
            self.task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    async def run(self):
        from ..nikke_logs.store import event
        count, started = 0, time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=6, trust_env=False, follow_redirects=False) as http:
                cache = pooled_cache(self.images, self.images.http or http)
                while not self.jobs.empty():
                    # One low-priority public request at a time; never hold up a card.
                    await asyncio.sleep(2)
                    job = self.jobs.get_nowait()
                    try:
                        with track_assets():
                            async with asyncio.timeout(8):
                                await getattr(cache, job[0])(*job[1:], refresh=True)
                        count += 1
                    except (TimeoutError, httpx.HTTPError, OSError, ValueError):
                        pass
                    finally:
                        self.pending.discard(job)
                        self.jobs.task_done()
        finally:
            event('头像素材', '后台检查', 'FINISHED', count=count,
                  elapsed_ms=round((time.monotonic()-started)*1000))


class DisplayAssets:
    def __init__(self, images, remote, *, budget=12):
        self.images, self.remote = images, remote
        self.root = images.root
        self.deadline = time.monotonic() + budget
        self.memo = {}
        self.hits = self.misses = self.deferred = self.unavailable = 0
        queue = getattr(images, '_display_refresh', None)
        if queue is None or queue.loop is not asyncio.get_running_loop():
            queue = images._display_refresh = RefreshQueue(images)
        self.refresh = queue

    def local(self, path, url):
        record_asset(path)
        meta = read_metadata(path.with_suffix('.json'))
        if meta.get('url', url) != url:
            return None, meta
        try:
            return normalize_png(path.read_bytes()), meta
        except (OSError, ValueError):
            return None, meta

    async def once(self, key, load):
        if key not in self.memo:
            self.memo[key] = asyncio.create_task(load())
        return await self.memo[key]

    async def read(self, path, url, job, *, immutable=False):
        async def load():
            raw, meta = self.local(path, url)
            if raw:
                self.hits += 1
                if not immutable and not 0 <= self.images.clock()-meta.get('checked_at', 0) < self.images.ttl:
                    self.refresh.add(job)
                return raw
            self.misses += 1
            remaining = self.deadline-time.monotonic()
            if remaining > 0:
                try:
                    async with asyncio.timeout(remaining):
                        fetched = await getattr(self.remote, job[0])(*job[1:])
                        if fetched:
                            return fetched
                except TimeoutError:
                    pass
            self.deferred += 1
            self.unavailable += 1
            self.refresh.add(job)
            return None
        return await self.once(('raw', str(path)), load)

    async def get(self, kind, resource_id, skin_index=0):
        try:
            path = self.images._path(kind, resource_id, skin_index)
            url = character_resource_url(kind, resource_id, skin_index)
        except (TypeError, ValueError):
            return None
        return await self.read(path, url, ('get', kind, resource_id, skin_index))

    async def resolved_source(self, kind, resource_id, skin_index=0):
        async def load():
            raw = await self.get(kind, resource_id, skin_index)
            actual = skin_index
            if not raw and skin_index:
                raw, actual = await self.get(kind, resource_id, 0), 0
            if not raw:
                return ResolvedImage(PLACEHOLDER, skin_index, None, False, True, None)
            return ResolvedImage(image_data_uri(raw, RESOURCE_TYPES[kind].embed_size),
                                 skin_index, actual, actual != skin_index, False, hashlib.sha256(raw).hexdigest())
        return await self.once(('source', kind, resource_id, skin_index), load)

    async def get_asset(self, kind, key, logical_path):
        from .base_icons import base_icon_spec
        from .cache import PUBLIC_ICON_TYPES
        import re
        if kind == 'weapons':
            spec = base_icon_spec(kind, key)
            if spec is None or logical_path != spec.url:
                return None
            path, url = self.root/spec.directory/(spec.key+'.png'), spec.url
        else:
            if kind not in PUBLIC_ICON_TYPES or not isinstance(key, (str, int)):
                return None
            directory, prefix = PUBLIC_ICON_TYPES[kind]
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', str(key)) or not isinstance(logical_path, str) or not logical_path.startswith(prefix):
                return None
            if not re.fullmatch(r'[A-Za-z0-9_-]+\.png', logical_path[len(prefix):]):
                return None
            path, url = self.root/directory/(str(key)+'.png'), obfuscate_path(logical_path)
        return await self.read(path, url, ('get_asset', kind, key, logical_path), immutable=kind=='weapons')

    async def get_badge(self, key):
        from .badges import local_badge, badge_path
        from .base_icons import STATIC_BADGES
        record_asset(badge_path(self.images, key))
        raw = local_badge(self.images, key, allow_fallback=True)
        if raw is None:
            # Audited built-in stars/core keep a cold card complete without HTTP.
            raw = base64.b64decode(STATIC_BADGES[key]['base64'])
            self.refresh.add(('get_badge', key))
        elif key == 'core':
            meta = read_metadata(badge_path(self.images, key).with_suffix('.json'))
            if not 0 <= self.images.clock()-meta.get('checked_at', 0) < self.images.ttl:
                self.refresh.add(('get_badge', key))
        return raw


@asynccontextmanager
async def display_assets(images, *, budget=12):
    if not isinstance(images, ImageCache):
        yield images
        return
    async with httpx.AsyncClient(timeout=6, trust_env=False, follow_redirects=False) as http:
        view = DisplayAssets(images, pooled_cache(images, images.http or http), budget=budget)
        try:
            yield view
        finally:
            # Close/cancel scoped memo tasks before releasing the shared HTTP pool.
            tasks = list(view.memo.values())
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
