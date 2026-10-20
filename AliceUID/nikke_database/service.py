"""Durable, bounded public database update queue, independent of player accounts."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import logging
from pathlib import Path
import time

import httpx

from ..nikke_api.resource import CDN, RESOURCE_TYPES, validate_resource_key
from ..nikke_resource import service as resource_module
from ..nikke_resource.cache import MAX_BYTES, ImageCache, atomic_write, normalize_png, read_metadata
from ..nikke_resource.base_icons import BASE_ICONS, STATIC_BADGES, FIXED_WEAPON_URLS, ensure_base_icon_library

from ..nikke_resource.badges import FIXED_BADGE_URLS, local_badge

log = logging.getLogger(__name__)
DEFAULTS = {
    'DatabaseWeeklyUpdate': True,
    'DatabaseIncludeSkins': True,
    'DatabaseMaxTasks': 40,
    'DatabaseMaxDownloadMB': 128,
    'DatabaseMaxDiskMB': 2048,
    'DatabaseRequestInterval': 2.0,
    'DatabaseFailureCooldown': 3600,
    'DatabaseMaxRunMinutes': 30,
}


class BatchStopped(Exception):
    """Must escape resource fallback handlers so blocked sources stop the batch."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class PublicHTTP:
    """Only public CDN and reviewed fixed icon GETs; strip injected credentials."""
    public_resource_paced = True
    def __init__(self, http, *, interval, byte_limit, sleep=asyncio.sleep, monotonic=time.monotonic):
        self.http, self.interval, self.byte_limit = http, max(2.0, interval), byte_limit
        self.sleep, self.monotonic = sleep, monotonic
        self.bytes = 0
        self.last_request = None
        self.stopped = ''

    @asynccontextmanager
    async def stream(self, method, url, headers=None):
        if self.stopped:
            raise BatchStopped(self.stopped)
        parsed = httpx.URL(url)
        cdn_allowed = (parsed.scheme == 'https' and parsed.host == httpx.URL(CDN).host
                       and parsed.port in {None, 443} and not parsed.username and not parsed.password
                       and not parsed.query and not parsed.fragment)
        if method != 'GET' or not (cdn_allowed or str(url) in (FIXED_WEAPON_URLS | FIXED_BADGE_URLS)):
            raise BatchStopped('公开资源地址不在允许的 CDN 或固定公共图标范围内')
        if self.bytes >= self.byte_limit:
            raise BatchStopped('本次下载字节预算已用完')
        if self.last_request is not None:
            await self.sleep(max(0, self.interval - (self.monotonic() - self.last_request)))
        self.last_request = self.monotonic()
        public_headers = {k: v for k, v in (headers or {}).items()
                          if k.lower() in {'user-agent', 'referer', 'if-none-match', 'accept'}}
        request = self.http.build_request('GET', url, headers=public_headers)
        for key in ('cookie', 'authorization', 'proxy-authorization'):
            request.headers.pop(key, None)
        response = await self.http.send(request, stream=True, auth=None, follow_redirects=False)
        started = self.monotonic()
        received = 0
        last_progress = started
        try:
            length = int(response.headers.get('content-length', ''))
            if length <= 0 or response.headers.get('content-encoding'):
                length = None
        except ValueError:
            length = None
        try:
            if response.status_code in {401, 403, 429} or 300 <= response.status_code < 304 or 304 < response.status_code < 400:
                self.stopped = f'公开源返回 HTTP {response.status_code}，已停止本批；可能拒绝访问、限流或要求登录，不会使用用户凭据或轮换地址'
                raise BatchStopped(self.stopped)
            if response.headers.get('content-type', '').split(';', 1)[0].lower() in {'text/html', 'application/xhtml+xml'}:
                self.stopped = '公开源返回网页而非资源，可能要求登录或拒绝访问；已停止本批，不使用用户凭据'
                raise BatchStopped(self.stopped)
            owner = self
            class CountedResponse:
                def __getattr__(self, name):
                    return getattr(response, name)

                async def aiter_bytes(self):
                    nonlocal received, last_progress
                    async for part in response.aiter_bytes():
                        owner.bytes += len(part)
                        received += len(part)
                        if owner.bytes > owner.byte_limit:
                            raise BatchStopped('本次下载字节预算已用完')
                        now = owner.monotonic()
                        if now-last_progress >= 1:
                            log.info('AliceUID resource stage=download bytes=%s total=%s percent=%s speed_Bps=%.0f batch_bytes=%s',
                                     received,length,round(received*100/length,1) if length and received<=length else None,
                                     received/max(.001,now-started),owner.bytes)
                            last_progress = now
                        yield part
            yield CountedResponse()
        finally:
            await response.aclose()
            log.info('AliceUID resource stage=response_closed bytes=%s total=%s speed_Bps=%.0f batch_bytes=%s',
                     received,length,received/max(.001,self.monotonic()-started),self.bytes)


