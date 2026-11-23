"""Background roster commands: strong task ownership, deduplication and send guards."""
from __future__ import annotations
import asyncio
import inspect
from .cache import identity
from .service import RosterCooldown, get_roster_service

_tasks = {}
_queue_locks = {}
_registered = None


async def allowed(policy, event):
    if not await policy.query_allowed(getattr(event, 'group_id', None)):
        return False
    check = getattr(policy, 'user_allowed', None)
    if check is None:
        return True  # Root guard supplies global actor permissions during integration.
    result = check(event.user_id)
    return bool(await result if inspect.isawaitable(result) else result)


async def current_before_send(policy, event, bind, prepared, model):
    current = await model.get_bind(event.user_id, event.bot_id)
    if current is None or identity(event.user_id, event.bot_id, current)[0] != prepared.key:
        return False
    return await allowed(policy, event)


async def roster_worker(bot, event, policy, *, mode='main'):
    from ..nikke_logs.store import request_scope
    with request_scope('主力卡片' if mode == 'main' else '图鉴卡片'):
        return await _roster_worker(bot, event, policy, mode=mode)


async def _roster_worker(bot, event, policy, *, mode='main'):
    from gsuid_core.logger import logger
    from gsuid_core.segment import MessageSegment
    from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
    from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
    from ..nikke_user.models import AliceBind
    from ..nikke_user.service import load_client, binding_lock
    client, bind = None, None
    service = get_roster_service()
    try:
        from ..nikke_message.persona import send_reply as _send_reply
    except ImportError:
        async def _send_reply(b, e, p, *, at_sender=True, newline=False, sep=None):
            return await b.send(p, at_sender=at_sender)
    try:
        if not await allowed(policy, event):
            await _send_reply(bot, event, '当前权限已关闭，已停止生成卡片。', at_sender=True)
            return
        client, bind = await load_client(event.user_id, event.bot_id)
        if client is None:
            await _send_reply(bot, event, unavailable_message(bind), at_sender=True)
            return
        from ..nikke_logs.store import event as diagnostic_event
        async with asyncio.timeout(120):
            prepared = await service.prepare(client, bind, event.user_id, event.bot_id, mode=mode)
        # Binding mutations use this same lock. Prevent revoke/rebind between the
        # final revision check and send, and verify permissions again after work.
        async with binding_lock(event.user_id, event.bot_id):
            if not await current_before_send(policy, event, bind, prepared, AliceBind):
                service.cache.invalidate_key(prepared.key)
                await _send_reply(bot, event, '绑定或权限已变化，已停止发送旧账号卡片。', at_sender=True)
                return
            data = prepared.path.read_bytes()
            from ..nikke_message import send_with_forward, display_name
            log_label = '主力卡片' if mode == 'main' else '图鉴卡片'
            title_kind = '主力妮姬' if mode == 'main' else '图鉴展示'
            diagnostic_event(log_label, '发送', 'START', bytes=len(data))
            result = await send_with_forward(bot, event, MessageSegment.image(data),
                                             config_key='AliceUID_RosterForward',
                                             title=f'[AliceUID·{title_kind}·{display_name(getattr(bind, "nickname", ""), "未知指挥官")}]')
            diagnostic_event(log_label, '发送', 'OK' if result is not False else 'FAILED')
            if result is not False:
                service.mark_sent(prepared)
    except TimeoutError:
        await _send_reply(bot, event, '完整卡片生成等待超时，已结束本次任务；资料缓存保留，请稍后重试。', at_sender=True)
    except RosterCooldown as exc:
        await _send_reply(bot, event, str(exc), at_sender=True)
    except NikkeLoginRequired:
        if bind is not None:
            service.invalidate_binding(bind, event.user_id, event.bot_id)
        await _send_reply(bot, event, RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        if bind is not None and exc.code in (401, 403, 300001):
            service.invalidate_binding(bind, event.user_id, event.bot_id)
        await _send_reply(bot, event, RELOGIN if is_login_error(exc) else f'查询失败（{exc.code}），已停止请求，请稍后再试。', at_sender=True)
    except Exception as exc:
        logger.error(f'[AliceUID] roster failed error_type={type(exc).__name__}')
        await _send_reply(bot, event, '无法安全生成或发送完整卡片，请稍后重试；不会发送截断图片。', at_sender=True)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def queue_roster(bot, event, policy, *, mode='main'):
    try:
        from ..nikke_message.persona import send_reply, wait_roster_generating
    except ImportError:
        async def send_reply(b, e, p, *, at_sender=True, newline=False, sep=None):
            return await b.send(p, at_sender=at_sender)
        def wait_roster_generating(*, merged=False, mode='main', style=None):
            tag = '主力妮姬' if mode == 'main' else '图鉴展示'
            return f'[AliceUID·{tag}]\n' + ('正在合并重复请求，卡片生成中，请稍候。' if merged else '正在准备卡片，请稍候。')
    if not await allowed(policy, event):
        await send_reply(bot, event, '当前用户或群未开放妮姬查询，请联系管理员。', at_sender=True)
        return
    key = (str(event.user_id), str(event.bot_id)) if mode == 'main' else (str(event.user_id), str(event.bot_id), mode)
    async with _queue_locks.setdefault(key, asyncio.Lock()):
        if key in _tasks and not _tasks[key].done():
            await send_reply(bot, event, wait_roster_generating(merged=True, mode=mode), at_sender=True)
            return
        await send_reply(bot, event, wait_roster_generating(merged=False, mode=mode), at_sender=True)
        task = asyncio.create_task(roster_worker(bot, event, policy, mode=mode))
        _tasks[key] = task
    def done(completed):
        if _tasks.get(key) is completed:
            _tasks.pop(key, None)
        # Retrieve errors even if the messaging adapter failed in the error path.
        if not completed.cancelled():
            completed.exception()
    task.add_done_callback(done)


def setup(policy=None, scheduler=None):
    global _registered
    if _registered is not None:
        return _registered
    from gsuid_core.sv import SV
    from ..nikke_config.config import MAIN_PATH
    from ..nikke_permissions.policy import GroupPolicy
    policy = policy or GroupPolicy(MAIN_PATH / 'group_policy.json')
    sv = SV('妮姬完整阵容卡片', priority=3)
    @sv.on_fullmatch(('卡片', '阵容卡片', '妮姬卡片'))
    async def card(bot, ev):
        await queue_roster(bot, ev, policy, mode='main')
    @sv.on_fullmatch(('图鉴', '妮姬图鉴', '完整图鉴'))
    async def codex(bot, ev):
        await queue_roster(bot, ev, policy, mode='codex')
    @sv.on_fullmatch(('刷新面板',))
    async def refresh(bot, ev):
        from ..nikke_user.panel_refresh import queue_refresh
        await queue_refresh(bot, ev, policy)
    if scheduler is None:
        from gsuid_core.aps import scheduler
    async def cleanup():
        # Local filesystem only; no account/static/public-network calls.
        from ..nikke_solo.cache import get_cache
        from gsuid_core.logger import logger
        from ..nikke_render.cache import get_card_cache
        for store in (get_roster_service().cache, get_cache(), get_card_cache()):
            try:
                store.cleanup()
            except (OSError, ValueError) as exc:
                logger.warning(f'[AliceUID] local cache cleanup error_type={type(exc).__name__}')
    scheduler.add_job(cleanup, 'interval', hours=1, id='aliceuid-roster-local-cleanup',
                      replace_existing=True, max_instances=1, coalesce=True)
    _registered = sv
    return sv
