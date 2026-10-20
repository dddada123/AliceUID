"""Bot-owner command: fast acknowledgement and retained background task."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from .service import get_database

HELP = (f'命令：{command_prefix()}数据库更新（仅 Bot 主）\n'
        '后台增量检查公开角色资料、装备/技能等已配置静态表及图库，无需账号、Token 或 Cookie。\n'
        '默认每周五北京时间 02:33 自动运行。NIKKE 通常约 21 天更新一次，周检用于发现变化。\n'
        '已有有效图片不按 TTL 重下；默认补公开清单的基础及皮肤头像（SI）、半身像（MI）和完整立绘。\n'
        'DatabaseIncludeSkins=False可只补基础图；公共资源清单不代表账号已拥有，展示仍依据本人接口报告。\n'
        '首装无需打包大图库；默认每批 40 项、128 MiB 下载、图库预算 2048 MiB；后台连续续传最多 30 分钟，'
        '剩余队列持久保存，下次周检或再次命令续跑。大量立绘补全可能较慢，未完成会明确显示剩余项。\n'
        '公开请求间隔默认 2 秒（至少 1.5 秒）；403/429/要求登录停止本批并冷却，不使用用户凭据。\n'
        f'{command_prefix()}数据库更新 状态：查看最近结果；{command_prefix()}数据库更新 帮助：查看说明。')


def summary(report):
    status = report.get('status')
    if status == 'busy':
        return '数据库更新正在后台运行，请稍后查看状态。'
    scope = '含可选皮肤变体的图库' if report.get('include_skins') else '基础图库'
    label = {'complete': f'数据库检查与当前清单{scope}补全完成',
             'incomplete': '数据库更新尚未全部完成',
             'cooldown': '数据库更新处于失败冷却',
             'error': '数据库更新失败'}.get(status, '数据库任务状态')
    text = (f"{label}。\n本次成功图片：{report.get('downloaded', 0)}；失败：{report.get('failed', 0)}；"
            f"待处理：{report.get('pending', 0)}；下载：{report.get('bytes', 0) / 1024**2:.2f} MiB。")
    changes = report.get('changes', {})
    if changes:
        text += f"\n角色新增 {changes.get('added', 0)}、变化 {changes.get('changed', 0)}、移出清单 {changes.get('removed', 0)}（旧资源保留）。"
    if report.get('error'):
        text += '\n' + report['error']
    if report.get('pending'):
        text += '\n剩余任务已保存，可在冷却结束后再次运行或等待下次周检。'
    return text


class DatabaseCommands:
    def __init__(self, service):
        self.service = service

    async def handle(self, bot, ev):
        text = (getattr(ev, 'text', '') or '').strip()
        if text in {'帮助', 'help'}:
            await bot.send(HELP, at_sender=True)
            return
        if text in {'状态', 'status'}:
            if self.service.running():
                pending = len(self.service.state()['queue'])
                await bot.send(f'数据库更新正在后台运行；当前持久队列待处理 {pending} 项（静态表检查阶段尚未生成新队列）；进度与最终摘要会写入日志。', at_sender=True)
            else:
                report = self.service.state().get('last_report')
                await bot.send(summary(report) if report else '尚无数据库维护记录。' + '\n' + HELP, at_sender=True)
            return
        if text:
            await bot.send(HELP, at_sender=True)
            return
        if self.service.running():
            await bot.send('数据库更新正在后台运行，本次请求已去重。', at_sender=True)
            return

        async def done(report):
            await bot.send(summary(report), at_sender=True)

        task = self.service.start(reason='manual', done=done)
        await bot.send('数据库增量更新已在后台启动；首装立绘补全较慢，完成或中止后会回复摘要。'
                       if task is not None else '数据库更新正在后台运行，本次请求已去重。', at_sender=True)


_sv = None


def setup(config_getter=None):
    global _sv
    service = get_database(config_getter)
    if _sv is not None:
        return _sv
    from gsuid_core.sv import SV
    _sv = SV('妮姬数据库维护', pm=0, priority=3)
    commands = DatabaseCommands(service)

    @_sv.on_command('数据库更新')
    async def database_update(bot, ev):
        await commands.handle(bot, ev)

    return _sv
