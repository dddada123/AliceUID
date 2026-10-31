"""Core adapters. Scheduled work never renders; only enable() asks for a card."""
from collections import OrderedDict
from contextlib import AsyncExitStack
import asyncio
import time
from .planner import account_key, revision, snapshot, title, body, footer
from .store import Store
from .service import HarvestService

_runtime = None
_sv = None
_contexts = OrderedDict()


class HarvestAuthError(ValueError):
    harvest_auth = True


def native_allowed(item, route, *, parent_area=None):
    if item is None or not getattr(item, 'enabled', True):
        return False
    area = getattr(item, 'area', 'ALL')
    kind = route['kind'].upper()
    if area not in ('ALL', 'SV', kind) and parent_area != 'ALL':
        return False
    if int(route.get('pm', 6)) > int(getattr(item, 'pm', 6)):
        return False
    targets = {route['user']}
    if route['kind'] == 'group':
        targets.add(route['target'])
    black = set(map(str, getattr(item, 'black_list', [])))
    white = set(map(str, getattr(item, 'white_list', []))) - {''}
    return not targets & black and (not white or bool(targets & white))


async def allowed(sub, acc):
    from gsuid_core.gss import gss
    from gsuid_core.sv import SL
    from gsuid_core.utils.plugins_config.gs_config import sp_config
    from ..nikke_permissions.runtime import get_policy
    from ..nikke_user.models import AliceBind
    from ..nikke_user.auth_state import expired, known_invalid
    route = sub['route']
    policy = get_policy()
    group = route['target'] if route['kind'] == 'group' else None
    if not policy.user_allowed(route['user']) or not await policy.query_allowed(group):
        return False
    targets = {route['user']} | ({group} if group else set())
    if targets & set(map(str, sp_config.get_config('BlackList').data)):
        return False
    plugin = SL.plugins.get('AliceUID')
    if not native_allowed(plugin, route) or not native_allowed(_sv, route, parent_area=getattr(plugin, 'area', None)):
        return False
    bind = await AliceBind.get_bind(route['user'], route['bot'])
    if bind is None or account_key(bind) != acc['key'] or revision(bind) != acc['revision']:
        return False
    if expired(bind) or known_invalid(bind):
        if _runtime is not None and acc.get('phase') not in (None, 'OFF', 'AUTO_STOPPED'):
            current = _runtime.store.account(acc['key'])
            if current and current['generation'] == acc['generation']:
                current.update(phase='PAUSED', due=None, error='HarvestAuthError')
                _runtime.store.save_account(current, current['generation'])
        return False
    transport = gss.active_bot.get(route['ws'])
    return transport is not None and getattr(transport, 'bot', None) is not None


async def fetch(acc):
    from ..nikke_user.service import load_client
    from ..nikke_user.auth_state import unavailable_message, is_login_error
    from ..nikke_status.service import resource_status
    from ..nikke_api.client import NikkeLoginRequired
    client, bind = await load_client(acc['user'], acc['bot'])
    if client is None:
        raise HarvestAuthError(unavailable_message(bind))
    try:
        if account_key(bind) != acc['key'] or revision(bind) != acc['revision']:
            raise HarvestAuthError('本人绑定已变化，请重新开启收菜提醒。')
        context = await resource_status.query(client, bind, actor=(acc['user'], acc['bot']), fresh=True)
        result = snapshot(context)
        _contexts[acc['key']] = context
        _contexts.move_to_end(acc['key'])
        while len(_contexts) > 256:
            _contexts.popitem(last=False)
        return result
    except Exception as exc:
        if isinstance(exc, NikkeLoginRequired) or is_login_error(exc):
            raise HarvestAuthError('登录凭据已失效，请重新登录后开启收菜提醒。') from None
        raise
    finally:
        await client.close()


