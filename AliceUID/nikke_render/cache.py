"""Bounded derived cards: stable content, explicit style dependencies and single flight."""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from ..nikke_character.cache import PanelCache
from ..nikke_resource.cache import atomic_write, validate_image, read_metadata

PACKAGE = Path(__file__).resolve().parents[1]
_stats = Counter()
_cache = None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def file_version(path):
    try:
        stat = Path(path).stat()
        return [stat.st_mtime_ns, stat.st_size]
    except OSError:
        return None


def style_version(*, dpi=None, theme=None):
    from .fonts import resolve_font
    from .language import get_card_language
    from .glass_settings import get_glass_strength
    from .theme import get_card_theme_mode
    from .background_sources import get_background_provider
    provider = get_background_provider()
    backgrounds = [(str(p), file_version(p)) for mode in ('dark', 'light')
                   for p in provider.candidates(mode)]
    if dpi is None:
        try:
            from ..nikke_config.config import AliceUIDConfig
            dpi = int(AliceUIDConfig.get_config('AliceUID_RenderDpi').data or 144)
        except (ImportError, AttributeError, KeyError, TypeError, ValueError):
            dpi = 144
    return dict(font=resolve_font().fingerprint, language=get_card_language(), backgrounds=backgrounds,
                bundled_assets=[(str(p.relative_to(PACKAGE.parent)), file_version(p))
                                for p in sorted((PACKAGE.parent/'assets').rglob('*'))
                                if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.svg', '.webp')],
                glass=get_glass_strength(), theme=theme or get_card_theme_mode(), dpi=dpi,
                templates=[(p.name, file_version(p)) for p in sorted((PACKAGE/'templates').iterdir())
                           if p.suffix in ('.html', '.css')],
                renderer=[(n, file_version(PACKAGE/'nikke_render'/n))
                          for n in ('theme.py', 'wallpaper.py', 'glass.py', 'render.py')],
                painters=[(n, file_version(PACKAGE/n/'draw.py')) for n in
                          ('nikke_profile', 'nikke_character', 'nikke_union', 'nikke_status')],
                alias_painter=file_version(PACKAGE/'nikke_character/alias_draw.py'))


def resource_version(resources, dependencies=None):
    """Small directory/metadata checks; never load or encode the N cached portraits."""
    root = getattr(getattr(resources, 'images', None), 'root', None)
    if root is None:
        return None
    root = Path(root)
    # A sidecar freshness/304 update is not a pixel change.
    if dependencies is None:
        assets = None  # Legacy entries have to prepare once to discover dependencies.
    else:
        assets = [[str(p), file_version(p)] for p in map(Path, dependencies)
                  if p.is_absolute() and p.is_relative_to(root.absolute())]
    return [assets,
            [[p.name, file_version(p)] for p in sorted((root.parent/'static').glob('*.json'))
             if not p.name.endswith('.meta.json')]]


def content_context(context):
    return {k: v for k, v in context.items()
            if not k.startswith('_') and k not in ('generated_at', 'fetched_at', 'fetched_at_epoch')}


def card_key(context, resources=None, *, dpi=None, dependencies=None):
    return fingerprint([content_context(context), style_version(dpi=dpi),
                        resource_version(resources, dependencies) if resources is not None else None])


class CardCache(PanelCache):
    """One image per hashed slot; a new season/content replaces the old image."""
    def __init__(self, root, *, clock=time.time):
        super().__init__(root)
        self.clock = clock
        self.locks = {}
        self.tasks = {}

    def read_card(self, slot, key, ttl):
        try:
            meta = read_metadata(self.path(slot, 'card.json'))
            if meta.get('fingerprint') != key or not 0 <= self.clock()-meta['created_at'] < ttl:
                return None
            path = self.path(slot, 'card-'+meta['sha256']+'.png')
            if path.stat().st_size > 64*1024*1024:
                return None
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != meta['sha256']:
                return None
            validate_image(data)
            return data
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def dependencies(self, slot):
        values = read_metadata(self.path(slot, 'card.json')).get('dependencies', [])
        return values if isinstance(values, list) and all(isinstance(p, str) for p in values) else []

    async def get(self, slot, key, build, *, ttl=7*86400, current=None, dependencies=None):
        if current is not None and not await current():
            raise ValueError('资料或权限已变化，已停止读取旧卡片。')
        flight = (slot, key())
        task = self.tasks.get(flight)
        if task is None:
            task = asyncio.create_task(self._get(slot, key, build, ttl=ttl, current=current, dependencies=dependencies))
            self.tasks[flight] = task
            def done(completed):
                if self.tasks.get(flight) is completed:
                    self.tasks.pop(flight, None)
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(done)
        else:
            _stats['image_joined'] += 1
        data = await asyncio.shield(task)
        if current is not None and not await current():
            raise ValueError('资料或权限已变化，已停止发送旧卡片。')
        return data

    async def _get(self, slot, key, build, *, ttl=7*86400, current=None, dependencies=None):
        async with self.locks.setdefault(slot, asyncio.Lock()):
            if current is not None and not await current():
                raise ValueError('资料或权限已变化，已停止生成旧卡片。')
            data = self.read_card(slot, key(), ttl)
            if data is not None:
                _stats['image_hit'] += 1
                return data
            _stats['image_miss'] += 1
            # build returns the exact key after preparation but before painting.
            data, prepared_key = await build()
            validate_image(data)
            if current is not None and not await current():
                raise ValueError('资料或权限已变化，已停止保存旧卡片。')
            if prepared_key == key():
                sha = hashlib.sha256(data).hexdigest()
                image_path = self.path(slot, 'card-'+sha+'.png')
                atomic_write(image_path, data)
                atomic_write(self.path(slot, 'card.json'), json.dumps(dict(
                    fingerprint=prepared_key, sha256=sha,
                    created_at=self.clock(), ttl=ttl, dependencies=dependencies or []), allow_nan=False).encode())
                for old in image_path.parent.glob('card-*.png'):
                    if old != image_path:
                        self.path(slot, old.name).unlink(missing_ok=True)
            _stats['image_built'] += 1
            return data

    def cleanup(self):
        if not self.root.exists():
            return 0
        removed = 0
        for directory in self.root.iterdir():
            if len(directory.name) != 64 or not directory.is_dir():
                continue
            try:
                meta = read_metadata(self.path(directory.name, 'card.json'))
                if not 0 <= self.clock()-meta.get('created_at', 0) < meta.get('ttl', 7*86400):
                    self.purge(directory.name)
                    removed += 1
            except (OSError, ValueError, TypeError):
                continue
        return removed


def get_card_cache():
    global _cache
    from ..nikke_config.config import MAIN_PATH
    root = MAIN_PATH/'cache'/'derived_cards'
    if _cache is None or _cache.root != root.absolute():
        _cache = CardCache(root)
    return _cache


def cache_stats():
    return dict(_stats)


def revoke_cards(bind):
    from ..nikke_character.cache import panel_identity
    scope = panel_identity(bind)
    cache = get_card_cache()
    cache.purge(fingerprint(['profile', scope]))
    for view in ('quick', 'detail', 'missing', 'tails'):
        for day in (0, 1):
            cache.purge(fingerprint(['union', scope, view, day]))
