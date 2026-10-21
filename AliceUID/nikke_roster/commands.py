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


async def roster_worker(bot, event, policy):
    from gsuid_core.logger import logger
    from gsuid_core.segment import MessageSegment
    from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
    from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
    from ..nikke_user.models import AliceBind
    from ..nikke_user.service import load_client, binding_lock
    client, bind = None, None
    service = get_roster_service()
    try:
        if not await allowed(policy, event):
            await bot.send('当前权限已关闭，已停止生成卡片。', at_sender=True)
            return
        client, bind = await load_client(event.user_id, event.bot_id)
        if client is None:
            await bot.send(unavailable_message(bind), at_sender=True)
            return
        prepared = await service.prepare(client, bind, event.user_id, event.bot_id)
        # Binding mutations use this same lock. Prevent revoke/rebind between the
        # final revision check and send, and verify permissions again after work.
        async with binding_lock(event.user_id, event.bot_id):
            if not await current_before_send(policy, event, bind, prepared, AliceBind):
                service.cache.invalidate_key(prepared.key)
                await bot.send('绑定或权限已变化，已停止发送旧账号卡片。', at_sender=True)
                return
            data = prepared.path.read_bytes()
            from ..nikke_message import send_with_forward, display_name
            result = await send_with_forward(bot, event, MessageSegment.image(data),
                                             config_key='AliceUID_RosterForward',
                                             title=f'AliceUID·{display_name(getattr(bind, "nickname", ""), "未知指挥官")}·图鉴展示')
            if result is not False:
                service.mark_sent(prepared)
    except RosterCooldown as exc:
        await bot.send(str(exc), at_sender=True)
    except NikkeLoginRequired:
        if bind is not None:
            service.invalidate_binding(bind, event.user_id, event.bot_id)
        await bot.send(RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        if bind is not None and exc.code in (401, 403, 300001):
            service.invalidate_binding(bind, event.user_id, event.bot_id)
        await bot.send(RELOGIN if is_login_error(exc) else f'查询失败（{exc.code}），已停止请求，请稍后再试。', at_sender=True)
    except Exception as exc:
        logger.error(f'[AliceUID] roster failed error_type={type(exc).__name__}')
        await bot.send('无法安全生成或发送完整卡片，请稍后重试；不会发送截断图片。', at_sender=True)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def queue_roster(bot, event, policy):
    if not await allowed(policy, event):
        await bot.send('当前用户或群未开放妮姬查询，请联系管理员。', at_sender=True)
        return
    key = (str(event.user_id), str(event.bot_id))
    async with _queue_locks.setdefault(key, asyncio.Lock()):
        if key in _tasks and not _tasks[key].done():
            await bot.send('你的完整卡片正在生成，请稍候；已合并重复请求。', at_sender=True)
            return
        await bot.send('正在核对本人阵容并生成完整卡片，首次准备肖像可能稍久。', at_sender=True)
        task = asyncio.create_task(roster_worker(bot, event, policy))
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
        await queue_roster(bot, ev, policy)
    @sv.on_fullmatch(('更新面板', '刷新面板'))
    async def refresh(bot, ev):
        from ..nikke_user.panel_refresh import queue_refresh
        await queue_refresh(bot, ev, policy)
    if scheduler is None:
        from gsuid_core.aps import scheduler
    async def cleanup():
        # Local filesystem only; no account/static/public-network calls.
        from ..nikke_solo.cache import get_cache
        from gsuid_core.logger import logger
        for store in (get_roster_service().cache, get_cache()):
            try:
                store.cleanup()
            except (OSError, ValueError) as exc:
                logger.warning(f'[AliceUID] local cache cleanup error_type={type(exc).__name__}')
    scheduler.add_job(cleanup, 'interval', hours=1, id='aliceuid-roster-local-cleanup',
                      replace_existing=True, max_instances=1, coalesce=True)
    _registered = sv
    return sv