async def render(acc, sub):
    from ..nikke_status.draw import draw_status
    from ..nikke_resource.cache import validate_image
    if not await allowed(sub, acc):
        raise ValueError('绑定或会话权限已变化，已停止生成开启卡片。')
    from ..nikke_status.service import resource_status
    from ..nikke_user.models import AliceBind
    bind = await AliceBind.get_bind(sub['route']['user'], sub['route']['bot'])
    if bind is None or revision(bind) != acc['revision']:
        raise ValueError('绑定已变化，开启卡片已取消。')
    context = _contexts[acc['key']]
    owner = resource_status.owner_key(bind, (sub['route']['user'], sub['route']['bot']))
    image = await draw_status(context, owner_key=owner)
    validate_image(image)
    return image


def segments(batch, now):
    from gsuid_core.segment import MessageSegment
    from ..nikke_commands import command_prefix
    kind = batch[0][0]['kind']
    message = [MessageSegment.text(title(kind)+'\n')]
    for note, sub in batch:
        if sub['route']['kind'] == 'group':
            message.extend([MessageSegment.at(sub['route']['user']), MessageSegment.text('  ')])
        message.append(MessageSegment.text(body(kind, note['snapshot'], now)+'\n'))
    end = footer(kind, batch[0][1]['quiet'], command_prefix())
    if end:
        message.append(MessageSegment.text(end))
    return message


async def send(batch):
    from gsuid_core.gss import gss
    from ..nikke_user.service import binding_lock
    service = get_runtime()
    # Binding changes and the actual send share the established owner lock.
    async with AsyncExitStack() as stack:
        for user, bot in sorted({(s['route']['user'], s['route']['bot']) for _, s in batch}):
            await stack.enter_async_context(binding_lock(user, bot))
        current = []
        for note, _ in batch:
            sub = await service.valid_notice(note)
            if sub:
                current.append((note, sub))
        if not current:
            return None
        route = current[0][1]['route']
        transport = gss.active_bot.get(route['ws'])
        if transport is None:
            return None
        return await transport.target_send(segments(current, service.clock()), route['kind'], route['target'],
                    route['bot'], route['self_id'], group_id=route['target'] if route['kind'] == 'group' else None,
                    at_sender=False, wait_recall=True)


def get_runtime():
    global _runtime
    if _runtime is None:
        from ..nikke_config.config import MAIN_PATH
        _runtime = HarvestService(Store(MAIN_PATH/'harvest.sqlite3'), fetch, allowed, send,
                                  render=render, has_context=lambda key: key in _contexts and 0 <= time.time()-_contexts[key]['fetched_at_epoch'] < 300)
    return _runtime


def setup(sv, scheduler=None):
    global _sv
    _sv = sv
    if scheduler is None:
        from gsuid_core.aps import scheduler
    runtime = get_runtime()
    scheduler.add_job(runtime.tick, 'interval', seconds=30, id='aliceuid-harvest',
                      name='AliceUID收菜提醒', replace_existing=True, max_instances=1,
                      coalesce=True, misfire_grace_time=60)
    return runtime


def revoke_binding(bind):
    if _runtime is not None and bind is not None:
        _contexts.pop(account_key(bind), None)
        _runtime.revoke(bind)


async def observe_manual(bind, context):
    if _runtime is None or context is None:
        return
    try:
        snap = snapshot(context)
    except (ValueError, KeyError):
        return
    key = account_key(bind)
    acc = _runtime.store.account(key)
    if acc and _runtime.live(acc) and acc['revision'] == revision(bind):
        current = _contexts.get(key)
        if current is None or snap['at'] > current['fetched_at_epoch']:
            _contexts[key] = context
            _contexts.move_to_end(key)
            while len(_contexts) > 256:
                _contexts.popitem(last=False)
    await _runtime.observe(key, revision(bind), snap)


def observe_route(ev):
    """Refresh only an already-consented exact conversation, never add consent."""
    if _runtime is None:
        return
    from .planner import route_from_event
    try:
        route = route_from_event(ev)
    except ValueError:
        return
    sub = _runtime.store.sub(route['id'])
    if sub and sub['enabled']:
        sub['route'] = route
        _runtime.store.save_sub(sub)
