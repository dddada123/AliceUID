"""Anonymous calendar plans; restart-safe hourly checks, never chat delivery."""
from __future__ import annotations
import asyncio
from datetime import datetime
import hashlib
import json
import logging
import math
import re
import time
from zoneinfo import ZoneInfo
from pathlib import Path
import httpx
from ..nikke_resource.cache import atomic_write

URL = 'https://api.blablalink.com/api/ugc/direct/standalonesite/Dynamics/GetCalendarDetail'
HOUR = 3600
DAY = 24 * HOUR
log = logging.getLogger(__name__)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def normalize_calendar(payload):
    if not isinstance(payload, dict) or type(payload.get('code')) is not int or payload['code'] != 0:
        raise ValueError('calendar business response')
    data = payload.get('data')
    module = data.get('character_gacha') if isinstance(data, dict) else None
    items = module.get('items') if isinstance(module, dict) else None
    if not isinstance(items, list) or len(items) > 256:
        raise ValueError('calendar schema')
    result = {}
    def numeric(v):
        if type(v) not in (int, str) or not re.fullmatch(r'[0-9]{1,12}', str(v)):
            raise ValueError('calendar identifier/time')
        return int(v)
    for row in items:
        start, end = numeric(row['start_time']), numeric(row['end_time'])
        if not 946684800 <= start < end < 4133980800:
            raise ValueError('calendar time range')
        characters = row.get('characters')
        if not isinstance(characters, list) or len(characters) > 100:
            raise ValueError('calendar characters')
        codes = []
        for char in characters:
            code, resource = numeric(char['name_code']), numeric(char['resource_id'])
            if not code or not resource:
                raise ValueError('calendar character key')
            codes.append(str(code))
        item = dict(start=start, end=end, codes=sorted(set(codes)))
        result[fingerprint(item)] = item
    return list(result.values())


async def fetch_calendar():
    headers = {'Referer': 'https://www.blablalink.com/activity-calendar',
               'Origin': 'https://www.blablalink.com', 'x-language': 'zh-tw', 'x-channel-type': '2',
               'x-common-params': json.dumps(dict(game_id='16', area_id='global', intl_game_id='29080',
                                                 language='zh-tw', source='pc_web', env='prod'))}
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
        response = await client.post(URL, json={}, headers=headers)
        if response.status_code == 429:
            error = ValueError('calendar rate limited')
            try:
                error.retry_after = max(HOUR, int(response.headers.get('retry-after', HOUR)))
            except ValueError:
                error.retry_after = HOUR
            raise error
        response.raise_for_status()
        if len(response.content) > 2 * 1024 * 1024:
            raise ValueError('calendar body limit')
        return normalize_calendar(response.json())


def database_snapshot(service):
    resources = service.resources
    characters = resources.load_static().characters
    ids = resources._load_rows('character_id_map.json')
    skills = resources._load_rows('character_skill_map.json')
    avatars = resources._load_rows('character_avatar_map.json')
    mapped = {(str(r.get('name_code')), str(r.get('resource_id'))) for r in ids}
    skilled = {str(r.get('resource_id')) for r in skills if all(r.get(k) for k in ('skill1_icon', 'skill2_icon', 'ulti_skill_icon'))}
    ready = [str(code) for code, row in characters.items()
             if (str(code), str(row.get('resource_id'))) in mapped and str(row.get('resource_id')) in skilled]
    ordered = lambda rows: sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    return dict(codes=sorted(str(c) for c in characters), ready=ready,
                fingerprint=fingerprint([characters, ordered(ids), ordered(skills), ordered(avatars)]))


