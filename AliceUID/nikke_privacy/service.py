"""Restore temporary visibility without storing credentials or stale setting groups."""
from __future__ import annotations
import asyncio
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from ..nikke_resource.cache import atomic_write
from ..nikke_logs.store import event, record_failure, request_scope, current_request

READ = '/api/ugc/direct/standalonesite/User/GetUserPrivacySetting'
WRITE = '/api/ugc/proxy/standalonesite/User/SetUserShiftyspadPrivacy'
FIELDS = ('show_daily_info', 'show_outpost_info', 'show_lost_relics',
          'show_resource_info', 'show_union_info', 'show_nikke_info')
LABELS = {0: '隐藏', 1: '所有人可见', 2: '仅盟友可见', 3: '仅好友可见'}


class PrivacyError(ValueError):
    pass


def account_key(bind):
    values = [str(bind.game_id), str(bind.intl_open_id)]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def check_owner(client, bind):
    if (str(client.credentials.openid) != str(bind.intl_open_id)
            or str(client.region.game_id) != str(bind.game_id)
            or int(client.region.area_id) != int(bind.area_id)):
        raise PrivacyError('本人账号或区服未确认，未修改隐私。')


async def self_share(client, bind):
    check_owner(client, bind)
    data = await client._request('POST', '/api/ugc/proxy/standalonesite/User/GetUserInfoNew', {})
    share = str(((data.get('data') or {}).get('info') or {}).get('intl_openid') or '')
    prefix, separator, identifier = share.partition('-')
    if prefix != str(bind.game_id) or separator != '-' or not identifier.isascii() or not identifier.isdigit():
        raise PrivacyError('未取得本人社区标识，未修改隐私。')
    return share


@dataclass(frozen=True)
class PrivacyLease:
    account: str
    job: str
    original: int


