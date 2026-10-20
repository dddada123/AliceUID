"""Active bounded panel refresh without modifying profile/character modules."""
from __future__ import annotations
import asyncio
import time

_tasks = {}
_queue_locks = {}


async def refresh_panel(client, bind, *, actor=None, bot=None):
    from ..nikke_profile import commands as profile
    from ..nikke_character.service import character_queries
    from ..nikke_roster.cache import identity
    from ..nikke_roster.service import account_reads, get_roster_service
    from .models import AliceBind
    from .service import binding_lock
    actor = str(actor if actor is not None else bind.user_id)
    bot = str(bot if bot is not None else bind.bot_id)
    expected = identity(actor, bot, bind)[0]
    roster = get_roster_service()
    # Invalidate immediately; an older in-flight render cannot republish its file.
    roster.invalidate_binding(bind, actor, bot)
    character_queries.invalidate(bind)
    from ..nikke_status.service import resource_status
    resource_status.invalidate(bind)
    account = profile._account_key(bind)
    async with profile._fetch_locks.setdefault(account, asyncio.Lock()):
        profile._cache.pop(profile._cache_key(bind), None)
        async with account_reads.transaction(client, bind) as paced:
            # basic, outpost, roster, matching saved role, player: max five calls.
            data = await profile._fetch(paced)
        async with binding_lock(actor, bot):
            current = await AliceBind.get_bind(actor, bot)
            if current is None or identity(actor, bot, current)[0] != expected:
                raise ValueError('绑定已变化，已停止发布旧账号资料。')
            profile._cache[profile._cache_key(bind)] = (time.time(), data)
            profile._last_fetch[account] = time.monotonic()
            character_queries.invalidate(bind)
            roster.invalidate_binding(bind, actor, bot)
    return data


async def refresh_worker(bot, ev, policy):
    from gsuid_core.logger import logger
    from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
    from ..nikke_roster.commands import allowed
    from ..nikke_roster.service import RosterCooldown
    from .service import load_client
    from .auth_state import RELOGIN, is_login_error, unavailable_message
    client = None
    try:
        if not await allowed(policy, ev):
            return
        client, bind = await load_client(ev.user_id, ev.bot_id)
        if client is None:
            await bot.send(unavailable_message(bind), at_sender=True)
            return
        await refresh_panel(client, bind, actor=ev.user_id, bot=ev.bot_id)
        if await allowed(policy, ev):
            await bot.send('本人资料与角色列表已主动更新，阵容卡片和角色详情缓存已失效。', at_sender=True)
    except RosterCooldown as exc:
        await bot.send(str(exc), at_sender=True)
    except NikkeLoginRequired:
        await bot.send(RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        await bot.send(RELOGIN if is_login_error(exc) else f'更新失败（{exc.code}），已停止请求，请稍后再试。', at_sender=True)
    except Exception as exc:
        logger.error(f'[AliceUID] panel refresh failed error_type={type(exc).__name__}')
        await bot.send('更新面板失败，请稍后重试。', at_sender=True)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def queue_refresh(bot, ev, policy):
    from ..nikke_roster.commands import allowed
    if not await allowed(policy, ev):
        await bot.send('当前用户或群未开放妮姬查询，请联系管理员。', at_sender=True)
        return
    key = str(ev.user_id), str(ev.bot_id)
    async with _queue_locks.setdefault(key, asyncio.Lock()):
        if key in _tasks and not _tasks[key].done():
            await bot.send('面板正在更新，请稍候。', at_sender=True)
            return
        await bot.send('正在主动更新本人面板；请求按间隔串行执行。', at_sender=True)
        task = asyncio.create_task(refresh_worker(bot, ev, policy))
        _tasks[key] = task
    def done(completed):
        if _tasks.get(key) is completed:
            _tasks.pop(key, None)
        if not completed.cancelled():
            completed.exception()
    task.add_done_callback(done)