class DatabaseService:
    def __init__(self, resources, *, config_getter=None, http=None, clock=time.time,
                 sleep=asyncio.sleep, monotonic=time.monotonic):
        self.resources = resources
        self.config_getter = config_getter
        self.http, self.clock, self.sleep, self.monotonic = http, clock, sleep, monotonic
        self.path = Path(resources.root) / 'database' / 'manifest.json'
        self._lock = asyncio.Lock()
        self.task = None
        self._owner = None
        self._last_request = None
        self._deadline = None

    def config(self, key):
        try:
            value = self.config_getter(key) if self.config_getter else DEFAULTS[key]
            return DEFAULTS[key] if value is None else value
        except (KeyError, TypeError, ValueError):
            return DEFAULTS[key]

    def number(self, key, minimum):
        try:
            value = float(self.config(key))
            return max(minimum, value) if value < float('inf') else DEFAULTS[key]
        except (TypeError, ValueError, OverflowError):
            return DEFAULTS[key]

    def state(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value, dict) and value.get('version') == 1:
                for field in ('characters', 'assets', 'tables'):
                    if not isinstance(value.get(field), dict):
                        value[field] = {}
                if not isinstance(value.get('queue'), list):
                    value['queue'] = []
                return value
        except (OSError, ValueError):
            pass
        return {'version': 1, 'characters': {}, 'assets': {}, 'tables': {}, 'queue': []}

    def save(self, state):
        atomic_write(self.path, json.dumps(state, ensure_ascii=False, sort_keys=True).encode())

    def _prune_disabled_skins(self, state):
        if self.config('DatabaseIncludeSkins') is not True:
            state['queue'] = [item for item in state['queue']
                              if isinstance(item, dict) and type(item.get('skin_index')) is int
                              and item['skin_index'] == 0]

    def _inventory(self, resources):
        characters, assets = {}, {}
        for code, row in resources.load_static().characters.items():
            if not isinstance(row, dict):
                continue
            try:
                rid, _ = validate_resource_key(row.get('resource_id'), 0)
            except (ValueError, TypeError):
                continue
            characters[str(code)] = {'hash': digest(row), 'resource_id': rid,
                                      'costumes': row.get('costumes', [])}
            skins = {0: None}
            costumes = row.get('costumes', []) if self.config('DatabaseIncludeSkins') is True else []
            for costume in costumes:
                try:
                    _, skin = validate_resource_key(rid, costume['costume_index'])
                    if skin > 0:
                        skins[skin] = costume
                except (ValueError, TypeError, KeyError):
                    continue
            for skin, costume in skins.items():
                for kind in ('icons', 'portraits', 'full'):
                    key = f'{kind}:{rid}:{skin}'
                    assets[key] = {'kind': kind, 'resource_id': rid, 'skin_index': skin,
                                   'mapping_hash': digest([rid, skin, costume])}
        return characters, assets

    def _asset_path(self, item):
        return self.resources.images.root / RESOURCE_TYPES[item['kind']].directory / f"c{item['resource_id']:03d}_{item['skin_index']:02d}.png"

    def _local_hash(self, item):
        path = self._asset_path(item)
        try:
            raw = path.read_bytes()
            data = normalize_png(raw)
            if raw != data:
                atomic_write(path, data)
            return hashlib.sha256(data).hexdigest()
        except (OSError, ValueError):
            return ''

    def _plan(self, state, resources):
        characters, assets = self._inventory(resources)
        old = state.get('characters', {})
        changes = {'added': len(characters.keys() - old.keys()),
                   'removed': len(old.keys() - characters.keys()),
                   'changed': sum(old[k] != v for k, v in characters.items() if k in old)}
        old_assets = state.get('assets', {})
        old_queue = {item['key']: item for item in state.get('queue', []) if isinstance(item, dict) and isinstance(item.get('key'), str)}
        queue = []
        # Base SI, MI, full art first; optional explicit variants follow.
        kind_order = {'icons': 0, 'portraits': 1, 'full': 2}
        for key, item in sorted(assets.items(), key=lambda kv: (kv[1]['skin_index'] != 0, kind_order[kv[1]['kind']], kv[0])):
            previous = old_assets.get(key, {})
            local_hash = self._local_hash(item)
            changed = bool(previous and previous.get('mapping_hash') != item['mapping_hash'])
            outstanding = old_queue.get(key)
            item['sha256'] = local_hash
            if not local_hash or changed or (outstanding and outstanding.get('refresh')):
                pending = dict(item, key=key, refresh=changed or bool(outstanding and outstanding.get('refresh')))
                if outstanding:
                    pending['retry_after'] = outstanding.get('retry_after', 0)
                queue.append(pending)
        state.update(characters=characters, assets=assets, queue=queue)
        tables = getattr(resources, 'TABLES', resource_module.TABLES)
        for name in tables:
            path = Path(resources.root) / 'static' / name
            if not path.exists():
                path = Path(resources.bundled) / name
            if path.is_file():
                state['tables'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return changes

    def running(self):
        return self._owner is not None or self._lock.locked() or (self.task is not None and not self.task.done())

    async def run_continuous(self, *, reason='manual', progress=None):
        """Resume bounded batches without fetching unchanged tables on every batch."""
        if self._owner is not None or self._lock.locked():
            return {'busy': True, 'status': 'busy'}
        self._owner = asyncio.current_task()
        deadline = self.monotonic() + self.number('DatabaseMaxRunMinutes', 1) * 60
        self._deadline = deadline
        total = {'downloaded': 0, 'attempted': 0, 'failed': 0, 'bytes': 0, 'batches': 0}
        first = True
        initial_tables, initial_changes = {}, {}
        try:
            while True:
                batch = await self.run(reason=reason if first else 'resume', progress=progress)
                if first:
                    initial_tables, initial_changes = batch.get('tables', {}), batch.get('changes', {})
                first = False
                for key in ('downloaded', 'attempted', 'failed', 'bytes'):
                    total[key] += batch.get(key, 0)
                total['batches'] += 1
                result = dict(batch, **total, tables=initial_tables, changes=initial_changes, reason=reason)
                if batch.get('status') != 'incomplete' or not (batch.get('pending') or batch.get('pending_base')):
                    break
                state = self.state()
                if (self.clock() < float(state.get('retry_after', 0))
                        or not batch.get('downloaded')
                        or any(value in {'fallback', 'cooldown'} for value in initial_tables.values())):
                    break
                if '磁盘' in batch.get('error', ''):
                    break
                if self.monotonic() >= deadline:
                    result['error'] = '本次后台补全达到总时长预算，剩余任务已保存，尚未全部完成'
                    break
                log.info('AliceUID database resume batch=%s downloaded=%s pending=%s', total['batches'], total['downloaded'], batch['pending'])
                if progress:
                    await progress(result)
                await self.sleep(0)
            state = self.state()
            if result.get('status') != 'busy':
                state.update(last_report=result, status=result['status'])
                self.save(state)
            return result
        finally:
            self._owner = None
            self._deadline = None

    def start(self, *, reason='manual', progress=None, done=None):
        if self.running():
            return None
        async def worker():
            try:
                report = await self.run_continuous(reason=reason, progress=progress)
            except Exception as exc:
                log.exception('AliceUID database update failed')
                report = {'status': 'error', 'error': f'数据库更新失败：{type(exc).__name__}', 'pending': len(self.state()['queue'])}
            if done:
                try:
                    await done(report)
                except Exception:
                    log.exception('AliceUID database completion message failed')
            return report
        self.task = asyncio.create_task(worker())
        return self.task

    async def run(self, *, reason='manual', progress=None):
        if self._lock.locked() or (self._owner is not None and self._owner is not asyncio.current_task()):
            return {'busy': True, 'status': 'busy'}
        async with self._lock:
            state = self.state()
            self._prune_disabled_skins(state)
            self.save(state)
            now = self.clock()
            if now < float(state.get('retry_after', 0)):
                return dict(state.get('last_report', {}), status='cooldown', pending=len(state['queue']),
                            include_skins=self.config('DatabaseIncludeSkins') is True,
                            error='公开资源失败冷却中，请稍后继续；旧资源保留')
            report = {'status': 'incomplete', 'tables': {}, 'downloaded': 0, 'attempted': 0,
                      'pending': len(state['queue']), 'bytes': 0, 'failed': 0, 'changes': {}, 'reason': reason}
            async def emit(stage, public=None):
                report.update(stage=stage,pending=len(state['queue']),
                              bytes=public.bytes if public is not None else report['bytes'],
                              total=len(state['assets']),
                              available=max(0,len(state['assets'])-len(state['queue'])),
                              checkpoint=state['queue'][0]['key'] if state['queue'] else None)
                log.info('AliceUID database progress %s',json.dumps(report,ensure_ascii=False))
                if progress:
                    await progress(dict(report))
            state.update(last_attempt=now, status='running')
            self.save(state)
            await emit('tables' if reason != 'resume' else 'resume')
            async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as owned:
                public = PublicHTTP(self.http or owned,
                                    interval=self.number('DatabaseRequestInterval', 1.5),
                                    byte_limit=int(self.number('DatabaseMaxDownloadMB', 1) * 1024**2),
                                    sleep=self.sleep, monotonic=self.monotonic)
                public.last_request = self._last_request
                # Isolated adapters avoid changing shared query clients or their cache TTL.
                resources = resource_module.ResourceService(self.resources.root, self.resources.bundled, http=public, clock=self.clock)
                images = ImageCache(self.resources.images.root, http=public, clock=self.clock)
                try:
                    if reason != 'resume':
                        report['tables'] = await resources.update_tables(force=True)
                        report['changes'] = self._plan(state, resources)
                        self.save(state)
                    report['skipped'] = max(0,len(state['assets'])-len(state['queue']))
                    await emit('base_icons',public)
                    max_tasks = int(self.number('DatabaseMaxTasks', 1))
                    disk_limit = int(self.number('DatabaseMaxDiskMB', 1) * 1024**2)
                    base = report['base_icons'] = {}
                    try:
                        await ensure_base_icon_library(
                            resources, public, max_downloads=max_tasks, disk_limit=disk_limit,
                            should_stop=lambda: self._deadline is not None and self.monotonic() >= self._deadline,
                            report=base)
                    finally:
                        report['attempted'] += base.get('attempted', 0)
                        report['downloaded'] += base.get('downloaded', 0)
                        report['failed'] += base.get('attempted', 0) - base.get('downloaded', 0)
                    report['pending_base'] = base['pending']
                    report['missing_base'] = base['missing']
                    await emit('characters',public)
                    disk = sum(p.stat().st_size for p in Path(self.resources.images.root).rglob('*.png') if p.is_file())
                    for item in list(state['queue']):
                        if item.get('skin_index') != 0 and self.config('DatabaseIncludeSkins') is not True:
                            self._prune_disabled_skins(state)
                            self.save(state)
                            continue
                        if self._deadline is not None and self.monotonic() >= self._deadline:
                            report['error'] = '本次后台补全达到总时长预算，剩余任务已保存，尚未全部完成'
                            break
                        if report['attempted'] >= max_tasks:
                            report['error'] = '本次任务预算已用完，剩余任务已持久保存'
                            break
                        if self.clock() < float(item.get('retry_after', 0)):
                            continue
                        path = self._asset_path(item)
                        meta = read_metadata(path.with_suffix('.json'))
                        if self.clock() < meta.get('retry_after', 0):
                            item['retry_after'] = meta['retry_after']
                            continue
                        # Reserve worst-case image size before download; never delete old resources.
                        if disk + MAX_BYTES > disk_limit:
                            report['error'] = '图库磁盘预算不足，剩余任务已持久保存；可调整 DatabaseMaxDiskMB'
                            break
                        old_size = path.stat().st_size if path.exists() else 0
                        report['attempted'] += 1
                        data = await images.get(item['kind'], item['resource_id'], item['skin_index'], refresh=item.get('refresh', False))
                        meta = read_metadata(path.with_suffix('.json'))
                        if data and not meta.get('retry_after', 0) > self.clock():
                            state['assets'][item['key']]['sha256'] = hashlib.sha256(data).hexdigest()
                            state['queue'].remove(item)
                            report['downloaded'] += 1
                            disk += len(data) - old_size
                        else:
                            report['failed'] += 1
                            item['retry_after'] = max(meta.get('retry_after', 0), self.clock() + self.number('DatabaseFailureCooldown', 60))
                        self.save(state)
                        await emit('characters',public)
                    if any(value in {'fallback', 'cooldown'} for value in report['tables'].values()):
                        report['error'] = '部分公开静态表未能更新（源不可用、格式异常或可能要求登录）；沿用旧表，不使用用户凭据'
                    if report['failed'] and not report.get('error'):
                        report['error'] = '部分公开图片暂不可用或校验失败，已冷却并保留待处理队列与旧资源'
                    if report.get('pending_base') and not report.get('error'):
                        report['error'] = '基础图标尚未全部补齐，剩余固定资源将在后续批次继续；不使用用户凭据'
                    report['status'] = 'complete' if not state['queue'] and not report.get('pending_base') and not report.get('error') else 'incomplete'
                except BatchStopped as exc:
                    report.update(status='incomplete', error=str(exc))
                    if '字节预算' not in str(exc):
                        state['retry_after'] = self.clock() + self.number('DatabaseFailureCooldown', 60)
                except Exception as exc:
                    log.exception('AliceUID database batch failed')
                    report.update(status='error', error=f'数据库更新失败：{type(exc).__name__}；旧资源保留')
                    state['retry_after'] = self.clock() + self.number('DatabaseFailureCooldown', 60)
                finally:
                    self._last_request = public.last_request
                    report['missing_base'] = [f'{spec.kind}:{spec.key}' for spec in BASE_ICONS
                                              if images.local_base_icon(spec.kind, spec.key) is None]
                    report['missing_base'].extend('badges:' + key for key in STATIC_BADGES
                                                  if local_badge(images, key) is None)
                    report['pending_base'] = len(report['missing_base'])
                    if 'base_icons' in report:
                        report['base_icons'].update(missing=report['missing_base'], pending=report['pending_base'],
                                                    available=len(BASE_ICONS) + len(STATIC_BADGES) - report['pending_base'])
                    state['missing_base'] = report['missing_base']
                    report.update(pending=len(state['queue']), bytes=public.bytes,
                                  include_skins=self.config('DatabaseIncludeSkins') is True)
                    state.update(status=report['status'], last_report=report)
                    if report['status'] == 'complete':
                        state['last_success'] = self.clock()
                        state['retry_after'] = 0
                    self.save(state)
                    await emit('complete' if report['status']=='complete' else 'checkpoint_saved',public)
                    log.info('AliceUID database summary %s', json.dumps(report, ensure_ascii=False))
            return report


_database = None


def get_database(config_getter=None):
    global _database
    if _database is None:
        _database = DatabaseService(resource_module.get_resources(), config_getter=config_getter)
    elif config_getter is not None:
        _database.config_getter = config_getter
    return _database
