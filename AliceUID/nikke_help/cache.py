"""Two shared help images, durable for 30 days; no player identity in cache keys."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from pathlib import Path

from ..nikke_resource.cache import atomic_write

TTL = 30 * 24 * 60 * 60
CACHE_VERSION = '1.0.11:1'
PNG_HEADER = b'\x89PNG\r\n\x1a\n'


class HelpCache:
    def __init__(self, root: Path, *, clock=time.time):
        self.root, self.clock = Path(root), clock
        self._locks = {}

    def _read(self, role, fingerprint):
        try:
            meta = json.loads((self.root / f'{role}.json').read_text('utf-8'))
            age = self.clock() - meta['created_at']
            if meta['fingerprint'] != fingerprint or not 0 <= age < TTL:
                return None
            image = (self.root / f'{role}.png').read_bytes()
            if image.startswith(PNG_HEADER) and hashlib.sha256(image).hexdigest() == meta['sha256']:
                return image
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return None

    async def get(self, context, renderer, *, settings=None):
        role = 'owner' if context['role'] == 'Bot 主' else 'public'
        # Do not accept personalized labels even from future integration callers.
        shared = {key: value for key, value in context.items()
                  if not key.startswith('commander_') and key != 'card_theme'}
        fingerprint = hashlib.sha256(json.dumps(
            [CACHE_VERSION, shared, settings], ensure_ascii=False, sort_keys=True,
            separators=(',', ':')).encode()).hexdigest()
        async with self._locks.setdefault(role, asyncio.Lock()):
            image = self._read(role, fingerprint)
            if image is not None:
                return image
            theme = random.choice(('light', 'dark'))
            image = await renderer(dict(shared, card_theme=theme))
            if not isinstance(image, bytes) or not image.startswith(PNG_HEADER):
                raise ValueError('help renderer did not return PNG')
            # Publish metadata last. A crash/torn pair is treated as a cache miss.
            meta = dict(fingerprint=fingerprint, created_at=self.clock(), theme=theme,
                        sha256=hashlib.sha256(image).hexdigest())
            atomic_write(self.root / f'{role}.png', image)
            atomic_write(self.root / f'{role}.json', json.dumps(meta).encode())
            return image


_cache = None


async def cached_help(context, renderer):
    from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
    global _cache
    root = MAIN_PATH / 'cache' / 'help'
    if _cache is None or _cache.root != root:
        _cache = HelpCache(root)
    # Guide content/settings changes invalidate immediately, never per sender.
    keys = ('AliceUID_CardLanguage', 'AliceUID_CardFont', 'AliceUID_GlassStrength', 'AliceUID_RenderDpi')
    settings = {key: AliceUIDConfig.get_config(key).data for key in keys}
    return await _cache.get(context, renderer, settings=settings)
