"""Shared account scheduler and per-session consent; all adapters injectable."""
import asyncio
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import logging
import time
from .planner import (TZ, DEFAULT_QUIET, account_key, revision, night_next, pre_next,
                      quiet, quiet_value, bedtime)


class HarvestService:
    def __init__(self, store, fetch, allowed, send, *, clock=time.time, render=None,
                 has_context=lambda key: True):
        self.store, self.fetch, self.allowed, self.send = store, fetch, allowed, send
        self.clock, self.render, self.has_context = clock, render, has_context
        self.locks = {}
        self.send_lock = asyncio.Lock()
        self.tick_lock = asyncio.Lock()

    def lock(self, key):
        return self.locks.setdefault(key, asyncio.Lock())

    def live(self, account):
        latest = self.store.account(account['key'])
        return (latest is not None and latest['generation'] == account['generation']
                and latest['phase'] not in ('OFF', 'AUTO_STOPPED', 'PAUSED')
                and bool(self.store.subs(account['key'])))

    def plan(self, acc, snap, *, final=False):
        old = acc.get('snapshot')
        p = Decimal(snap['p'])
        old_phase, collected = acc['phase'], False
        if old and p < 85:
            expected = min(Decimal(100), Decimal(old['p']) + Decimal(str(max(0, snap['at']-old['at']))) / 864)
            if p + 1 < expected:
                collected = True
                acc['cycle'] += 1
        acc['snapshot'] = snap
        acc['error'] = ''
        if p < 85:
            acc.update(phase='WAIT_90', due=snap['t90'])
        elif p == 100 or final:
            acc.update(phase='WAIT_REARM', due=None)
        else:
            acc.update(phase='WAIT_MAX', due=snap['full'])
        if old_phase == 'WAIT_MAX' and not final and not collected and p < 100:
            acc.update(phase='WAIT_MAX', due=snap['full'])
        return acc

    async def enable(self, route, bind):
        key, now = account_key(bind), self.clock()
        async with self.lock(key):
            old = self.store.sub(route['id'])
            acc = self.store.account(key)
            if old and old['enabled'] and old['account'] == key and acc and acc['revision'] == revision(bind) and acc['phase'] not in ('OFF', 'AUTO_STOPPED', 'PAUSED', 'INITIALIZING'):
                # Reconnection changes transport identity, never consent identity.
                old['route'] = route
                self.store.save_sub(old)
                return acc, old, None, False
            if old and old['enabled'] and old['account'] != key:
                await self.disable(route['id'])
            reset = not acc or acc['phase'] in ('OFF', 'AUTO_STOPPED', 'PAUSED') or acc['revision'] != revision(bind)
            if reset:
                if acc:
                    self.store.stop(key, acc['generation'], 'reinitialized', now)
                acc = dict(key=key, user=route['user'], bot=route['bot'], revision=revision(bind),
                           generation=(acc['generation']+2 if acc else 1), cycle=(acc['cycle']+1 if acc else 1),
                           snapshot=None, phase='INITIALIZING', due=None, night_due=night_next(now),
                           full_nights=0, night_date='', error='')
                self.store.reset_nights(key)
                self.store.save_account(acc)
            sub = dict(id=route['id'], account=key, enabled=True, generation=(old['generation']+1 if old else 1),
                       route=route, quiet=old['quiet'] if old else DEFAULT_QUIET,
                       pre_due=pre_next(now, old['quiet'] if old else DEFAULT_QUIET), reason='')
            self.store.save_sub(sub)
            try:
                if not await self.allowed(sub, acc):
                    raise ValueError('当前会话、本人绑定或机器人路由不可用，未开启收菜提醒。')
                if reset or not self.has_context(key):
                    acc['bot'] = route['bot']
                    snap = await asyncio.wait_for(self.fetch(acc), 90)
                    if not self.live(acc):
                        raise ValueError('订阅或绑定已变化，本次开启已取消。')
                    self.plan(acc, snap)
                    if datetime.fromtimestamp(snap['at'], TZ).hour == 23:
                        self.store.nightly(acc, snap)
                    self.store.save_account(acc, acc['generation'])
                image = await self.render(acc, sub) if self.render else None
                current = self.store.sub(sub['id'])
                if not self.live(acc) or not current or not current['enabled'] or current['generation'] != sub['generation']:
                    raise ValueError('收菜提醒已关闭，本次开启已取消。')
                # An opening card is already a notification for this conversation.
                if Decimal(acc['snapshot']['p']) >= 85 or bedtime(now, acc['snapshot']['full'], sub['quiet']):
                    note = self.notice(acc, sub, 'normal')
                    self.store.enqueue(note)
                    self.store.mark(note['id'], 'confirmed')
                return acc, sub, image, True
            except BaseException:
                self.store.disable_sub(sub['id'], 'initialization_failed')
                if not self.store.subs(key):
                    latest = self.store.account(key)
                    self.store.stop(key, latest['generation'], 'initialization_failed', self.clock())
                raise

    async def disable(self, sid):
        async with self.send_lock:
            sub = self.store.disable_sub(sid)
            if sub and not self.store.subs(sub['account']):
                acc = self.store.account(sub['account'])
                self.store.stop(acc['key'], acc['generation'], 'manual', self.clock())
            return sub

    async def set_quiet(self, sid, value):
        value = quiet_value(value)
        async with self.send_lock:
            sub = self.store.sub(sid)
            if not sub:
                raise ValueError('请先在当前会话开启收菜提醒。')
            sub.update(quiet=value, pre_due=pre_next(self.clock(), value))
            self.store.save_sub(sub)
        return value

    def revoke(self, bind):
        if bind is None:
            return
        key = account_key(bind)
        acc = self.store.account(key)
        if acc:
            self.store.stop(key, acc['generation'], 'binding_changed', self.clock())

    def notice(self, acc, sub, kind):
        now = self.clock()
        event = f'{sub["id"]}:{acc["cycle"]}' if kind != 'stop' else f'{sub["id"]}:stop:{acc["generation"]}'
        return dict(id=event, account=acc['key'], generation=acc['generation'], sub=sub['id'],
                    sub_generation=sub['generation'], kind=kind, snapshot=acc.get('snapshot'),
                    created=now, expires=now+300)

    def events(self, acc, subs, now):
        events = set()
        if acc['phase'] in ('OFF', 'AUTO_STOPPED', 'INITIALIZING', 'PAUSED'):
            return events
        due = acc.get('due')
        if acc['phase'] == 'WAIT_MAX':
            return {'max'} if due is not None and due <= now else events
        if due is not None and due <= now:
            events.add('max' if now >= acc['snapshot']['full'] else 'ninety')
        if acc['night_due'] <= now:
            events.add('night')
        if any(s['pre_due'] is not None and s['pre_due'] <= now for s in subs):
            events.add('bed')
        return events

    async def process(self, key):
        async with self.lock(key):
            acc = self.store.account(key)
            subs = self.store.subs(key)
            now = self.clock()
            if not acc or not subs:
                return
            events = self.events(acc, subs, now)
            if not events or not self.store.claim(key, now):
                return
            try:
                await self._process(acc, subs, events)
            finally:
                self.store.release(key)

    async def _process(self, acc, subs, events):
        now = self.clock()
        allowed_ids = {s['id'] for s in subs if await self.allowed(s, acc)}
        subs = self.store.subs(acc['key'])
        active = [s for s in subs if s['id'] in allowed_ids]
        if not self.live(acc):
            return
        # No network for unauthorized/offline targets. Local scheduler can recover later.
        if not active:
            return
        night_window = datetime.fromtimestamp(now, TZ).hour == 23
        if acc['night_due'] <= now:
            acc['night_due'] = night_next(now)
        for sub in subs:
            if sub['pre_due'] is not None and sub['pre_due'] <= now:
                sub['pre_due'] = pre_next(now, sub['quiet'])
                self.store.save_sub(sub)
        snap = acc.get('snapshot')
        risk = snap and any(bedtime(now, snap['full'], s['quiet']) and not self.store.seen(s['id'], acc['cycle']) for s in active)
        recovery = acc['phase'] == 'WAIT_REARM' or acc.get('full_nights', 0) > 0
        query = bool(events & {'ninety', 'max'}) or bool(risk) or ('night' in events and night_window and recovery)
        if events == {'ninety'} and all(quiet(now, s['quiet']) for s in active):
            acc.update(phase='WAIT_MAX', due=snap['full'])
            self.store.save_account(acc, acc['generation'])
            return
        if not query:
            self.store.save_account(acc, acc['generation'])
            return
        acc['bot'] = active[0]['route']['bot']
        try:
            new = await asyncio.wait_for(self.fetch(acc), 90)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self.live(acc):
                return
            acc['error'] = type(exc).__name__
            if getattr(exc, 'harvest_auth', False):
                acc.update(phase='PAUSED', due=None)
            elif 'ninety' in events and snap:
                acc.update(phase='WAIT_MAX', due=snap['full'])
            else:
                acc.update(phase='WAIT_REARM', due=None)
            self.store.save_account(acc, acc['generation'])
            return
        if not self.live(acc):
            return
        self.plan(acc, new, final='max' in events)
        # Each actual 23:xx sample can serve both its due task and the nightly check.
        if datetime.fromtimestamp(new['at'], TZ).hour == 23:
            self.store.nightly(acc, new)
        if not self.store.save_account(acc, acc['generation']):
            return
        if acc.get('full_nights', 0) >= 2:
            stopping_ids = {s['id'] for s in self.store.subs(acc['key'])}
            stopped = self.store.stop(acc['key'], acc['generation'], 'two_full_nights', self.clock())
            if stopped:
                for sub in self.store.subs(acc['key'], active=False):
                    if sub['id'] in stopping_ids and sub['reason'] == 'two_full_nights':
                        self.store.enqueue(self.notice(stopped, sub, 'stop'))
            return
        p = Decimal(new['p'])
        bed_sent = False
        for sub in self.store.subs(acc['key']):
            if quiet(self.clock(), sub['quiet']) or self.store.seen(sub['id'], acc['cycle']):
                continue
            kind = None
            if bedtime(self.clock(), new['full'], sub['quiet']) and p < 100:
                kind = 'bed'
            elif 'ninety' in events and 85 <= p <= 95:
                kind = 'normal'
            elif events & {'ninety', 'max'} and p == 100:
                kind = 'full'
            if kind:
                self.store.enqueue(self.notice(acc, sub, kind))
                bed_sent |= kind == 'bed'
        if bed_sent:
            acc.update(phase='WAIT_MAX', due=new['full'])
            self.store.save_account(acc, acc['generation'])

    async def observe(self, key, rev, snap):
        """Accept real manual reads without creating consent or sending a message."""
        async with self.lock(key):
            acc = self.store.account(key)
            if not acc or not self.live(acc) or acc['phase'] == 'PAUSED' or acc['revision'] != rev:
                return
            old = acc.get('snapshot')
            if old and snap['at'] <= old['at']:
                return
            collected = old and Decimal(snap['p']) + 1 < min(Decimal(100), Decimal(old['p']) + Decimal(str(max(0, snap['at']-old['at']))) / 864)
            p = Decimal(snap['p'])
            if p < 85 and (collected or acc['phase'] == 'WAIT_90'):
                self.plan(acc, snap)
            else:
                acc['snapshot'] = snap
                if p == 100:
                    # This manual read already performed the MAX check.
                    acc.update(phase='WAIT_REARM', due=None)
                elif acc['phase'] == 'WAIT_MAX':
                    # Move the one pending check; never add an intermediate poll.
                    acc['due'] = snap['full']
                elif acc['phase'] == 'WAIT_90':
                    acc.update(phase='WAIT_90' if p < 90 else 'WAIT_MAX',
                               due=snap['t90'] if p < 90 else snap['full'])
            self.store.save_account(acc, acc['generation'])

    async def valid_notice(self, note):
        acc, sub = self.store.account(note['account']), self.store.sub(note['sub'])
        if not acc or not sub or acc['generation'] != note['generation'] or sub['generation'] != note['sub_generation']:
            return None
        if self.clock() > note['expires'] or quiet(self.clock(), sub['quiet']):
            return None
        if note['kind'] == 'stop':
            if acc['phase'] != 'AUTO_STOPPED' or sub['reason'] != 'two_full_nights':
                return None
        elif not sub['enabled'] or not self.live(acc) or acc['cycle'] != int(note['id'].rsplit(':', 1)[1]):
            return None
        if not await self.allowed(sub, acc):
            return None
        return sub

    async def deliver(self):
        # Also serializes explicit closes with final sends (not with network reads).
        async with self.send_lock:
            groups = defaultdict(list)
            for note in self.store.ready():
                sub = await self.valid_notice(note)
                if sub is None:
                    self.store.mark(note['id'], 'discarded')
                    continue
                route = sub['route']
                bucket = (route['bot'], route['self_id'], route['kind'], route['target'], note['kind'], sub['quiet'])
                groups[bucket].append((note, sub))
            for entries in groups.values():
                size = 5 if entries[0][1]['route']['kind'] == 'group' else 1
                for index in range(0, len(entries), size):
                    batch = []
                    for note, _ in entries[index:index+size]:
                        sub = await self.valid_notice(note)
                        if sub and self.store.reserve(note['id']):
                            batch.append((note, sub))
                    if not batch:
                        continue
                    try:
                        receipt = await asyncio.wait_for(self.send(batch), 40)
                        if isinstance(receipt, (list, tuple)) and receipt and all(isinstance(r, str) and r for r in receipt):
                            for note, _ in batch:
                                self.store.mark(note['id'], 'confirmed')
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # A missing/ambiguous receipt never resends the whole batch.
                        pass

    async def tick(self):
        if self.tick_lock.locked():
            return
        async with self.tick_lock:
            buckets = defaultdict(list)
            for acc in self.store.accounts():
                subs = self.store.subs(acc['key'])
                if subs and self.events(acc, subs, self.clock()):
                    for sub in subs:
                        r = sub['route']
                        buckets[(r['bot'], r['self_id'], r['kind'], r['target'])].append(acc['key'])
            checked = set()
            for bucket, keys in sorted(buckets.items(), key=lambda item: item[0][2] != 'group'):
                keys = list(dict.fromkeys(keys))
                for offset in range(0, len(keys), 5):
                    batch = [key for key in keys[offset:offset+5] if key not in checked]
                    checked.update(batch)
                    results = await asyncio.gather(*(self.process(key) for key in batch), return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            logging.getLogger(__name__).warning('harvest worker failed error_type=%s', type(result).__name__)
                    await self.deliver()
            await self.deliver()
