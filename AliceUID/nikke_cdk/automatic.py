"""Opt-out preferences and serialized, newly contributed-code automation."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from types import SimpleNamespace
from .models import PRODUCT, identity, revision, clean, code_key, retirement_at

KEY = 'AliceUID_AutoCDKEnabled'


class AutoStore:
    def __init__(self, store):
        self.store = store
        with store.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auto_preferences (
                    bot TEXT,user TEXT,enabled INTEGER NOT NULL,PRIMARY KEY(bot,user));
                CREATE TABLE IF NOT EXISTS auto_groups (
                    bot TEXT,self_id TEXT,user TEXT,group_id TEXT,seen REAL,
                    PRIMARY KEY(bot,self_id,user,group_id));
                CREATE TABLE IF NOT EXISTS auto_routes (
                    bot TEXT,self_id TEXT,group_id TEXT,ws TEXT,seen REAL,
                    PRIMARY KEY(bot,self_id,group_id));
                CREATE TABLE IF NOT EXISTS auto_connections (
                    bot TEXT,self_id TEXT,ws TEXT,user TEXT,seen REAL,
                    PRIMARY KEY(bot,self_id,ws));
            ''')

    def enabled(self, bot, user):
        with self.store.tx() as db:
            row = db.execute('SELECT enabled FROM auto_preferences WHERE bot=? AND user=?',
                             (str(bot), str(user))).fetchone()
        return row is None or bool(row[0])

    def set_many(self, bot, users, enabled):
        with self.store.tx() as db:
            db.executemany('INSERT OR REPLACE INTO auto_preferences VALUES(?,?,?)',
                           [(str(bot), str(user), int(enabled)) for user in set(users)])

    def observe(self, ev, now=None):
        bot, own, user, group, ws = (str(getattr(ev, k, '') or '') for k in
                                    ('bot_id', 'bot_self_id', 'user_id', 'group_id', 'WS_BOT_ID'))
        if not all((bot, own, user, ws)):
            return
        now = time.time() if now is None else now
        with self.store.tx() as db:
            db.execute('INSERT OR REPLACE INTO auto_connections VALUES(?,?,?,?,?)', (bot, own, ws, user, now))
            if not group:
                return
            db.execute('INSERT OR REPLACE INTO auto_groups VALUES(?,?,?,?,?)', (bot, own, user, group, now))
            db.execute('INSERT OR REPLACE INTO auto_routes VALUES(?,?,?,?,?)', (bot, own, group, ws, now))

    def groups(self, ev, user):
        with self.store.tx() as db:
            return [r[0] for r in db.execute(
                'SELECT group_id FROM auto_groups WHERE bot=? AND self_id=? AND user=? AND seen>=? ORDER BY seen DESC,group_id',
                (str(ev.bot_id), str(ev.bot_self_id), str(user), time.time()-30*86400))]

    def route(self, ev, group):
        with self.store.tx() as db:
            row = db.execute('SELECT * FROM auto_routes WHERE bot=? AND self_id=? AND group_id=? AND seen>=?',
                (str(ev.bot_id), str(ev.bot_self_id), str(group), time.time()-30*86400)).fetchone()
        return dict(row) if row else None

    def routes(self):
        with self.store.tx() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM auto_routes WHERE seen>=? ORDER BY seen DESC', (time.time()-30*86400,))]
            rows.extend(dict(r, group_id=None) for r in db.execute(
                'SELECT * FROM auto_connections WHERE seen>=? ORDER BY seen DESC', (time.time()-30*86400,)))
        return rows


class Automatic:
    def __init__(self, commands, *, config, bindings, permitted, notify, masters=lambda: (),
                 sleep=asyncio.sleep, interval=lambda: 3, background_event=None):
        self.commands, self.config, self.bindings = commands, config, bindings
        self.permitted, self.notify, self.masters = permitted, notify, masters
        self.store = AutoStore(commands.redemptions.store)
        self.lock = asyncio.Lock()
        self.sleep, self.interval = sleep, interval
        self.background_event = background_event

    def inventory(self, items):
        merged = {}
        for item in [*items, *self.commands.catalog.report()['items']]:
            merged.setdefault(code_key(item['code']), item)
        blocked = {code_key(code) for code in self.commands.redemptions.store.blocked(PRODUCT)}
        now = self.commands.catalog.clock()
        return [item for key, item in merged.items() if key not in blocked
                and (retirement_at(item) is None or now < retirement_at(item))
                and (not item.get('valid_from') or now >= item['valid_from'])]

    def reject_codes(self, results):
        """1302016 is owned/claimed; 1302014 means globally used, not owned."""
        reasons = []
        for result in results:
            if result.get('status') != 'failed' or not result.get('code'):
                continue
            text = result.get('result', '')
            if any(f'（{code}）' in text for code in (1302014, 1302003, 1302015)):
                reason = '可能为私人一次性兑换码，或已超过使用次数；已停止后续兑换并移出库存'
                self.commands.redemptions.store.block(PRODUCT, result['code'], 'possibly_private', reason,
                                                      self.commands.catalog.clock())
                reasons.append(result['code'] + '：' + reason)
        return reasons

    def enabled(self):
        return self.config.get_config(KEY).data is True

    def active(self, ev):
        return self.enabled() and self.commands.enabled() and self.store.enabled(ev.bot_id, ev.user_id)

    def members(self, ev, row):
        return set(self.store.groups(ev, row.user_id)) | ({str(row.group_id)} if getattr(row, 'group_id', None) else set())

    async def control(self, bot, ev, scope, enabled):
        if not await self.commands.allowed(ev):
            return
        master = type(getattr(ev, 'user_pm', None)) is int and ev.user_pm == 0
        if scope != 'self' and not master:
            return await self.commands.send(bot, ev, '仅Bot主可以使用此管理指令')
        if scope == 'system':
            same = self.enabled() == enabled
            if self.config.set_config(KEY, enabled) is False:
                return await self.commands.send(bot, ev, '系统开关保存失败，请稍后重试')
            if not enabled and getattr(self.commands, 'public_discoveries', None) is not None:
                self.commands.public_discoveries.discover(self.commands.catalog.report()['items'], False)
            state = '启用' if enabled else '停用'
            return await self.commands.send(bot, ev, f'自动兑换码系统已{"处于" if same else ""}{state}状态。')
        if enabled and not self.enabled():
            text = (f'当前自动兑换码系统已关闭，是否需要启用？\n如需启用，请发送：{self.commands.prefix()}启用自动兑换码'
                    if master else 'Bot主尚未开启自动兑换码功能，请联系Bot主启用。')
            return await self.commands.send(bot, ev, text)
        rows = [r for r in await self.bindings() if str(r.bot_id) == str(ev.bot_id)]
        if scope == 'group':
            if not getattr(ev, 'group_id', None):
                return await self.commands.send(bot, ev, '请在需要设置的群内使用此指令')
            rows = [r for r in rows if str(ev.group_id) in self.members(ev, r)]
        elif scope == 'self':
            rows = [r for r in rows if str(r.user_id) == str(ev.user_id)]
            if not rows:
                return await self.commands.send(bot, ev, f'请先{self.commands.prefix()}登录绑定本人账号')
        users = {str(r.user_id) for r in rows}
        self.store.set_many(ev.bot_id, users, enabled)
        label = {'self': '个人', 'group': '本群绑定用户', 'all': '全部绑定用户'}[scope]
        await self.commands.send(bot, ev, f'已{"开启" if enabled else "关闭"}{label}自动兑换码（{len(users)}人）。')

    def event(self, source, row, group):
        # Explicit target identity; never run another account with the initiator's event.
        return SimpleNamespace(bot_id=str(row.bot_id), user_id=str(row.user_id), group_id=group,
            bot_self_id=str(source.bot_self_id), WS_BOT_ID=str(source.WS_BOT_ID),
            user_pm=0 if str(row.user_id) in set(map(str, self.masters())) else 6)

    async def run(self, bot, source, initiator, items, seed, *, seed_client=None, background=False):
        # No replay when the system is re-enabled after an addition made while disabled.
        if not self.enabled() or not self.commands.enabled():
            return
        async with self.lock:
            if not self.enabled() or not self.commands.enabled():
                return
            self.store.observe(source)
            group = str(getattr(source, 'group_id', '') or '')
            rows = [r for r in await self.bindings() if str(r.bot_id) == str(source.bot_id)]
            masters = set(map(str, self.masters()))
            def rank(row):
                user = str(row.user_id)
                return (0 if user == str(source.user_id) else 1 if user in masters else
                        2 if group and group in self.members(source, row) else 3, user)
            rows.sort(key=rank)
            plans, seen, owners = [], set(), set()
            for row in rows:
                user, account = str(row.user_id), identity(row)
                if user in owners or account in seen or not self.store.enabled(row.bot_id, user):
                    continue
                memberships = self.members(source, row)
                home = (group if group and group in memberships else
                        str(getattr(row, 'group_id', '') or '') or next(iter(sorted(memberships)), ''))
                ev = self.event(source, row, home or None)
                if background and self.background_event is not None:
                    ev = await self.background_event(ev)
                    if ev is None:
                        continue
                if not await self.permitted(ev):
                    continue
                owners.add(user); seen.add(account)
                plans.append((row, ev))
            def route_key(ev):
                return (ev.bot_id, ev.bot_self_id, ev.group_id)
            groups = {route_key(ev): ev for _, ev in plans if ev.group_id}
            for ev in groups.values():
                await self.safe_notify(ev, ev.group_id, '正在为绑定用户兑换新增兑换码。')
            outcomes = defaultdict(list)
            abort = ''
            for index, (row, ev) in enumerate(plans):
                target = route_key(ev)
                inventory = self.inventory(items)
                if abort:
                    outcomes[target].append((row, 'stopped'))
                    self.commands.redemptions.store.audit_inventory(row, inventory,
                        [dict(code='', status='stopped', result=abort)], self.commands.catalog.clock())
                    continue
                if index:
                    await self.sleep(max(0, float(self.interval())))
                if not self.active(ev) or not await self.permitted(ev):
                    outcomes[target].append((row, 'stopped'))
                    self.commands.redemptions.store.audit_inventory(row, inventory,
                        [dict(code='', status='stopped', result='开关或权限变化，未继续兑换')], self.commands.catalog.clock())
                    continue
                client, close_client, results = None, False, []
                try:
                    all_known = all((receipt := self.commands.redemptions.store.receipt(identity(row), item['code']))
                                    and receipt['state'] in ('success', 'claimed') for item in inventory)
                    actual = row
                    if not all_known and initiator is not None and seed_client is not None and (
                        str(row.user_id) == str(source.user_id) and revision(row) == revision(initiator)
                    ):
                        client = seed_client
                    elif not all_known:
                        client, actual = await self.commands.load(ev)
                        close_client = client is not None
                        if client is None or actual is None:
                            results = [dict(code='', status='stopped', result='COOKIE不可用，未执行兑换，请重新登录')]
                            outcomes[target].append((row, 'cookie'))
                            if str(row.user_id) in masters:
                                abort = 'Bot主COOKIE不可用，核验未完成，已停止后续自动兑换。'
                            continue
                        if revision(actual) != revision(row):
                            results = [dict(code='', status='stopped', result='绑定已变化，未执行兑换')]
                            outcomes[target].append((row, 'stopped'))
                            if str(row.user_id) in masters:
                                abort = 'Bot主绑定已变化，核验未完成，已停止后续自动兑换。'
                            continue
                    async def current():
                        return (self.active(ev) and await self.permitted(ev)
                                and await self.commands.current(ev, actual))
                    results = await self.commands.redemptions.run(client, actual, inventory,
                        current=current, enabled=lambda: self.active(ev), reconcile=True)
                    # Uncertain writes retain their receipt. Further rounds only confirm
                    # history, never erase the journal to blindly resubmit a timeout.
                    if str(row.user_id) in masters:
                        for _ in range(2):
                            if not any(r['status'] == 'uncertain' for r in results) or not await current():
                                break
                            await self.sleep(max(0, float(self.interval())))
                            results = await self.commands.redemptions.run(client, actual, inventory,
                                current=current, enabled=lambda: self.active(ev), reconcile=True)
                    rejected = self.reject_codes(results)
                    if rejected:
                        abort = '\n'.join(rejected)
                    elif any(code_key(item['code']) in {code_key(code) for code in
                             self.commands.redemptions.store.blocked(PRODUCT)} for item in inventory):
                        abort = '新增兑换码已失效或被停用，已移出库存并停止后续自动兑换。'
                    statuses = {r['status'] for r in results}
                    status = 'ok' if results and statuses <= {'success', 'claimed'} else (
                        'cookie' if any('登录' in r.get('result', '') or '凭据' in r.get('result', '') for r in results)
                        else 'failed' if 'failed' in statuses else 'uncertain' if 'uncertain' in statuses else 'stopped')
                    outcomes[target].append((row, status))
                    if str(row.user_id) in masters and status != 'ok' and not abort:
                        abort = 'Bot主核验未通过或结果未确认，已停止后续自动兑换，请检查登录及兑换状态。'
                except Exception:
                    results.append(dict(code='', status='uncertain', result='自动兑换核验异常，结果未确认'))
                    outcomes[target].append((row, 'uncertain'))
                    if str(row.user_id) in masters:
                        abort = 'Bot主核验异常，结果未确认，已停止后续自动兑换。'
                finally:
                    try:
                        self.commands.redemptions.store.audit_inventory(row, inventory, results, self.commands.catalog.clock())
                    finally:
                        if close_client:
                            await client.close()
            for target, results in outcomes.items():
                if not target[2]:
                    continue
                bad = [(row, state) for row, state in results if state != 'ok']
                text = ('本群参与本次自动兑换的绑定用户已全员成功兑换（含已领取）。' if not bad else
                        '新增兑换码自动兑换已结束，部分用户未能完成。')
                text += f'\n成功{len(results)-len(bad)}人｜未完成{len(bad)}人'
                text += '\n已静默核对当前全部有效兑换码，结果已记录。'
                if abort:
                    text += '\n' + abort
                for row, state in bad:
                    name = ' '.join(clean(str(getattr(row, 'nickname', '') or row.user_id), 60).split())
                    reason = ('COOKIE可能已失效，请重新登录' if state == 'cookie' else
                              '兑换失败，COOKIE可能已失效，请检查登录状态及兑换条件' if state == 'failed' else
                              '结果未确认，请稍后核对' if state == 'uncertain' else '开关、权限、绑定或兑换条件变化，未完成')
                    text += f'\n{name}（{row.user_id}）：{reason}'
                await self.safe_notify(groups[target], target[2], text)
            return abort

    async def safe_notify(self, source, group, text):
        # Delivery failures must not abort redemption for the rest of the queue.
        try:
            await self.notify(source, group, text)
        except Exception:
            import logging
            logging.getLogger(__name__).warning('AliceUID automatic CDK notice delivery unconfirmed')
