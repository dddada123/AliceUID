"""Explicit per-conversation opt-in. Only a newly enabled session gets a card."""
from decimal import Decimal
from gsuid_core.sv import SV
from gsuid_core.segment import MessageSegment
from gsuid_core.logger import logger
from ..nikke_commands import command_prefix
from ..nikke_permissions.runtime import get_policy
from ..nikke_user.models import AliceBind
from ..nikke_user.service import binding_lock
from ..nikke_user.auth_state import unavailable_message, expired, known_invalid
from .planner import route_from_event, percent, moment
from .runtime import get_runtime, allowed

sv_harvest = SV('妮姬收菜提醒', pm=6, priority=3)


async def permitted(ev):
    policy = get_policy()
    return policy.user_allowed(ev.user_id) and await policy.query_allowed(getattr(ev, 'group_id', None))


async def execute(bot, ev, action):
    if not await permitted(ev):
        await bot.send('当前未开放收菜提醒，请联系管理员。', at_sender=True)
        return
    try:
        route = route_from_event(ev)
        svc = get_runtime()
        value = (ev.text or '').strip()
        if action != 'quiet' and value:
            raise ValueError('本指令不接受额外参数。')
        if action == 'enable':
            bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
            if bind is None or expired(bind) or known_invalid(bind):
                raise ValueError(unavailable_message(bind))
            acc, sub, image, created = await svc.enable(route, bind)
            where = '本群' if route['kind'] == 'group' else '当前私聊'
            if not created:
                text = f'[AliceUID]收菜提醒已开启\n指挥官，{where}已开启，无需重复操作。'
            else:
                snap = acc['snapshot']
                text = (f'[AliceUID]收菜提醒已开启\n指挥官，已在{where}开启您的收菜提醒。\n'
                        f'最近查询容量（{moment(snap["at"], svc.clock())}）：{percent(snap)}%。\n'
                        + ('资源保管箱已达到MAX。\n' if Decimal(snap['p']) == 100 else
                           f'预计{moment(snap["t90"], svc.clock())}达到90%，{moment(snap["full"], svc.clock())}达到MAX。\n')
                        + f'收菜提醒免打扰时段：{sub["quiet"] or "关闭"}（北京时间）。\n'
                        + '连续两天23点检查均为MAX时，将自动关闭该账号的全部收菜提醒。')
            async with svc.send_lock:
                async with binding_lock(ev.user_id, ev.bot_id):
                    current = svc.store.sub(sub['id'])
                    if not current or not current['enabled'] or current['generation'] != sub['generation'] or not await allowed(current, acc):
                        return
                    message = [MessageSegment.image(image), text] if image is not None else text
                    await bot.send(message, at_sender=route['kind'] == 'group')
            return
        if action == 'disable':
            sub = await svc.disable(route['id'])
            where = '本群' if route['kind'] == 'group' else '当前私聊'
            text = f'[AliceUID]收菜提醒已关闭\n指挥官，已关闭{where}中的收菜提醒，您在其他会话中开启的提醒不受影响。'
            if sub and not svc.store.subs(sub['account']):
                text += '\n该账号已无开启的提醒会话，后台检查已停止。'
        elif action == 'quiet':
            period = await svc.set_quiet(route['id'], value)
            text = f'[AliceUID]收菜免打扰已设置\n当前会话：{period or "关闭"}（北京时间）。仅影响收菜提醒。'
        else:
            sub = svc.store.sub(route['id'])
            if not sub:
                text = f'[AliceUID]收菜提醒状态\n当前会话未开启。发送“{command_prefix()}开启收菜提醒”开启。'
            else:
                acc = svc.store.account(sub['account'])
                reasons = {'two_full_nights':'连续两天23点检查均为MAX，已自动关闭', 'binding_changed':'绑定已变更，请重新开启',
                           'manual':'本人已关闭', 'initialization_failed':'初始化未完成，请重新开启'}
                text = (f'[AliceUID]收菜提醒状态\n当前会话：{"开启" if sub["enabled"] else "关闭"}。\n'
                        f'免打扰：{sub["quiet"] or "关闭"}（北京时间）。\n'
                        + reasons.get(sub.get('reason'), '') )
                if acc and acc.get('snapshot'):
                    snap = acc['snapshot']
                    text += f'\n最近查询：{moment(snap["at"], svc.clock())}，容量{percent(snap)}%。'
                    text += f'\n预计MAX：{moment(snap["full"], svc.clock())}。'
                if acc and sub['enabled']:
                    phases = {'WAIT_90':'等待90%检查','WAIT_MAX':'仅等待一次MAX检查','WAIT_REARM':'等待23点静默恢复检查','PAUSED':'已暂停，请重新登录或开启','INITIALIZING':'初始化中'}
                    text += '\n当前阶段：'+phases.get(acc['phase'], acc['phase'])+'。'
                    if acc.get('due') is not None:
                        text += f'\n下次检查：{moment(acc["due"], svc.clock())}。'
                if acc and acc.get('error'):
                    text += '\n最近检查未成功，等待下一次合法检查或重新开启。'
        await bot.send(text, at_sender=route['kind'] == 'group')
    except Exception as exc:
        logger.warning(f'[AliceUID] harvest command error_type={type(exc).__name__}')
        text = str(exc) if isinstance(exc, ValueError) else '收菜提醒操作未完成，请稍后重试或查看状态。'
        if await permitted(ev):
            await bot.send(text, at_sender=bool(getattr(ev, 'group_id', None)))


@sv_harvest.on_command('开启收菜提醒')
async def enable_cmd(bot, ev):
    await execute(bot, ev, 'enable')


@sv_harvest.on_command('关闭收菜提醒')
async def disable_cmd(bot, ev):
    await execute(bot, ev, 'disable')


@sv_harvest.on_command('收菜提醒状态')
async def status_cmd(bot, ev):
    await execute(bot, ev, 'status')


@sv_harvest.on_command('收菜免打扰')
async def quiet_cmd(bot, ev):
    await execute(bot, ev, 'quiet')
