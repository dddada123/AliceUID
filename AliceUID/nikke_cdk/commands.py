"""Separate read-only query and parameter-aware redemption; Core registration below."""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from .models import PRODUCT, SHANGHAI, code_text, time_text, identity, clean, retirement_at, code_key
from . import api


def listing(report, prefix):
    blocks = ['当前兑换码｜官方 + GameWith + 成员补充（已过滤历史及已知停用码）']
    for item in report['items']:
        labels = {'official': '官方', 'gamewith': 'GameWith', 'member': '成员补充'}
        sources = '、'.join(labels[s] for s in item['sources'] if s in labels)
        lines = [f"兑换码：{item['code']}", '来源：' + sources]
        if item.get('reward'):
            lines.extend(['报酬详情（GameWith）：', clean(item['reward'])])
        if item.get('expires_at'):
            official = item.get('expiry_source') == 'official'
            label = '官方期限：' if official else '第三方期限：'
            stamp = lambda value: datetime.fromtimestamp(value, SHANGHAI).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(label + stamp(item['expires_at'] - (0 if official else 1)) + '（北京时间）')
            lines.append('库存移出：' + stamp(retirement_at(item)) + '（期限后5分钟）')
        blocks.append('\n'.join(lines))
    lines = []
    if not report['items']:
        lines.append('当前暂无可尝试兑换码')
    if report['checked_at'] is not None:
        lines.append('最近双源汇总：' + time_text(report['checked_at']) + '（北京时间）')
    lines.extend(report['warnings'])
    lines.append('实际是否可领取以官方结果为准')
    lines.append('来源：https://www.blablalink.com/cdk ｜ https://gamewith.jp/nikke/article/show/371014')
    blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def quick_listing(report, prefix):
    lines = ['[AliceUID]兑换码速查']
    lines.extend(item['code'] for item in report['items'])
    if not report['items']:
        lines.append('当前暂无可用兑换码' if report.get('complete') else '暂时没有可用兑换码，请稍后再查')
    lines.append(f'如已绑定账号到AliceUID可输入“{prefix}兑换码”命令尝试进行兑换。')
    return '\n'.join(lines)


def result_text(results):
    lines = ['兑换结果']
    for row in results:
        label = {'success': '兑换成功✅', 'claimed': '已领取✅'}.get(row['status'], row['result'])
        lines.append((row['code'] + '：' if row.get('code') else '') + label)
        if row.get('pool_status') in ('added', 'existing'):
            lines.append('共享缓存：已验证并加入，同码自动合并' if row['pool_status'] == 'added' else '共享缓存：同码已收录，保留原记录')
        elif row.get('pool_status') == 'blocked':
            lines.append('共享缓存：已存在停用标记，未重新入池')
    counts = Counter(r['status'] for r in results)
    lines.append('｜'.join(f'{label}{counts[key]}' for key, label in
        [('success', '成功'), ('claimed', '已领取'), ('skipped', '跳过'), ('failed', '失败'), ('uncertain', '未确认')]))
    return '\n'.join(lines)


def detailed_result(results):
    """Only the displayed summary length can opt a batch into forwarding."""
    text = result_text(results)
    return len(text) > 600 or len(text.splitlines()) > 12


def detail_header(kind, bind):
    from ..nikke_api.client import REGIONS
    def label(value, fallback):
        return ' '.join(clean(str(value or ''), 100).split()) or fallback
    region = REGIONS.get(getattr(bind, 'area_id', None))
    name = label(getattr(bind, 'nickname', ''), '未知指挥官' if bind else '未绑定')
    area = region.label if region else ('未知区服' if bind else '未绑定')
    uid = label(getattr(bind, 'uid', ''), '未取得' if bind else '未绑定')
    return f'[AliceUID]{kind}\n指挥官：{name}\n区服：{area}｜UID：{uid}'


class _DeliveryBot:
    """Recheck owner/binding before both the forward and every fallback page."""
    def __init__(self, bot, commands, ev, bind):
        self._bot, self._commands, self._ev, self._bind = bot, commands, ev, bind

    def __getattr__(self, name):
        return getattr(self._bot, name)

    async def send(self, message, **kwargs):
        payloads = pages('\n\n'.join(message)) if isinstance(message, list) and all(
            isinstance(item, str) for item in message) else [message]
        for payload in payloads:
            if not await self._commands.allowed(self._ev) or (
                self._bind is not None and not await self._commands.current(self._ev, self._bind)
            ):
                return False
            result = await self._bot.send(payload, **kwargs)
            if result is False:
                return False
        return result


