"""Shared public metadata checks; never stores player profiles or credentials."""
from __future__ import annotations
import asyncio
import hashlib
import json
import math
import time
import httpx
from .selection import BY_CODE
from ..nikke_resource.cache import atomic_write

BASE = 'https://dildoro.com'

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()

POLICY = 'solo-season-v120'
ADVICE = '建议在本期活动第3天下午之后，再查询或刷新一次。'


def seasons(listing):
    rows = listing.get('seasons')
    if not isinstance(rows, list) or not 0 < len(rows) <= 100:
        raise ValueError('排行赛季列表异常或尚未收录')
    if any(not isinstance(s, dict) or type(s.get('raid')) is not int or s['raid'] <= 0
           or s.get('weakness_code') not in BY_CODE or not isinstance(s.get('servers'), list) for s in rows):
        raise ValueError('排行赛季信息异常')
    if len({s['raid'] for s in rows}) != len(rows):
        raise ValueError('排行赛季信息重复，暂无法确认')
    return sorted(rows, key=lambda s: s['raid'], reverse=True)


def automatic_code(listing):
    rows = seasons(listing)
    current = listing.get('current')
    raid = current.get('raid') if isinstance(current, dict) else None
    if raid is None:
        return rows[0]['weakness_code']
    if type(raid) is not int or raid <= 0:
        raise ValueError('网站赛季标识异常')
    row = next((s for s in rows if s['raid'] == raid), None)
    if row is None:
        raise ValueError('本期排行或属性尚未确认。' + ADVICE)
    return row['weakness_code']


def choose(listing, code, server):
    season = next((s for s in seasons(listing) if s['weakness_code'] == code), None)
    if season is None:
        raise ValueError('网站暂无该属性的排行参考赛季。' + ADVICE)
    if server not in season['servers']:
        raise ValueError('该属性最新参考赛季暂无本人区服数据。' + ADVICE)
    return season


def resolve(listing, mode, server):
    from .selection import ELEMENTS
    if mode == 'default':
        code = automatic_code(listing)
    else:
        code = ELEMENTS[mode][2]
    return code, choose(listing, code, server)


def season_notice(meta):
    current, raid = meta.get('current_raid'), meta.get('raid')
    if type(current) is not int or type(raid) is not int:
        return '本次未能确认赛季是否一致；当前按最近已收录的同属性赛季查询。'
    if current == raid:
        return ''
    if raid > current:
        return '参考赛季与网站赛季标识不一致，网站标识可能尚未同步，请稍后核对。' + ADVICE
    delta = current - raid
    detail = f'本次尚未取得第{current}期排行推荐，当前参考第{raid}期（落后{delta}期）。'
    if meta.get('mode') != 'default':
        detail = f'你手动指定了属性，当前使用第{raid}期同属性历史排行，与网站第{current}期不一致；本次未使用本期排行。若需本期推荐，请使用不带属性的查询。'
    return detail + ADVICE


def source_fingerprint(payload, season, server):
    if (payload.get('raid') != season['raid'] or
            payload.get('weakness_code') != season['weakness_code'] or
            payload.get('boss') != season.get('boss') or server not in payload.get('servers', [])):
        raise ValueError('实际阵容的赛季、属性、BOSS或区服与排行列表不一致')
    decks, sets, servers = payload.get('decks'), payload.get('sets'), payload.get('srv')
    if not all(isinstance(v, list) for v in (decks, sets, servers)) or len(sets) != len(servers):
        raise ValueError('网站阵容数据格式异常')
    relevant = []
    for ids, srv in zip(sets, servers):
        if srv != server:
            continue
        if (not isinstance(ids, list) or len(ids) != 5 or
                any(type(i) is not int or i < 0 or i >= len(decks) for i in ids)):
            raise ValueError('网站阵容索引异常')
        names = [decks[i] for i in ids]
        if any(not isinstance(d, list) or len(d) != 5 or
               any(not isinstance(n, str) or not n for n in d) for d in names):
            raise ValueError('网站队伍数据异常')
        relevant.append(names)
    if not relevant:
        raise ValueError('该属性参考赛季尚无本人区服有效五队阵容')
    # Ignore fetch timestamps and unrelated servers; compare actual usable inputs.
    return fingerprint([season['raid'], season.get('boss'), season['weakness_code'], server, relevant])

def metadata(listing, default_code, code, mode, season, source):
    current = listing.get('current') or {}
    raid = current.get('raid') if isinstance(current, dict) else None
    return dict(policy=POLICY, mode=mode, code=code, default_code=default_code,
                raid=season['raid'], boss=str(season.get('boss') or ''),
                fetched_at=str(season.get('fetched_at') or ''),
                active=listing.get('active') if type(listing.get('active')) is bool else None,
                current_raid=raid if type(raid) is int else None,
                current_until=str(current.get('until') or '') if isinstance(current, dict) else '',
                source_fingerprint=source, verified_at=time.time(), _listing=listing)