class CalendarUpdates:
    def __init__(self, service, *, fetch=fetch_calendar, snapshot=database_snapshot, clock=time.time):
        self.service, self.fetch, self.snapshot, self.clock = service, fetch, snapshot, clock
        self.path = Path(service.path).with_name('calendar_update.json')
        self.lock = asyncio.Lock()

    def state(self):
        try:
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('calendar plan size')
            state = json.loads(self.path.read_text('utf-8'))
            if state.get('version') == 1 and isinstance(state.get('handled'), dict) and isinstance(state.get('plans'), dict):
                def valid_time(value):
                    return type(value) in (int, float) and math.isfinite(value) and value >= 0
                if not valid_time(state.get('poll_at')):
                    raise ValueError('calendar poll time')
                for key, plan in state['plans'].items():
                    if (not isinstance(plan, dict) or plan.get('key') != key or not valid_time(plan.get('due'))
                            or plan.get('kind') not in ('start', 'end') or not isinstance(plan.get('codes'), list)):
                        raise ValueError('calendar plan')
                active = state.get('active')
                if active is not None:
                    if (not isinstance(active, dict) or active.get('phase') not in ('waiting', 'observing')
                            or not all(valid_time(active.get(k)) for k in ('started', 'deadline', 'next', 'checks', 'failures'))
                            or not all(isinstance(active.get(k), list) for k in ('targets', 'baseline', 'seen'))
                            or not isinstance(active.get('last'), str)):
                        raise ValueError('calendar cycle')
                return state
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return dict(version=1, handled={}, plans={}, poll_at=0, active=None)

    def save(self, state):
        atomic_write(self.path, json.dumps(state, ensure_ascii=False, sort_keys=True).encode())

    def status(self):
        s = self.state()
        active = s.get('active')
        labels = {'waiting': '等待新妮姬/结构化资料', 'observing': '资料已就绪，等待一小时复查'}
        stamp = lambda ts: datetime.fromtimestamp(ts, ZoneInfo('Asia/Shanghai')).strftime('%m-%d %H:%M')
        if self.service.config('DatabaseCalendarUpdate') is False:
            return '日历自动更新已关闭'
        if active:
            return labels.get(active['phase'], active['phase']) + f"；下次 {stamp(active['next'])}；无新增等待截止 {stamp(active['deadline'])}（北京时间）"
        plans = [v['due'] for v in s['plans'].values() if v['key'] not in s['handled']]
        result = ('下次日历计划 ' + stamp(min(plans)) + '（北京时间）') if plans else '等待下一期日历计划'
        previous = s.get('last_cycle', {}).get('result')
        if previous:
            result += '；上轮：' + {'stable': '资料已稳定', 'timeout': '24小时未新增或目标资料未齐，已结束等待',
                                  'source_unavailable': '公开源未能完成核验，已结束等待'}.get(previous, previous)
        if s.get('calendar_error'):
            result += '；日历源暂不可用，保留已知计划'
        return result

    async def tick(self):
        if self.service.config('DatabaseCalendarUpdate') is False or self.lock.locked():
            return None
        async with self.lock:
            state = self.state()
            now = self.clock()
            active = state.get('active')
            if active and now > active['deadline']:
                self.finish(state, 'source_unavailable' if state.get('calendar_error') or not active['checks'] else 'timeout')
                active = None
            if not state.get('calendar_error') and any(p['due'] <= now and key not in state['handled'] for key, p in state['plans'].items()):
                state['poll_at'] = min(state.get('poll_at', 0), now)
            if state.get('calendar_error') and now < state.get('poll_at', 0):
                self.save(state)
                return None
            if now >= state.get('poll_at', 0):
                try:
                    items = await self.fetch()
                    plans = {}
                    snap = self.snapshot(self.service)
                    first = not state.get('initialized')
                    for item in items:
                        for kind, due in [('start', item['start']), ('end', item['end'] + 1)]:
                            key = fingerprint([kind, item])
                            plan = dict(key=key, kind=kind, due=due, codes=item['codes'] if kind == 'start' else [])
                            if first and due <= now:
                                if kind == 'start' and item['end'] >= now and set(item['codes']) - set(snap['ready']):
                                    plan['due'] = now
                                    plans[key] = plan
                                else:
                                    state['handled'][key] = now
                            elif due > now or (item['end'] >= now and key not in state['handled']):
                                if due <= now and key not in state['plans']:
                                    plan['due'] = now  # A newly announced, already active pool.
                                plans[key] = plan
                    for key, plan in state['plans'].items():
                        if plan['due'] <= now and key not in state['handled']:
                            plans.setdefault(key, plan)
                    state.update(plans=plans, initialized=True, calendar_error='',
                                 poll_at=now + (HOUR if active else 6 * HOUR))
                except Exception as exc:
                    state.update(calendar_error=type(exc).__name__, poll_at=now + max(HOUR, getattr(exc, 'retry_after', HOUR)))
                    self.save(state)
                    log.warning('AliceUID calendar plan fetch failed type=%s', type(exc).__name__)
                    return None
            for key, plan in state['plans'].items():
                if plan['due'] + DAY < now and key not in state['handled']:
                    state['handled'][key] = now
                    log.info('AliceUID calendar missed window skipped')
            due = [p for p in state['plans'].values() if p['due'] <= now and p['key'] not in state['handled']]
            if due:
                snap = self.snapshot(self.service)
                targets = sorted({c for p in due for c in p['codes']})
                if active is None:
                    started = min(p['due'] for p in due)
                    active = dict(phase='waiting', started=started, deadline=started + DAY, next=now,
                                  targets=targets, baseline=snap['codes'], last=snap['fingerprint'],
                                  seen=snap['codes'],
                                  require_new=not any(p['kind'] == 'start' for p in due) or bool(set(targets) - set(snap['codes'])),
                                  checks=0, failures=0, found_new=False)
                    state['active'] = active
                else:
                    active['targets'] = sorted(set(active['targets']) | set(targets))
                    if any(p['kind'] == 'start' for p in due):
                        active['require_new'] = bool(set(active['targets']) - set(snap['codes']))
                for p in due:
                    state['handled'][p['key']] = now
                # Completed old event IDs need not grow forever in a long-running bot.
                state['handled'] = dict(sorted(state['handled'].items(), key=lambda kv: kv[1])[-1024:])
                state['poll_at'] = min(state['poll_at'], now + HOUR)
            self.save(state)
            if active is None or now < active['next']:
                return None
            if self.service.running():
                return None
            if self.service.config('DatabaseCalendarUpdate') is False:
                return None
            active['next'] = now + HOUR
            self.save(state)
            try:
                structured_at = None
                async def progress(report):
                    nonlocal structured_at
                    if report.get('stage') == 'structured_ready':
                        structured_at = self.clock()
                report = await self.service.run_continuous(reason='calendar', progress=progress)
                if report.get('status') == 'busy':
                    return report
                tables = report.get('tables', {})
                if (report.get('status') in ('cooldown', 'error') or not tables
                        or any(not str(v).startswith('updated:') for v in tables.values())):
                    raise ValueError('structured data not freshly verified')
                snap = self.snapshot(self.service)
                active['checks'] += 1
                checked_at = structured_at if structured_at is not None else self.clock()
                active['next'] = checked_at + HOUR
                newly_seen = set(snap['codes']) - set(active['seen'])
                if newly_seen:
                    active['seen'] = sorted(set(active['seen']) | newly_seen)
                active['found_new'] = active['found_new'] or bool(newly_seen)
                ready = set(active['targets']) <= set(snap['ready'])
                satisfied = ready and (not active['require_new'] or active['found_new'])
                if satisfied:
                    if active['phase'] == 'observing' and snap['fingerprint'] == active['last']:
                        self.finish(state, 'stable')
                    else:
                        active.update(phase='observing', last=snap['fingerprint'],
                                      deadline=max(active['deadline'], checked_at + HOUR))
                if state.get('active') and self.clock() >= active['deadline']:
                    self.finish(state, 'timeout')
            except Exception as exc:
                active['failures'] += 1
                state['update_error'] = type(exc).__name__
                if self.clock() >= active['deadline']:
                    self.finish(state, 'source_unavailable')
                log.warning('AliceUID calendar update deferred type=%s', type(exc).__name__)
            self.save(state)
            return state.get('last_cycle') or state.get('active')

    def finish(self, state, result):
        active = state.get('active')
        if active:
            state['last_cycle'] = dict(active, result=result, finished=self.clock())
            state['active'] = None
            state['poll_at'] = 0
            log.info('AliceUID calendar update cycle result=%s checks=%s new=%s failures=%s',
                     result, active['checks'], active['found_new'], active['failures'])