def pages(text, limit=1800):
    """Prefer whole code blocks, then whole lines; only split an oversized line."""
    if limit < 1:
        raise ValueError('message page limit must be positive')
    pending = ''
    for block in text.split('\n\n'):
        if len(block) > limit:
            if pending:
                yield pending
                pending = ''
            for line in block.split('\n'):
                if len(line) > limit:
                    if pending:
                        yield pending
                        pending = ''
                    while len(line) > limit:
                        yield line[:limit]
                        line = line[limit:]
                if not line:
                    continue
                joined = pending + ('\n' if pending else '') + line
                if len(joined) > limit:
                    yield pending
                    pending = line
                else:
                    pending = joined
            if pending:
                yield pending
                pending = ''
            continue
        joined = pending + ('\n\n' if pending else '') + block
        if len(joined) > limit:
            yield pending
            pending = block
        else:
            pending = joined
    if pending:
        yield pending


class Commands:
    def __init__(self, catalog, redemptions, *, load, allowed, current, enabled, prefix,
                 forward=None, profile=None, result_forward_enabled=lambda: False):
        self.catalog, self.redemptions = catalog, redemptions
        self.load, self.allowed, self.current, self.enabled, self.prefix = load, allowed, current, enabled, prefix
        self.tasks = set()
        self.forward, self.profile = forward, profile
        self.result_forward_enabled = result_forward_enabled

    async def send_detail(self, bot, ev, text, kind, bind=None, *, config_key='AliceUID_CDKForward'):
        if self.forward is None:
            return await self.send(bot, ev, text, bind)
        if not await self.allowed(ev):
            return False
        if bind is None and self.profile is not None:
            bind = await self.profile(ev)  # Local binding only, never credentials/API.
        message = [detail_header(kind, bind), *pages(text)]
        result = await self.forward(_DeliveryBot(bot, self, ev, bind), ev, message,
                                    config_key=config_key)
        return result is not False

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
        if mode == 'redeem' and argument == '速查':
            mode, argument = 'quick', ''
        if mode not in ('redeem', 'add') and argument:
            await self.send(bot, ev, '此命令无需附加参数')
            return
        if mode == 'add' and not argument:
            await self.send(bot, ev, f'用法：{self.prefix()}增加兑换码ABCDEFG；本人兑换成功后入库，也可复用48小时内成功记录')
            return
        if mode in ('redeem', 'add') and argument:
            try:
                code = code_text(argument)
            except ValueError as exc:
                await self.send(bot, ev, str(exc))
                return
            report = self.catalog.report()
            cached = next((r for r in report['items'] if code_key(r['code']) == code_key(code)), None)
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
            if mode == 'quick':
                await self.send(bot, ev, quick_listing(report, self.prefix()))
                return
            if mode == 'query' or mode == 'redeem':
                if not await self.send_detail(bot, ev, listing(report, self.prefix()), '兑换码查询详情'):
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
            notice = (f'将核验 {items[0]["code"]}；本人本次或48小时内明确兑换成功后加入共享缓存'
                      if mode == 'add' else f'将为当前绑定角色尝试处理{len(items)}个码，已领取或已知过期项自动跳过')
            if not await self.send(bot, ev, notice, bind):
                return
            # Keep the client alive in the retained worker; delivery failure must not cause a new submit.
            task = asyncio.create_task(self._worker(bot, ev, client, bind, items, contribute=mode == 'add'))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            client = None
        finally:
            if client is not None:
                await client.close()

    async def _worker(self, bot, ev, client, bind, items, *, contribute=False):
        try:
            results = await self.redemptions.run(client, bind, items,
                current=lambda: self.current(ev, bind), enabled=self.enabled, contribute=contribute)
            if contribute and not any(r.get('pool_status') in ('added', 'existing', 'blocked') for r in results):
                results.append(dict(code='', status='info', result='无本次或48小时内明确成功记录，未新增共享码；已有缓存记录保留'))
            if detailed_result(results) and self.result_forward_enabled():
                await self.send_detail(bot, ev, result_text(results), '兑换结果详情', bind,
                                       config_key='AliceUID_CDKResultForward')
            else:
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

    @user.on_command('增加兑换码')
    async def add(bot, ev):
        await invoke(bot, ev, 'add')

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
