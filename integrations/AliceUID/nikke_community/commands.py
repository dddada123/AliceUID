"""Bot adapter with explicit dependency injection; importing registers nothing."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .api import CommunityError
from .service import CommunityService
from .cycle import cycle_label
from .schedule import DEFAULT, normalized_time
from .messages import result_message


@dataclass(frozen=True)
class Binding:
    actor_id: str
    bot_id: str
    revision: str
    client: Any


class CommunityCommands:
    def __init__(self, service: CommunityService, load_binding: Callable[..., Awaitable[Binding | None]],
                 enabled: Callable[[], bool] = lambda: False, *, sign_time=lambda: DEFAULT, group_report=None, binding_hint=None):
        self.service, self.load_binding, self.enabled = service, load_binding, enabled
        self.sign_time, self.group_report = sign_time, group_report
        self.binding_hint = binding_hint
        self.local_control = None

    async def handle(self, actor_id: str, bot_id: str, argument: str) -> str:
        option = argument.strip()
        valid = {"开启", "开", "关闭", "关", "状态", "点赞开启", "点赞关闭"}
        if option not in valid:
            return (f"{command_prefix()}自动社区 开启/关闭/状态；{command_prefix()}自动社区 点赞开启/点赞关闭。\n"
                    "开启即授权当前绑定账号每日签到及浏览；点赞需另行开启；不自动评论。\n"
                    "请求与换号采用后台设置的随机间隔；每日最多30请求、签到1次、浏览5帖、点赞5帖；连续三个签到周期失败后自动关闭。")
        if option in {'关闭','关','状态'} and self.local_control is not None:
            try:
                return await self.local_control(str(actor_id),str(bot_id),option)
            except Exception:
                return '自动社区本地状态读取或保存失败，请稍后重试。'
        binding = await self.load_binding(str(actor_id), str(bot_id))
        if binding is None:
            return await self.binding_hint(actor_id,bot_id) if self.binding_hint else "请先登录并绑定账号。"
        client = binding.client
        try:
            if str(binding.actor_id) != str(actor_id) or str(binding.bot_id) != str(bot_id):
                return "仅能操作本人当前绑定账号。"
            state = self.service.status(client, actor_id, bot_id, binding.revision)
            if option == "状态":
                return (f"自动社区：{'开启' if state['enabled'] else '关闭'}\n"
                        f"连续失败：{state.get('fail_count',0)}/3个签到周期\n"
                        f"系统停用：{'连续三天失败' if state.get('auto_disabled') else '无'}\n"
                        f"点赞：{'开启' if state['likes'] else '关闭'}\n"
                        f"暂停：{state['paused'] or '无'}\n"
                        f"每日自动时间：北京时间{normalized_time(self.sign_time())}\n"
                        f"上次处理周期（北京时间08点起）：{state['last_day'] or '无'}\n"
                        f"全局紧急暂停：{'否' if self.enabled() else '是'}\n"
                        f"命令：{command_prefix()}自动社区 开启/关闭/状态；点赞开启/点赞关闭。")
            if option in {"关闭", "关"}:
                self.service.configure(client, actor_id, bot_id, binding.revision, enabled=False)
                return "自动社区已关闭（签到、浏览及点赞均关闭）。"
            if option == '点赞关闭':
                self.service.disable_likes(client, actor_id, bot_id, binding.revision)
                return '自动点赞已关闭；已有暂停状态保持不变。'
            if not self.enabled():
                return "社区模块处于全局紧急暂停，请联系管理员。"
            if option in {"开启", "开"}:
                self.service.configure(client, actor_id, bot_id, binding.revision, enabled=True)
                return (f"已授权当前账号每日自动签到及浏览；每天北京时间{normalized_time(self.sign_time())}开始按账号依次执行。"
                        "社区周期从08:00开始；点赞关闭，不自动评论。短期异常后台有限重试，连续三个签到周期失败后自动关闭。")
            if not state["enabled"]:
                return f"请先发送 {command_prefix()}自动社区 开启，授权当前账号。"
            if state["paused"]:
                return f"任务已暂停，请人工检查后发送 {command_prefix()}自动社区 开启。"
            self.service.configure(client, actor_id, bot_id, binding.revision, enabled=True,
                                   likes=option == "点赞开启")
            return "已授权每日最多点赞5帖。" if option == "点赞开启" else "自动点赞已关闭。"
        except CommunityError as exc:
            return str(exc)
        finally:
            await client.close()

    async def execute(self, actor_id, bot_id, *, full=False, notify=None):
        """Immediate owned run, with the live daily schedule in the final reply."""
        binding = await self.load_binding(str(actor_id), str(bot_id))
        if binding is None:
            return await self.binding_hint(actor_id,bot_id) if self.binding_hint else f'请先发送 {command_prefix()}登录，绑定本人的账号。'
        client = binding.client
        configured = False
        def finish(text):
            if not full or not configured:
                return text
            state = self.service.status(client,actor_id,bot_id,binding.revision)
            at = normalized_time(self.sign_time())
            if not state['enabled']:
                return text + '\n自动签到授权已变更，请查看自动社区状态。'
            if state['paused'] or not self.enabled() or not self.service.user_allowed(str(actor_id)):
                return text + f'\n⏰ 自动签到时间为北京时间{at}；当前任务暂停或权限受限，恢复后生效。'
            return text + f'\n⏰ 此后每天北京时间{at}开始自动签到，按账号依次执行，请稍候完成。'
        try:
            if (str(binding.actor_id),str(binding.bot_id)) != (str(actor_id),str(bot_id)):
                return '仅能操作本人当前绑定账号。'
            if not self.enabled() or not self.service.user_allowed(str(actor_id)):
                return '社区任务当前暂停或无权使用，请联系管理员。'
            day = self.service.prepare_cycle()
            account = self.service.identity(client)
            owner = self.service.owner(actor_id,bot_id,binding.revision)
            stored = self.service.store.state(account)
            if full:
                self.service.configure(client,actor_id,bot_id,binding.revision,enabled=True,likes=True)
                configured = True
            elif stored.get('owner') != owner:
                self.service.configure(client,actor_id,bot_id,binding.revision,enabled=False)
            state = self.service.status(client,actor_id,bot_id,binding.revision)
            prefix = '已为你本人开启全量签到（签到、浏览及点赞），不影响其他用户。\n' if full else ''
            if self.service.store.signin_status(account,owner,day)['confirmed']:
                return finish(prefix + '本周期已签到✅ 本次未重复请求。')
            if state['paused']:
                return finish('社区任务已暂停：' + state['paused'] + '。请人工检查后重新开启。')
            if notify:
                await notify(prefix + '签到任务已受理⏳ 正在排队或执行，完成后会返回结果，请勿重复发送。')
            result = await self.service.run(client,actor_id,bot_id,binding.revision,
                                            manual=True,signin_only=not bool(state['likes'] and state['enabled']))
            if self.service.binding_current is not None and not await self.service.binding_current(actor_id,bot_id,binding.revision):
                return None
            kind = result['result']
            if kind in ('completed', 'paused', 'cycle_changed', 'unconfirmed', 'failed', 'retry_pending'):
                return finish(result_message(result))
            if kind == 'daily_limit':
                return finish('本周期请求预算已用尽，未继续发送签到或互动请求。')
            if kind == 'already_completed':
                return finish('社区确认本周期已签到✅ 本次未继续浏览、点赞或查询金币。')
            return finish('本周期已执行或已有任务正在处理，本次未重复请求。')
        except CommunityError as exc:
            return finish(str(exc))
        finally:
            await client.close()


def register_commands(commands: CommunityCommands):
    """Call once from plugin integration, after configuring the shared service."""
    from gsuid_core.sv import SV

    sv = SV("妮姬社区积分", pm=6, priority=3)

    @sv.on_command("自动社区")
    async def community_command(bot, ev):
        reply = await commands.handle(str(ev.user_id), str(ev.bot_id), ev.text or "状态")
        await bot.send(reply, at_sender=True)

    async def immediate(bot, ev, full):
        if (ev.text or '').strip():
            await bot.send(f'用法：{command_prefix()}签到 / {command_prefix()}开启全量签到（仅操作本人账号）。',at_sender=True)
            return
        reply = await commands.execute(str(ev.user_id),str(ev.bot_id),full=full,
                                       notify=lambda text: bot.send(text,at_sender=True))
        if reply is not None:
            await bot.send(reply,at_sender=True)

    @sv.on_fullmatch('签到')
    async def immediate_signin(bot, ev):
        await immediate(bot,ev,False)

    @sv.on_command('开启全量签到')
    async def enable_full_signin(bot, ev):
        await immediate(bot,ev,True)

    admin = SV("妮姬签到记录查询", pm=0, priority=2)

    @admin.on_command('签到查询')
    async def signin_query(bot, ev):
        if type(getattr(ev, 'user_pm', None)) is not int or ev.user_pm != 0:
            await bot.send('仅Bot主可以查询本群签到记录。',at_sender=True)
            return
        if not getattr(ev, 'group_id', None):
            await bot.send(f'请在群内使用 {command_prefix()}签到查询。',at_sender=True)
            return
        arg = (ev.text or '').strip()
        if arg and (len(arg)>5 or not arg.isascii() or not arg.isdecimal() or not 1<=int(arg)<=10000):
            await bot.send(f'用法：{command_prefix()}签到查询 [页码]，仅查询当前群的本插件记录。',at_sender=True)
            return
        if commands.group_report is None:
            await bot.send('本地签到记录查询尚未初始化。',at_sender=True)
            return
        try:
            reply = await commands.group_report(bot,ev,int(arg or '1'))
        except Exception:
            reply = '本地签到记录读取失败，请稍后重试或检查日志。'
        await bot.send(reply,at_sender=True)

    return sv
