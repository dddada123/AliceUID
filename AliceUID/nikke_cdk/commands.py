"""Separate read-only query and parameter-aware redemption; Core registration below."""
from __future__ import annotations

import asyncio
from collections import Counter
from .models import PRODUCT, code_text, time_text, identity, clean
from . import api


def listing(report, prefix):
    lines = ['当前兑换码｜官方 + GameWith（已过滤历史及已知过期码）']
    for item in report['items']:
        sources = '、'.join('官方' if s == 'official' else 'GameWith' for s in item['sources'])
        lines.append(f"{item['code']}｜{sources}")
        if item.get('reward'):
            lines.append('报酬详情（GameWith）：' + clean(item['reward']))
        if item.get('expires_at'):
            lines.append('期限：' + time_text(item['expires_at'] - 1) + '（北京时间）')
    if not report['items']:
        lines.append('当前暂无可尝试兑换码')
    if report['checked_at'] is not None:
        lines.append('最近双源汇总：' + time_text(report['checked_at']) + '（北京时间）')
    lines.extend(report['warnings'])
    lines.append('实际是否可领取以官方结果为准')
    lines.append('来源：https://www.blablalink.com/cdk ｜ https://gamewith.jp/nikke/article/show/371014')
    return '\n'.join(lines)


def result_text(results):
    lines = ['兑换结果']
    for row in results:
        lines.append((row['code'] + '：' if row.get('code') else '') + row['result'])
        if row['status'] == 'success' and row.get('reward'):
            lines.append('报酬详情（GameWith）：' + clean(row['reward']))
    counts = Counter(r['status'] for r in results)
    lines.append('｜'.join(f'{label}{counts[key]}' for key, label in
        [('success', '成功'), ('claimed', '已领取'), ('skipped', '跳过'), ('failed', '失败'), ('uncertain', '未确认')]))
    return '\n'.join(lines)


def pages(text, limit=1800):
    for start in range(0, len(text), limit):
        yield text[start:start + limit]


class Commands:
    def __init__(self, catalog, redemptions, *, load, allowed, current, enabled, prefix):
        self.catalog, self.redemptions = catalog, redemptions
        self.load, self.allowed, self.current, self.enabled, self.prefix = load, allowed, current, enabled, prefix
        self.tasks = set()

    async def send(self, bot, ev, text, bind=None):
        for page in pages(text):
            if not await self.allowed(ev) or (bind is not None and not await self.current(ev, bind)):
                return False
            if await bot.send(page, at_sender=True) is False:
                return False
        return True

    async def handle(self, bot, ev, mode, argument=''):
        if not await self.allowed(ev):
            return
        if mode == 'refresh' and (type(getattr(ev, 'user_pm', None)) is not int or ev.user_pm != 0):
            await self.send(bot, ev, '仅Bot主可以刷新兑换码缓存')
            return
        argument = (argument or '').strip()
        if mode != 'redeem' and argument:
            await self.send(bot, ev, '此命令无需附加参数')
            return
        if mode == 'redeem' and argument:
            try:
                code = code_text(argument)
            except ValueError as exc:
                await self.send(bot, ev, str(exc))
                return
            report = self.catalog.report()
            cached = next((r for r in report['items'] if r['code'] == code), None)
            items = [cached or dict(code=code, sources=[], reward=self.catalog.reward(code))]
        else:
            report = await self.catalog.ensure(first=mode == 'redeem', force=mode == 'refresh')
            items = report['items']
            if mode == 'refresh':
                state = '双源检查完成' if report['complete'] else '双源汇总未全部成功'
                action = {'cached':'使用缓存', 'refreshed':'已执行检查', 'joined':'已等待同一更新',
                          'busy':'其他更新仍在进行', 'cooldown':'来源请求暂时冷却'}.get(report['action'], '状态待确认')
                source_lines = ['官方' + ('：检查未完成' if 'official' in report['errors'] else '：已有可用快照'),
                                'GameWith' + ('：检查未完成' if 'gamewith' in report['errors'] else '：已有可用快照')]
                await self.send(bot, ev, f"{state}｜当前候选{len(items)}个｜{action}\n"
                                + '\n'.join(source_lines + report['warnings']) + '\n过期标记和本人领取记录已保留')
                return
            if mode == 'query' or mode == 'redeem':
                if not await self.send(bot, ev, listing(report, self.prefix())):
                    return
            if mode == 'query':
                return  # This branch never loads credentials or calls a private endpoint.
            if mode == 'third':
                items = [r for r in items if 'gamewith' in r['sources']]
        if mode == 'redeem' and not items:
            return
        client, bind = await self.load(ev)
        if client is None:
            if bind is not None:
                await self.send(bot, ev, f'绑定凭据不可用，本次未兑换；请{self.prefix()}重新登录')
            elif mode != 'redeem' or argument:
                await self.send(bot, ev, f'请先{self.prefix()}登录；无需绑定查看码可用{self.prefix()}查询兑换码')
            return
        try:
            if not self.enabled():
                await self.send(bot, ev, 'CDK兑换尚未由Bot主开启；列表与只读查询仍可使用', bind)
                return
            if not await self.current(ev, bind):
                return
            if mode == 'official':
                await self.redemptions.role_matches(client, bind)
                rows = await api.recommendation(client)
                items = []
                for row in rows:
                    code = code_text(row.get('cdk'))
                    if type(row.get('status')) is int and row['status'] == 1:
                        self.redemptions.store.record(identity(bind), code, 'claimed', '官网确认本人已领取', self.catalog.clock())
                    elif type(row.get('status')) is not int or row['status'] != 0:
                        continue
                    items.append(dict(code=code, reward=self.catalog.reward(code), sources=['official']))
            if not items:
                await self.send(bot, ev, '当前来源暂无待兑换的有效码', bind)
                return
            if not await self.send(bot, ev, f'将为当前绑定角色尝试处理{len(items)}个码，已领取或已知过期项自动跳过', bind):
                return
            # Keep the client alive in the retained worker; delivery failure must not cause a new submit.
            task = asyncio.create_task(self._worker(bot, ev, client, bind, items))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            client = None
        finally:
            if client is not None:
                await client.close()

    async def _worker(self, bot, ev, client, bind, items):
        try:
            results = await self.redemptions.run(client, bind, items,
                current=lambda: self.current(ev, bind), enabled=self.enabled)
            await self.send(bot, ev, result_text(results), bind)
        except Exception:
            try:
                await self.send(bot, ev, '兑换任务中断；提交记录已保留，未自动重试，请稍后核对官方记录', bind)
            except Exception:
                pass
        finally:
            await client.close()


def register(commands):
    from gsuid_core.sv import SV
    user = SV('妮姬兑换码', pm=6, priority=3)
    admin = SV('妮姬兑换码维护', pm=0, priority=2)

    async def invoke(bot, ev, mode):
        try:
            await commands.handle(bot, ev, mode, ev.text or '')
        except Exception:
            await commands.send(bot, ev, '兑换码请求未完成，请稍后重试；未自动重复提交')

    @user.on_command('兑换码')
    async def redeem(bot, ev):
        await invoke(bot, ev, 'redeem')

    @user.on_command('查询兑换码')
    async def query(bot, ev):
        await invoke(bot, ev, 'query')

    @user.on_command('兑换官方兑换码')
    async def official(bot, ev):
        await invoke(bot, ev, 'official')

    @user.on_command('第三方兑换码')
    async def third(bot, ev):
        await invoke(bot, ev, 'third')

    @admin.on_command('刷新兑换码')
    async def refresh(bot, ev):
        await invoke(bot, ev, 'refresh')
    return user, admin
