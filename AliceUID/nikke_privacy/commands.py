"""Explicit website privacy commands; old local ranking marks stay separate."""
from gsuid_core.sv import SV
from ..nikke_commands import command_prefix
from ..nikke_permissions.runtime import get_policy
from ..nikke_user.service import load_client, binding_lock
from ..nikke_user.models import AliceBind
from ..nikke_user.auth_state import unavailable_message
from ..nikke_status.service import binding_key
from ..nikke_logs.store import record_failure, request_scope
from .service import get_service, self_share, account_key, LABELS, recover_pending

sv_privacy = SV('官网妮姬隐私', priority=3)


async def execute(bot, ev, value=None):
    policy = get_policy()
    if not policy.user_allowed(ev.user_id) or not await policy.query_allowed(getattr(ev, 'group_id', None)):
        return
    client = None
    with request_scope('官网妮姬隐私'):
        try:
            client, bind = await load_client(ev.user_id, ev.bot_id)
            if client is None:
                await bot.send(unavailable_message(bind), at_sender=True)
                return
            async with binding_lock(ev.user_id, ev.bot_id):
                current = await AliceBind.get_bind(ev.user_id, ev.bot_id)
                if (current is None or binding_key(current) != binding_key(bind)
                        or not policy.user_allowed(ev.user_id)
                        or not await policy.query_allowed(getattr(ev, 'group_id', None))):
                    return
                share = await self_share(client, bind)
                service = get_service()
                if value is None:
                    settings = await service.read(client, share)
                    pending = service.pending(account_key(bind))
                    text = '官网妮姬资料：' + LABELS[settings['show_nikke_info']] + '。'
                    if pending:
                        text += ('\n临时公开任务仍在执行。' if pending['job'] in service.running else
                                 '\n隐私恢复尚未确认，请到官网检查；可发送'+command_prefix()+'妮姬隐藏。')
                else:
                    await service.manual(client, bind, share, value)
                    text = '已将Blablalink「显示我的妮姬」设为' + LABELS[value] + '；持续生效。'
                await bot.send(text, at_sender=True)
        except Exception as exc:
            record_failure('官网妮姬隐私', '命令', exc)
            await bot.send('官网隐私读取或修改未确认，请稍后用'+command_prefix()+'妮姬公开状态检查，或到官网设置页核对。', at_sender=True)
        finally:
            if client is not None:
                await client.close()


@sv_privacy.on_fullmatch(('妮姬公开', '妮姬公開'))
async def public(bot, ev):
    await execute(bot, ev, 1)


@sv_privacy.on_fullmatch(('妮姬隐藏', '妮姬隱藏'))
async def hidden(bot, ev):
    await execute(bot, ev, 0)


@sv_privacy.on_fullmatch(('妮姬公开状态', '妮姬公開狀態'))
async def status(bot, ev):
    await execute(bot, ev)


def setup(scheduler=None):
    if scheduler is None:
        from gsuid_core.aps import scheduler
    scheduler.add_job(recover_pending, 'interval', seconds=60, id='aliceuid-privacy-recovery',
                      replace_existing=True, max_instances=1, coalesce=True)
