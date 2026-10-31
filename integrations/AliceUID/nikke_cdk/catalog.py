"""One shared refresh flight; 8-hour cron, daily first call and 4-hour freshness."""
from __future__ import annotations

import asyncio
import time
from .models import PRODUCT, PARSER_VERSION, day_at, merged, code_key
from .api import fetch_public


class Catalog:
    def __init__(self, store, fetch=fetch_public, clock=time.time):
        self.store, self.fetch, self.clock = store, fetch, clock
        self._flight = None

    def needs(self, now, first=False, scheduled=False):
        checked = self.store.meta('catalog_checked_at')
        snapshots = self.store.snapshots()
        incompatible = any(s.get('parser_version') != PARSER_VERSION for s in snapshots.values())
        return (checked is None or now < checked or incompatible
                or (first and self.store.meta('first_user_refresh_day') != day_at(now))
                or now - checked >= (28800 if scheduled else 14400))

    async def ensure(self, *, first=False, force=False, scheduled=False):
        now = self.clock()
        # Fixed cron checks occur on every scheduled tick; startup uses needs(scheduled=True).
        need = force or self.needs(now, first=first, scheduled=scheduled)
        if self._flight and not self._flight.done():
            report = await asyncio.shield(self._flight)
            if first and report['complete']:
                self.store.set_meta('first_user_refresh_day', day_at(self.clock()))
            return report
        if not need:
            return self.report('cached')
        if self.store.meta('cooldown_until', 0) > now:
            return self.report('cooldown')
        self._flight = asyncio.create_task(self._refresh(first))
        return await asyncio.shield(self._flight)

    async def _refresh(self, first):
        now = self.clock()
        token = self.store.acquire('catalog', now)
        if not token:
            # Another process owns the fetch. Wait a bounded time for its durable snapshot.
            checked = self.store.meta('catalog_checked_at')
            for _ in range(45):
                await asyncio.sleep(1)
                current = self.store.meta('catalog_checked_at')
                if current is not None and current != checked:
                    if first:
                        self.store.set_meta('first_user_refresh_day', day_at(self.clock()))
                    return self.report('joined')
            return self.report('busy')
        try:
            results = await asyncio.gather(*(self.fetch(s, now) for s in ('official', 'gamewith')),
                                           return_exceptions=True)
            snapshots, errors = {}, {}
            cooldown = 900
            for source, value in zip(('official', 'gamewith'), results):
                if isinstance(value, BaseException):
                    errors[source] = type(value).__name__
                    cooldown = max(cooldown, getattr(value, 'retry_after', 900))
                else:
                    try:
                        if (not isinstance(value, dict) or not isinstance(value.get('items'), list)
                                or any(not isinstance(i, dict) or 'code' not in i for i in value['items'])):
                            raise ValueError()
                        snapshots[source] = value
                    except (TypeError, ValueError):
                        errors[source] = 'InvalidSnapshot'
            finished = self.clock()
            self.store.publish(snapshots, finished, errors,
                day_at(finished) if first and not errors else None, lease=token, cooldown=cooldown)
            return self.report('refreshed')
        finally:
            self.store.release('catalog', token)

    def report(self, action='cached'):
        now = self.clock()
        snapshots = self.store.snapshots()
        items, warnings = merged(snapshots, now, self.store.blocked(PRODUCT),
                                 self.store.members(PRODUCT), self.store.details(PRODUCT), self.store.inventory(PRODUCT))
        for item in items:
            if not item.get('reward'):
                item['reward'] = self.reward(item['code'])
        errors = self.store.meta('errors', {})
        for source in errors:
            warnings.append(('官方' if source == 'official' else 'GameWith') + '最近更新失败；保留该源可用缓存')
        return dict(action=action, complete=not errors and len(snapshots) == 2,
                    checked_at=self.store.meta('catalog_checked_at'), items=items,
                    warnings=warnings, errors=errors,
                    sources={k: dict(checked_at=v['checked_at'], total=len(v['items'])) for k, v in snapshots.items()})

    def reward(self, code):
        from .models import clean
        detail = self.store.detail(PRODUCT, code)
        if detail and clean(detail.get('reward')):
            return clean(detail['reward'])
        source = self.store.snapshots().get('gamewith', {})
        for item in source.get('items', []):
            if code_key(item['code']) == code_key(code):
                return clean(item.get('reward', ''))
        return ''