class PrivacyService:
    def __init__(self, root, *, clock=time.time):
        self.root, self.clock = Path(root), clock
        self.locks = {}
        self.running = set()
        self.cancelled = set()

    def path(self, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise PrivacyError('隐私恢复记录标识无效。')
        return self.root / (key + '.json')

    def pending(self, key):
        path = self.path(key)
        if not path.exists():
            return None
        try:
            if path.stat().st_size > 16384:
                raise ValueError()
            item = json.loads(path.read_text('utf-8'))
            if (not isinstance(item, dict) or item.get('account') != key
                    or type(item.get('original')) is not int or item['original'] not in LABELS
                    or not isinstance(item.get('job'), str)
                    or item.get('state') not in {'reserved', 'opening', 'open', 'pending'}):
                raise ValueError()
            return item
        except (OSError, ValueError, TypeError):
            raise PrivacyError('隐私恢复记录不可读，请管理员检查，未继续修改官网设置。') from None

    def save(self, item):
        atomic_write(self.path(item['account']), json.dumps(item, ensure_ascii=False).encode())

    def clear(self, key):
        self.path(key).unlink(missing_ok=True)

    async def read(self, client, share):
        response = await client._request('POST', READ, {'intl_openid': share})
        data = response.get('data')
        if not isinstance(data, dict) or any(type(data.get(k)) is not int or data[k] not in LABELS for k in FIELDS):
            raise PrivacyError('官网隐私响应不完整，未猜测或覆盖设置。')
        return {key: data[key] for key in FIELDS}

    async def write(self, client, share, value, *, expected=None, before_write=None):
        latest = await self.read(client, share)
        if expected is not None and latest['show_nikke_info'] != expected:
            raise PrivacyError('官网妮姬设置已变化，请重新查询。')
        if latest['show_nikke_info'] == value:
            return
        payload = dict(latest, show_nikke_info=value)
        if before_write:
            before_write()
        await client._request('POST', WRITE, payload)
        confirmed = await self.read(client, share)
        if confirmed['show_nikke_info'] != value:
            raise PrivacyError('官网隐私修改未确认，请使用妮姬公开状态检查。')
        # Do not overwrite a concurrent change to another field with an old group.
        event('官网隐私', '保存', 'OK', count=value)

    async def begin(self, client, bind, share, notify, *, register=None):
        check_owner(client, bind)
        key = account_key(bind)
        async with self.locks.setdefault(key, asyncio.Lock()):
            existing = self.pending(key)
            if existing:
                if existing['job'] in self.running:
                    raise PrivacyError('本人隐私恢复任务仍在进行，请稍后重试。')
                await self._restore(client, bind, share)
                if self.pending(key):
                    raise PrivacyError('上次隐私恢复尚未完成，请先检查妮姬公开状态。')
            settings = await self.read(client, share)
            original = settings['show_nikke_info']
            if original == 1:
                return None
            item = dict(account=key, job='p'+secrets.token_hex(8), original=original,
                        user=str(bind.user_id), bot=str(bind.bot_id), state='reserved',
                        created_at=self.clock(), retry_at=0, request_id=current_request())
            self.save(item)
            lease = PrivacyLease(key, item['job'], original)
            self.running.add(lease.job)
            if register:
                register(lease)
            try:
                await notify(original)
                def opening():
                    item['state'] = 'opening'
                    self.save(item)  # Write-ahead: a lost response may still have changed visibility.
                await self.write(client, share, 1, expected=original, before_write=opening)
                item['state'] = 'open'
                self.save(item)
                return lease
            except BaseException:
                self.running.discard(lease.job)
                raise

    def valid(self, lease):
        return lease is None or lease.job not in self.cancelled

    async def manual(self, client, bind, share, value):
        if type(value) is not int or value not in (0, 1):
            raise PrivacyError('隐私目标值无效。')
        check_owner(client, bind)
        key = account_key(bind)
        async with self.locks.setdefault(key, asyncio.Lock()):
            pending = self.pending(key)
            if pending:
                # Explicit intent wins even if the write response is subsequently lost.
                pending['original'] = value
                pending['state'] = 'pending'
                self.save(pending)
                if value == 0:
                    self.cancelled.add(pending['job'])
            await self.write(client, share, value)
            if pending:
                self.clear(key)

    async def _restore(self, client, bind, share):
        key = account_key(bind)
        item = self.pending(key)
        if not item or item['job'] in self.running:
            return False
        if item['state'] == 'reserved':
            self.clear(key)
            return True
        try:
            latest = await self.read(client, share)
            if latest['show_nikke_info'] == 1:
                await self.write(client, share, item['original'], expected=1)
            # Different visible scope was chosen elsewhere; preserve it.
            self.clear(key)
            self.cancelled.discard(item['job'])
            event('官网隐私', '后台恢复', 'OK', count=item['original'])
            return True
        except Exception as exc:
            item['state'] = 'pending'
            item['retry_at'] = self.clock() + max(60, getattr(exc, 'retry_after', 0) or 0)
            item['error_type'] = type(exc).__name__
            self.save(item)
            record_failure('官网隐私', '后台恢复未确认', exc)
            return False

    async def restore(self, client, bind):
        check_owner(client, bind)
        key = account_key(bind)
        async with self.locks.setdefault(key, asyncio.Lock()):
            item = self.pending(key)
            if not item or item['job'] in self.running:
                return False
            share = await self_share(client, bind)
            return await self._restore(client, bind, share)


_service = None
_restoring = {}


def get_service():
    global _service
    if _service is None:
        from ..nikke_config.config import MAIN_PATH
        _service = PrivacyService(MAIN_PATH / 'privacy_restore')
    return _service


async def begin_recommendation(client, bind, account, notify, *, register=None):
    share = str(bind.game_id) + '-' + account.share_openid
    return await get_service().begin(client, bind, share, notify, register=register)


async def restore_owner(key):
    service = get_service()
    client = None
    try:
        item = service.pending(key)
        if not item or item['job'] in service.running:
            return
        from ..nikke_user.service import load_client
        client, bind = await load_client(item['user'], item['bot'])
        if client is None or account_key(bind) != key:
            event('官网隐私', '后台恢复', 'PENDING', reason='LOGIN_OR_BINDING_REQUIRED')
            return
        with request_scope('官网隐私后台', item.get('request_id')):
            await service.restore(client, bind)
    except Exception as exc:
        record_failure('官网隐私', '恢复任务', exc)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                record_failure('官网隐私', '恢复客户端关闭', exc)


async def before_unbind(bind):
    """Never discard the only credential while an outstanding restore is unresolved."""
    if bind is None:
        return
    service = get_service()
    key = account_key(bind)
    item = service.pending(key)
    if not item:
        return
    service.cancelled.add(item['job'])
    service.running.discard(item['job'])
    await restore_owner(key)
    if service.pending(key):
        raise PrivacyError('临时公开尚未恢复，已保留绑定；请先到官网恢复隐私后重试解绑。')


def schedule_restore(lease):
    if lease is None:
        return
    service = get_service()
    service.running.discard(lease.job)
    if lease.account in _restoring and not _restoring[lease.account].done():
        return
    task = asyncio.create_task(restore_owner(lease.account))
    _restoring[lease.account] = task
    def done(completed):
        if _restoring.get(lease.account) is completed:
            _restoring.pop(lease.account, None)
        if not completed.cancelled():
            completed.exception()
    task.add_done_callback(done)


async def recover_pending():
    service = get_service()
    for path in service.root.glob('*.json'):
        try:
            item = service.pending(path.stem)
            if item and item['job'] not in service.running and item.get('retry_at', 0) <= service.clock():
                if path.stem not in _restoring:
                    await restore_owner(path.stem)
        except Exception as exc:
            record_failure('官网隐私', '待恢复记录', exc)
