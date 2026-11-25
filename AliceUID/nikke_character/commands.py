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


def _arguments(text: str) -> tuple[str, bool]:
    name = str(text or '').strip()
    refresh = False
    if name.endswith('刷新'):
        refresh = True
        name = name[:-2].strip()
    if name.endswith(('练度', '面板')):
        name = name[:-2].strip()
    return name, refresh


def _format_candidate_message(exc: CharacterLookupError, static) -> str | None:
    codes = getattr(exc, 'codes', None) or getattr(exc, 'suggestions', None) or []
    if not codes:
        return None
    from .aliases import aliases_for_code
    prefix = command_prefix()
    header = '角色名不唯一，请确认要查询的角色：' if getattr(exc, 'codes', None) else f'{exc}\n您是不是想找：'
    lines = [header]
    for idx, code in enumerate(codes[:10], 1):
        cname = static.name(code)
        aliases = sorted(set(aliases_for_code(code)), key=len)[:2]
        alias_str = f'（别名：{"、".join(aliases)}）' if aliases else ''
        lines.append(f'{idx}. {cname}{alias_str}')
    lines.append(f'请在 120 秒内回复 {prefix}查询1 ～ {prefix}查询{len(codes[:10])}，或直接发送完整角色名。')
    return '\n'.join(lines)


