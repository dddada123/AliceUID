"""Single Union Raid command boundary; all reads use the invoking sender."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from ..nikke_config.config import MAIN_PATH
from ..nikke_permissions.runtime import get_policy
from ..nikke_user.service import load_client
from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
from ..nikke_user.service import binding_lock
from ..nikke_user.models import AliceBind
from .builder import UnionDataError
from .service import UnionCooldown, union_queries

sv_union = SV('妮姬联盟突袭', pm=6, priority=3)
_before_send = None
USAGE = f'用法：{command_prefix()}出刀 / {command_prefix()}出刀速查 Day2 / {command_prefix()}出刀 Day1 / {command_prefix()}查刀 / {command_prefix()}出刀详情10（按伤害排名查成员，不带数字查本人） / {command_prefix()}出刀缺刀 / {command_prefix()}出刀尾刀。'


def set_before_send(callback):
    """Parent hook: async callback(bot, event) -> bool, rechecked before sending."""
    global _before_send
    _before_send = callback


async def _send(bot, ev, message, *, title=None, caption=None):
    if _before_send is not None and not await _before_send(bot, ev):
        return
    if getattr(message, 'type', None) == 'image':
        from ..nikke_message import send_with_forward
        await send_with_forward(bot, ev, [message, caption] if caption else message,
                                config_key='AliceUID_UnionForward', at_sender=False,
                                title=title or 'AliceUID·当前公会-出刀统计')
    else:
        await bot.send(message, at_sender=True)


def parse_arguments(text):
    text = ''.join(str(text or '').split())
    view, day, refresh = 'quick', None, False
    if text.endswith('刷新'):
        text, refresh = text[:-2], True
    for prefix, mode in (('速查', 'quick'), ('详情', 'detail'), ('详细', 'detail'), ('缺刀', 'missing'), ('尾刀', 'tails')):
        if text.startswith(prefix):
            text, view = text[len(prefix):], mode
            break
    if text.lower() in ('day1', '1'):
        day = 0
    elif text.lower() in ('day2', '2'):
        day = 1
    elif text not in ('', '全部'):
        raise UnionDataError(USAGE)
    if view == 'detail' and day == 0:
        raise UnionDataError('Day1仅看Boss通关，不统计个人出刀。')
    if view in ('detail', 'missing', 'tails'):
        day = 1
    return view, day, refresh


def parse_request(text):
    text = ''.join(str(text or '').split())
    refresh = text.endswith('刷新')
    body = text[:-2] if refresh else text
    for prefix in ('详情', '详细'):
        if body.startswith(prefix):
            number = body[len(prefix):]
            if number and number.isascii() and number.isdigit():
                rank = int(number)
                if not 1 <= rank <= 1000:
                    raise UnionDataError('请输入大于0的成员伤害排名；不带数字查询本人。')
                return 'detail', 1, refresh, rank
    view, day, refresh = parse_arguments(text)
    return view, day, refresh, None


@sv_union.on_command(('出刀', '查刀', '联盟突袭', '突袭'))
async def nikke_union_cmd(bot, ev):
    client = None
    bind = None
    result = None
    forward_title = None
    try:
        view, day, refresh, target_rank = parse_request(ev.text)
        if not await get_policy().query_allowed(ev.group_id):
            result = '本群未开放妮姬查询，请联系群管理员或 Bot 主。'
        else:
            client, bind = await load_client(ev.user_id, ev.bot_id)
            if client is None:
                result = unavailable_message(bind)
            else:
                static, character_map = None, []
                if view == 'detail':
                    from ..nikke_resource.service import get_resources
                    resources = get_resources()
                    static = resources.load_static()
                    # Read only the existing database resource table. Never
                    # interpret tid ordering / suffixes as a character code.
                    character_map = resources._load_rows('character_id_map.json')
                context = await union_queries.query(client, bind, view=view, day=day, refresh=refresh,
                                                    static=static, character_map=character_map, target_rank=target_rank)
                from ..nikke_character.cache import panel_identity
                async def current_card():
                    current = await AliceBind.get_bind(ev.user_id, ev.bot_id)
                    policy = get_policy()
                    return (current is not None and union_queries.cache_key(current) == union_queries.cache_key(bind)
                            and union_queries.context_current(context, bind)
                            and policy.user_allowed(ev.user_id) and await policy.query_allowed(ev.group_id))
                context.update(_cache_scope=panel_identity(bind), _current=current_card)
                from .draw import draw_union
                from ..nikke_message import display_name
                forward_title = f'AliceUID·{display_name(context.get("guild_name"), "当前公会")}-出刀统计'
                result = MessageSegment.image(await draw_union(context))
    except (UnionDataError, UnionCooldown) as exc:
        result = str(exc)
    except NikkeLoginRequired:
        result = RELOGIN
    except NikkeApiError as exc:
        logger.warning(f'[AliceUID] union stage=query error_type={type(exc).__name__} code={exc.code}')
        result = RELOGIN if is_login_error(exc) else f'联盟查询失败，请稍后重试（{exc.code}）。'
    except Exception as exc:
        logger.error(f'[AliceUID] union stage=query error_type={type(exc).__name__}')
        result = '联盟查询失败，请稍后重试并请管理员检查日志。'
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                # Closure errors must not replace a successfully rendered result
                # or send an extra reply. Never log exception text / credentials.
                logger.error(f'[AliceUID] union stage=close error_type={type(exc).__name__}')
    if result is not None:
        if bind is None or client is None:
            await _send(bot, ev, result, title=forward_title)
        else:
            async with binding_lock(ev.user_id, ev.bot_id):
                current=await AliceBind.get_bind(ev.user_id,ev.bot_id)
                if current is not None and union_queries.cache_key(current)==union_queries.cache_key(bind):
                    if getattr(result, 'type', None) == 'image' and not await current_card():
                        return
                    caption = None
                    if getattr(result, 'type', None) == 'image':
                        from ..nikke_message import display_name
                        caption = (f'查询指挥官：{display_name(getattr(bind, "nickname", ""), "昵称未知")}'
                                   f'｜{client.region.label}｜UID：{getattr(bind, "uid", "") or "未知"}')
                        if context.get('view') == 'detail' and context.get('target_rank') is not None:
                            target = next(iter(context.get('details', [])), {})
                            caption += f'\n查询对象：伤害排名第{context["target_rank"]}名 · {display_name(target.get("name"), "未知成员")}'
                        if context.get('fetched_at'):
                            caption += '\n本次所用数据时间：'+context['fetched_at']+'；复用图片时保留图内原快照时间。'
                    await _send(bot,ev,result,title=forward_title,caption=caption)