def revision(meta):
    return fingerprint([meta.get(k) for k in ('policy', 'mode', 'code', 'raid', 'boss', 'active', 'current_raid',
                                              'current_until', 'source_fingerprint')] +
                       ([meta.get('default_code')] if meta.get('mode') == 'default' else []) +
                       [(meta.get('recommended') or {}).get('fingerprint')])

def status_notes(meta):
    notes = []
    current, raid, active = meta.get('current_raid'), meta.get('raid'), meta.get('active')
    if type(current) is int and type(raid) is int and current > raid:
        notes.append('本次采用历史同属性赛季阵容；BOSS机制可能不同，不代表本期实战表现。')
    if active is True:
        notes.append('赛季进行中，已收录阵容可能尚不充分；排行、推荐与伤害预估后续仍可能变动。')
    elif active is None:
        notes.append('网站当前赛季状态未确认，排行数据仍可能继续补充。')
    else:
        notes.append('网站当前未标记排行采集活动进行中；参考赛季不代表正在进行的游戏活动。')
    return tuple(notes)

async def fetch_json(path):
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
        async with client.stream('GET', BASE + path, headers={'Cache-Control':'no-cache','Pragma':'no-cache'}) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError('网站排行响应过大')
    value = json.loads(body)
    if not isinstance(value, dict) or value.get('error'):
        raise ValueError('网站排行暂不可用')
    return value

class SiteMonitor:
    def __init__(self, path, *, clock=time.time, fetch=fetch_json, probe=None, recommend=None):
        self.path, self.clock, self.fetch, self.probe = path, clock, fetch, probe
        self.recommend = recommend
        self.lock = asyncio.Lock()
        self.retry_at = 0

    def load(self):
        try:
            if self.path.stat().st_size > 256 * 1024:
                return {}
            state = json.loads(self.path.read_text('utf-8'))
            if state.get('schema') == 2 and isinstance(state.get('entries'), dict):
                return state
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {}

    def fresh(self, stamp, ttl):
        return type(stamp) in (int, float) and math.isfinite(stamp) and 0 <= self.clock() - stamp < ttl

    def save(self, state):
        atomic_write(self.path, json.dumps(state, ensure_ascii=False, allow_nan=False).encode())

    async def record(self, image, server):
        meta = image.site
        if not meta:
            return
        async with self.lock:
            state = self.load()
            state.update(schema=2, listing=meta['_listing'], default_code=meta['default_code'],
                         checked_at=self.clock())
            entries = state.setdefault('entries', {})
            entries[meta['code'] + ':' + server] = dict(checked_at=self.clock(), meta=meta)
            self.save(state)

    async def inspect(self, mode, server):
        from .selection import ELEMENTS
        async with self.lock:
            if mode != 'default' and self.clock() < self.retry_at:
                raise ValueError('网站更新检查暂不可用，请稍后重试')
            try:
                state = self.load()
                listing = state.get('listing') or {}
                # Unknown state is checked at the active interval, not treated as closed.
                ttl = 21600 if listing.get('active') is False else 3600
                if mode == 'default' or not self.fresh(state.get('checked_at'), ttl):
                    listing = await self.fetch('/api/sr-rank/list')
                    # A browser's native default is unrelated to the current ranking season.
                    seasons(listing)
                    state.update(schema=2, listing=listing, checked_at=self.clock())
                code, season = resolve(listing, mode, server)
                try:
                    default_code = automatic_code(listing)
                except ValueError:
                    if mode == 'default':
                        raise
                    default_code = None
                state['default_code'] = default_code
                entries = state.setdefault('entries', {})
                entry = entries.get(code + ':' + server, {})
                old = entry.get('meta', {})
                ttl = 21600 if listing.get('active') is False else 3600
                if (old.get('policy') == POLICY and old.get('raid') == season['raid'] and old.get('fetched_at') == str(season.get('fetched_at') or '')
                        and self.fresh(entry.get('checked_at'), ttl)):
                    source = old['source_fingerprint']
                else:
                    payload = await self.fetch('/api/sr-rank/sets?raid=' + str(season['raid']))
                    source = source_fingerprint(payload, season, server)
                    entries[code + ':' + server] = dict(checked_at=self.clock(),
                        meta=metadata(listing, default_code, code, mode, season, source))
                result = metadata(listing, default_code, code, mode, season, source)
                if self.recommend is None:
                    from .recommended import fetch_recommendation
                    result['recommended'] = await fetch_recommendation(code, self.fetch)
                else:
                    result['recommended'] = await self.recommend(code)
                self.save(state)
                self.retry_at = 0
                return result
            except Exception:
                self.retry_at = self.clock() + 300
                raise

_monitor = None

def get_monitor():
    global _monitor
    from ..nikke_config.config import MAIN_PATH
    path = MAIN_PATH / 'cache' / 'solo' / 'site-v1.json'
    if _monitor is None or _monitor.path != path:
        _monitor = SiteMonitor(path)
    return _monitor