def _guide_hint_line(name_code: int | None, canonical: str) -> str:
    if name_code is None:
        return ''
    try:
        from ..nikke_guide.service import get_guide_service
        svc = get_guide_service()
        if svc.is_initialized() and svc.store.find_by_name_code(int(name_code), limit=1):
            return f'\n可发 {command_prefix()}{canonical}攻略 查看养成指南'
    except Exception:
        pass
    return ''


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
        parsed_name, trailing_refresh = _arguments(text)
        name = parsed_name
        refresh = refresh or trailing_refresh
        if not refresh and '全量导出' in name:
            return  # Reserved for the exact export command.
        from ..nikke_message.persona import send_reply
        if not refresh and name.endswith('更新'):
            await send_reply(bot, ev, f'单角色更新请使用 {command_prefix()}{name[:-2] or "爱丽丝"}练度 刷新 或 {command_prefix()}刷新爱丽丝面板。', at_sender=True)
            return
        if not name:
            await send_reply(bot, ev, USAGE, at_sender=True)
            return
        if not await get_policy().query_allowed(ev.group_id):
            await send_reply(bot, ev, '本群未开放妮姬查询，请联系群管理员或 Bot 主。', at_sender=True)
            return
        client, bind = await load_client(ev.user_id, ev.bot_id)
        if client is None:
            await send_reply(bot, ev, unavailable_message(bind), at_sender=True)
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
        if hasattr(resources, 'ensure_character_catalog'):
            await resources.ensure_character_catalog(name=name)
        equipment_items, skill_icons = await resources.ensure_character_tables()
        async def ownership_notice(role_name):
            if await current():
                from ..nikke_message.persona import send_reply, wait_character_single_query
                await send_reply(bot, ev, wait_character_single_query(role_name), at_sender=True)
        from ..nikke_resource.attributes import prepare_character
        context = await character_queries.query(
            client, bind, name, resources.load_static(), refresh=refresh, ttl=_cache_ttl(),
            equipment_items=equipment_items, skill_icons=skill_icons,
            current_check=current, publish_lock=binding_lock(ev.user_id, ev.bot_id),
            ownership_notice=ownership_notice, attribute_prepare=prepare_character,
        )
        # Draw and resource preparation are owned by the integration layer.
        from .draw import draw_character
        ai_summary("character", context)
        png = await draw_character(context)
        if not character_queries.context_current(context,bind):
            from ..nikke_message.persona import send_reply
            await send_reply(bot, ev, '面板已更新，请重新查询；未发送旧卡片。', at_sender=True)
            return
        sent = False
        async with binding_lock(ev.user_id, ev.bot_id):
            if await current() and character_queries.context_current(context,bind):
                import time as _time
                from ..nikke_time import beijing_text
                from ..nikke_message.persona import send_reply
                stamp = context.get('_detail_checked_at')
                canonical = context['name']  # Canonical static name, already resolved by name_code.
                if stamp and 0 <= (_time.time() - float(stamp)) < 600:
                    text = f'最近核对：{beijing_text(stamp)}'
                elif stamp:
                    text = f'最近核对：{beijing_text(stamp)} ｜ 刷新：{command_prefix()}刷新{canonical}面板'
                else:
                    text = f'刷新：{command_prefix()}刷新{canonical}面板'
                text += _guide_hint_line(context.get('name_code'), canonical)
                result = await send_reply(bot, ev, [MessageSegment.image(png), text], at_sender=True, newline=True)
                sent = result is not False
        if sent and context.get('_needs_full_refresh'):
            try:
                from ..nikke_user.panel_refresh import schedule_silent_refresh
                schedule_silent_refresh(bind, ev, get_policy())
            except Exception as exc:
                logger.warning(f'[AliceUID] silent refresh scheduling failed error_type={type(exc).__name__}')
    except CharacterLookupError as exc:
        from ..nikke_message.persona import send_reply
        static = get_resources().load_static()
        candidate_msg = _format_candidate_message(exc, static)
        if candidate_msg:
            codes = (getattr(exc, 'codes', None) or getattr(exc, 'suggestions', None) or [])[:10]
            from ..nikke_commands.selection import register_selection
            async def _pick_character(b, e, idx: int, _codes=codes, _refresh=refresh):
                if not 1 <= idx <= len(_codes):
                    await send_reply(b, e, f'编号超出范围，请回复 {command_prefix()}查询1 ～ {command_prefix()}查询{len(_codes)}。', at_sender=True)
                    return
                await _query(b, e, str(_codes[idx - 1]), refresh=_refresh)
            register_selection(ev, _pick_character)
            await send_reply(bot, ev, candidate_msg, at_sender=True)
        else:
            await send_reply(bot, ev, str(exc), at_sender=True)
    except (CharacterCooldown, CharacterNotOwned, CharacterDataError) as exc:
        from ..nikke_message.persona import send_reply
        text = str(exc) + '\n' + refresh_hint()
        await send_reply(bot, ev, text, at_sender=True)
    except NikkeLoginRequired:
        from ..nikke_message.persona import send_reply
        await send_reply(bot, ev, RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        from ..nikke_message.persona import send_reply
        logger.warning(f'[AliceUID] 角色练度查询失败 code={exc.code}')
        if is_login_error(exc):
            await send_reply(bot, ev, RELOGIN, at_sender=True)
        elif exc.code == 403:
            await send_reply(bot, ev, '社区拒绝访问（403），请稍后重试或检查账号资料权限。' + refresh_hint(), at_sender=True)
        elif exc.code == 429:
            await send_reply(bot, ev, '社区请求较频繁，请稍后再查询练度。' + refresh_hint(), at_sender=True)
        else:
            await send_reply(bot, ev, f'练度查询失败，暂时无法完成社区核实或详情查询（{exc.code}）。' + refresh_hint(), at_sender=True)
    except Exception as exc:
        from ..nikke_message.persona import send_reply
        logger.error(f'[AliceUID] 角色练度异常 error_type={type(exc).__name__}')
        await send_reply(bot, ev, '练度查询失败，暂时无法完成社区核实或详情查询，请稍后重试并请管理员检查日志。' + refresh_hint(), at_sender=True)
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


@sv_character.on_suffix('刷新')
async def nikke_character_refresh_suffix_cmd(bot: Bot, ev: Event):
    text = (ev.text or '').strip()
    if not text:
        return
    if text.endswith(('练度', '面板')):
        role = text[:-2].strip()
        if role and role not in ('更新', '刷新', '信息', '卡片', '图鉴'):
            await _query(bot, ev, role, refresh=True)
