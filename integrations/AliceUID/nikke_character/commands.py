"""本人角色练度查询：nk爱丽丝练度 / nk练度 爱丽丝。"""
from __future__ import annotations
from contextlib import AsyncExitStack
from ..nikke_commands import command_prefix
from ..nikke_ai import query as ai_query, summary as ai_summary, description as ai_description

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
from ..nikke_permissions.runtime import get_policy
from ..nikke_resource.service import get_resources
from ..nikke_user.service import load_client
from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
from .builder import CharacterLookupError
from .service import CharacterCooldown, CharacterDataError, CharacterNotOwned, character_queries

sv_character = SV('妮姬角色练度', pm=6, priority=3)
USAGE = (f'用法：{command_prefix()}爱丽丝练度 / {command_prefix()}爱丽丝面板 / {command_prefix()}练度 爱丽丝\n'
         f'强制刷新：{command_prefix()}刷新爱丽丝面板（替换角色名，至少间隔5秒）。\n'
         f'仅查询本人已绑定账号持有的角色；全量表格请发送 {command_prefix()}练度全量导出。')


def _arguments(text: str) -> str:
    name = str(text or '').strip()
    if name.endswith(('练度', '面板')):
        name = name[:-2].strip()
    return name


def _cache_ttl() -> int:
    try:
        value = int(AliceUIDConfig.get_config('AliceUID_CacheTTL').data)
        return max(0, value)
    except (TypeError, ValueError, AttributeError):
        return 600


