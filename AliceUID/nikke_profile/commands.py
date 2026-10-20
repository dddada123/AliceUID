"""nk 信息：个人名片查询与渲染。"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import asyncio
from functools import wraps
import time

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from ..nikke_api.parser import StaticData
from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
from ..nikke_permissions.runtime import get_policy
from ..nikke_resource.service import get_resources
from ..nikke_user.models import AliceBind
from ..nikke_user.service import load_client
from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
from ..nikke_user.service import binding_lock
from .builder import build_profile_context
from .draw import draw_profile

sv_profile = SV("妮姬个人信息", priority=3)

_cache: dict[str, tuple[float, dict]] = {}
_fetch_locks: dict[str, asyncio.Lock] = {}
_last_fetch: dict[str, float] = {}


def profile_errors(func):
    @wraps(func)
    async def guarded(bot, ev):
        try:
            return await func(bot, ev)
        except Exception as exc:
            logger.error(f"[AliceUID] 资料命令失败 command={func.__name__} error_type={type(exc).__name__}")
            await bot.send("查询操作失败，请稍后重试。", at_sender=True)
    return guarded


def _account_key(bind) -> str:
    return f'{bind.game_id}:{bind.intl_open_id}:{bind.area_id}'


async def _clear_profile_cache(bind) -> None:
    # Wait for an in-flight fetch to publish before invalidating. Otherwise its
    # old result can refill the cache after the refresh command reports success.
    async with _fetch_locks.setdefault(_account_key(bind), asyncio.Lock()):
        _cache.pop(_cache_key(bind), None)


class ProfileCooldown(Exception):
    pass


async def _profile_data(client, bind) -> dict:
    key = _cache_key(bind)
    account = _account_key(bind)
    async with _fetch_locks.setdefault(account, asyncio.Lock()):
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _cache_ttl():
            return cached[1]
        now = time.monotonic()
        if account in _last_fetch and now - _last_fetch[account] < 5:
            raise ProfileCooldown
        _last_fetch[account] = now
        data = await _fetch(client)
        from ..nikke_character.service import character_queries
        character_queries.invalidate(bind)
        from ..nikke_status.service import resource_status
        resource_status.invalidate(bind)
        _cache[key] = (time.time(), data)
        return data


def _get_static() -> StaticData:
    return get_resources().load_static()


def _cache_key(bind: AliceBind) -> str:
    from ..nikke_community.runtime import binding_revision
    return f"{bind.game_id}:{bind.intl_open_id}:{bind.area_id}:{binding_revision(bind)}"


def _cache_ttl() -> int:
    try:
        return int(AliceUIDConfig.get_config("AliceUID_CacheTTL").data or 600)
    except Exception:
        return 600


async def _fetch(client) -> dict:
    basic = await client.get_basic_info()
    outpost = await client.get_outpost_info()
    chars = await client.get_characters()

    try:
        saved = await client.get_saved_role_info()
        from ..nikke_login.regions import saved_role_matches
        if not saved_role_matches(saved, client.region):
            saved = {}
    except NikkeLoginRequired:
        raise
    except NikkeApiError as exc:
        if exc.code in (401, 403, 429, 300001):
            raise
        saved = {}
    except Exception:  # Optional endpoint failure must not disclose response text.
        saved = {}

    try:
        player = await client.get_game_player_info()
        if str(player.get('area_id', '')) != str(client.region.area_id):
            player = {}
    except NikkeLoginRequired:
        raise
    except NikkeApiError as exc:
        if exc.code in (401, 403, 429, 300001):
            raise
        player = {}
    except Exception:
        player = {}

    return {"basic": basic, "outpost": outpost, "chars": chars, "saved": saved, "player": player}


@sv_profile.on_fullmatch(("信息", "名片", "个人资料"))
@profile_errors
async def nikke_profile_cmd(bot: Bot, ev: Event):
    if not await get_policy().query_allowed(ev.group_id):
        await bot.send('本群未开放妮姬查询，请联系群管理员或 Bot 主。', at_sender=True)
        return
    client, bind = await load_client(ev.user_id, ev.bot_id)
    if client is None:
        await bot.send(unavailable_message(bind), at_sender=True)
        return

    try:
        data = await _profile_data(client, bind)

        context = build_profile_context(
            data["basic"],
            data["outpost"],
            data["chars"],
            _get_static(),
            saved_role=data["saved"],
            player_info=data["player"],
            area_label=client.region.label,
        )
        png = await draw_profile(context)
        async with binding_lock(ev.user_id,ev.bot_id):
            current=await AliceBind.get_bind(ev.user_id,ev.bot_id)
            if (current is not None and _cache_key(current)==_cache_key(bind) and
                    get_policy().user_allowed(ev.user_id) and await get_policy().query_allowed(ev.group_id)):
                await bot.send(MessageSegment.image(png), at_sender=True)
    except ProfileCooldown:
        await bot.send('资料刷新较频繁，请至少等待5秒后再查询。', at_sender=True)
    except NikkeLoginRequired:
        _cache.pop(_cache_key(bind), None)
        await bot.send(RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        logger.warning(f"[AliceUID] {command_prefix()} 信息查询失败 code={exc.code}")
        await bot.send(RELOGIN if is_login_error(exc) else f"查询失败，请稍后重试（{exc.code}）。", at_sender=True)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[AliceUID] {command_prefix()} 信息异常 error_type={type(exc).__name__}")
        await bot.send("查询失败，请稍后重试。", at_sender=True)
    finally:
        try:
            await client.close()
        except Exception as exc:
            logger.error(f"[AliceUID] 客户端关闭失败 error_type={type(exc).__name__}")


@sv_profile.on_fullmatch(("刷新信息", "刷新名片"))
@profile_errors
async def nikke_profile_refresh_cmd(bot: Bot, ev: Event):
    if not await get_policy().query_allowed(ev.group_id):
        await bot.send('本群未开放妮姬查询，请联系群管理员或 Bot 主。', at_sender=True)
        return
    bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
    if not bind:
        await bot.send(f"还没有绑定账号。发送 {command_prefix()} 登录 获取绑定链接。", at_sender=True)
        return
    await _clear_profile_cache(bind)
    from ..nikke_character.service import character_queries
    character_queries.invalidate(bind)
    await bot.send(f"已清除个人信息缓存，重新发送 {command_prefix()} 信息 即可。", at_sender=True)
