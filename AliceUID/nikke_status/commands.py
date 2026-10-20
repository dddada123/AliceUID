"""Only the invoking user's account, with binding and policy rechecked at send."""
from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..nikke_api.client import NikkeApiError,NikkeLoginRequired
from ..nikke_permissions.runtime import get_policy
from ..nikke_user.models import AliceBind
from ..nikke_user.service import load_client,binding_lock
from ..nikke_user.auth_state import RELOGIN, is_login_error, unavailable_message
from ..nikke_union.service import union_queries,UnionCooldown
from ..nikke_union.builder import UnionDataError
from ..nikke_roster.service import RosterCooldown
from .builder import StatusDataError
from .service import resource_status,binding_key

sv_status=SV('妮姬资源与会战状态',pm=6,priority=3)


async def _allowed(ev):
    policy=get_policy()
    return policy.user_allowed(ev.user_id) and await policy.query_allowed(ev.group_id)


async def _current(ev,bind):
    current=await AliceBind.get_bind(ev.user_id,ev.bot_id)
    return current is not None and binding_key(current)==binding_key(bind) and await _allowed(ev)


async def _query(bot,ev,kind):
    client=None
    result=None
    bind=None
    try:
        text=(ev.text or '').strip()
        if text not in ('','刷新'):
            result=f'用法：nk{"资源查询" if kind=="resources" else "会战血量"} [刷新]。'
        elif not await _allowed(ev):
            result='当前未开放妮姬查询，请联系管理员。'
        else:
            client,bind=await load_client(ev.user_id,ev.bot_id)
            if client is None:
                result=unavailable_message(bind)
            else:
                if not await _current(ev,bind):return
                if kind=='resources':
                    prepared=await resource_status.prepare_image(client,bind,refresh=text=='刷新',
                        actor=(ev.user_id,ev.bot_id),still_current=lambda:_current(ev,bind))
                    result=[MessageSegment.image(prepared.image),
                            '成功出图后5分钟内复用缓存图片；没有可用缓存图时重新同步并生成。']
                else:
                    context=await union_queries.query_bosses(client,bind,refresh=text=='刷新')
                    if not await _current(ev,bind):return
                    from .draw import draw_status
                    result=MessageSegment.image(await draw_status(context,owner_key=(str(ev.user_id),str(ev.bot_id),*binding_key(bind))))
    except NikkeLoginRequired:
        result=RELOGIN
    except (StatusDataError,UnionDataError,UnionCooldown,RosterCooldown) as exc:
        result=str(exc)
    except NikkeApiError as exc:
        result=RELOGIN if is_login_error(exc) else f'社区查询未完成，请稍后重试（{exc.code}）；本次未用旧数据替代。'
        logger.warning(f'[AliceUID] status query error_type={type(exc).__name__} code={exc.code}')
    except Exception as exc:
        result='查询失败，请稍后重试并请管理员检查日志。'
        logger.error(f'[AliceUID] status query error_type={type(exc).__name__}')
    finally:
        if client is not None:
            try:await client.close()
            except Exception as exc:logger.warning(f'[AliceUID] status close error_type={type(exc).__name__}')
    if result is not None and await _allowed(ev):
        if bind is None:
            await bot.send(result,at_sender=True)
        else:
            async with binding_lock(ev.user_id,ev.bot_id):
                if await _current(ev,bind):await bot.send(result,at_sender=True)


@sv_status.on_command('会战血量')
async def nikke_boss_health_cmd(bot,ev):
    await _query(bot,ev,'bosses')


@sv_status.on_command('资源查询')
async def nikke_resource_status_cmd(bot,ev):
    await _query(bot,ev,'resources')