async def _query(bot: Bot, ev: Event, text: str, *, refresh: bool = False):
    client = None
    views = AsyncExitStack()
    name = ''
    def refresh_hint():
        return (f'请稍后使用 {command_prefix()}刷新{name}面板 重试，'
                f'或使用 {command_prefix()}刷新面板 同步社区数据。')
    try:
        name = _arguments(text)
        if not refresh and name == '全量导出':
            return  # Reserved for the exact export command.
        if not refresh and name.endswith(('刷新', '更新')):
            await bot.send(f'单角色更新请使用 {command_prefix()}刷新爱丽丝面板（替换角色名）。', at_sender=True)
            return
        if not name:
            await bot.send(USAGE, at_sender=True)
            return
        if not await get_policy().query_allowed(ev.group_id):
            await bot.send('本群未开放妮姬查询，请联系群管理员或 Bot 主。', at_sender=True)
            return
        client, bind = await load_client(ev.user_id, ev.bot_id)
        if client is None:
            await bot.send(unavailable_message(bind), at_sender=True)
            return
        from ..nikke_user.service import binding_lock
        from ..nikke_user.models import AliceBind
        from ..nikke_character.cache import panel_identity
        from ..nikke_roster.commands import allowed
        async def current():
            stored = await AliceBind.get_bind(ev.user_id, ev.bot_id)
            return (stored is not None and panel_identity(stored) == panel_identity(bind)
                    and await allowed(get_policy(), ev))
        if not await current():
            return
        await views.enter_async_context(character_queries.foreground_view(bind))
        resources = get_resources()
        equipment_items, skill_icons = await resources.ensure_character_tables()
        async def ownership_notice(role_name):
            if await current():
                await bot.send(f'本地记录未持有「{role_name}」，正在单独查询该角色，请稍候。', at_sender=True)
        context = await character_queries.query(
            client, bind, name, resources.load_static(), refresh=refresh, ttl=_cache_ttl(),
            equipment_items=equipment_items, skill_icons=skill_icons,
            current_check=current, publish_lock=binding_lock(ev.user_id, ev.bot_id),
            ownership_notice=ownership_notice,
        )
        # Draw and resource preparation are owned by the integration layer.
        from .draw import draw_character
        ai_summary("character", context)
        png = await draw_character(context)
        if not character_queries.context_current(context,bind):
            await bot.send('面板已更新，请重新查询；未发送旧卡片。',at_sender=True)
            return
        sent = False
        async with binding_lock(ev.user_id, ev.bot_id):
            if await current() and character_queries.context_current(context,bind):
                from ..nikke_time import beijing_text
                stamp = context.get('_detail_checked_at')
                canonical = context['name']  # Canonical static name, already resolved by name_code.
                text = ('角色资料最近核对：'+beijing_text(stamp)+'\n') if stamp else ''
                text += ('如卡片数据不是最新，请发送以下命令重新获取最新数据：\n'
                         f'{command_prefix()}刷新{canonical}面板')
                result = await bot.send([MessageSegment.image(png), text], at_sender=True)
                sent = result is not False
        if sent and context.get('_needs_full_refresh'):
            try:
                from ..nikke_user.panel_refresh import schedule_silent_refresh
                schedule_silent_refresh(bind, ev, get_policy())
            except Exception as exc:
                logger.warning(f'[AliceUID] silent refresh scheduling failed error_type={type(exc).__name__}')
    except (CharacterLookupError, CharacterCooldown, CharacterNotOwned, CharacterDataError) as exc:
        text = str(exc)
        if not isinstance(exc, (CharacterLookupError, CharacterNotOwned)):
            text += '\n' + refresh_hint()
        await bot.send(text, at_sender=True)
    except NikkeLoginRequired:
        await bot.send(RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        logger.warning(f'[AliceUID] 角色练度查询失败 code={exc.code}')
        if is_login_error(exc):
            await bot.send(RELOGIN, at_sender=True)
        elif exc.code == 403:
            await bot.send('社区拒绝访问（403），请稍后重试或检查账号资料权限。' + refresh_hint(), at_sender=True)
        elif exc.code == 429:
            await bot.send('社区请求较频繁，请稍后再查询练度。' + refresh_hint(), at_sender=True)
        else:
            await bot.send(f'练度查询失败，暂时无法完成社区核实或详情查询（{exc.code}）。' + refresh_hint(), at_sender=True)
    except Exception as exc:
        logger.error(f'[AliceUID] 角色练度异常 error_type={type(exc).__name__}')
        await bot.send('练度查询失败，暂时无法完成社区核实或详情查询，请稍后重试并请管理员检查日志。' + refresh_hint(), at_sender=True)
    finally:
        await views.aclose()
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                logger.error(f'[AliceUID] 角色查询客户端关闭失败 error_type={type(exc).__name__}')


@sv_character.on_command('练度',
    to_ai=ai_description("""查询当前用户本人持有的妮姬角色练度，展示等级、战力、技能和装备；复用插件缓存。
    不支持替他人查询，不执行强制刷新。
    Args:
        text: 单个角色名或别名，例如“爱丽丝”“红莲：暗影”，不附加刷新、更新或UID。
    """), covers=['妮姬角色练度', 'NIKKE技能等级', '妮姬角色装备'],
    aliases=['妮姬·查角色练度', '妮姬·我的角色面板'])
@ai_query(sv_character)
async def nikke_character_cmd(bot: Bot, ev: Event):
    await _query(bot, ev, ev.text or '')


@sv_character.on_suffix('练度')
async def nikke_character_suffix_cmd(bot: Bot, ev: Event):
    # Core's command and suffix triggers can both match a deliberately combined
    # input such as nk练度爱丽丝练度. get_command consumes the leading keyword in
    # that case, leaving 练度 at the end; only the command route should query it.
    text = (ev.text or '').strip()
    if not text or '练度' in text or '面板' in text:
        return
    await _query(bot, ev, text)


@sv_character.on_command('面板')
async def nikke_character_panel_cmd(bot: Bot, ev: Event):
    await _query(bot, ev, ev.text or '')


@sv_character.on_suffix('面板')
async def nikke_character_panel_suffix_cmd(bot: Bot, ev: Event):
    text=(ev.text or '').strip()
    # The exact whole-account refresh is owned by roster.commands. Removed
    # 更新面板 must not fall through to a character lookup either.
    if not text or text in ('更新', '刷新') or '面板' in text or '练度' in text:
        return
    if text.startswith('刷新'):
        await _query(bot, ev, text[len('刷新'):].strip(), refresh=True)
    else:
        await _query(bot, ev, text)
