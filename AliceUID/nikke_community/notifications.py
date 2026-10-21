"""Per-group confirmed sign-in summaries; no member credentials or remote queries."""
from __future__ import annotations
import asyncio
from collections import Counter
import hashlib
from .store import digest
from ..nikke_commands import command_prefix
from .cycle import cycle_day, cycle_label

class NotificationStore:
    def __init__(self, store):
        self.store = store
        with store.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS notify_routes ('
                       'route_key TEXT PRIMARY KEY,bot_id TEXT,group_id TEXT,ws_id TEXT,self_id TEXT,seen_at REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS notify_receipts ('
                       'route_key TEXT,day TEXT,status TEXT,updated_at REAL,PRIMARY KEY(route_key,day))')

    def observe(self, ev, now):
        bot, group, ws, own = (str(getattr(ev, key, '') or '') for key in ('bot_id','group_id','WS_BOT_ID','bot_self_id'))
        # Missing routing fields never guess another active bot.
        if not all(0 < len(v) <= 128 for v in (bot,group,ws,own)):
            return
        key = digest('notification',bot,own,group)
        with self.store.transaction() as db:
            db.execute('INSERT INTO notify_routes VALUES(?,?,?,?,?,?) ON CONFLICT(route_key) DO UPDATE SET '
                       'ws_id=excluded.ws_id,seen_at=excluded.seen_at',(key,bot,group,ws,own,now))

    def routes(self, now):
        with self.store.transaction() as db:
            return [dict(row) for row in db.execute('SELECT * FROM notify_routes WHERE seen_at>=?',(now-30*86400,))]

    def reserve(self, key, day, now):
        with self.store.transaction() as db:
            # Reserve BEFORE sending. Crash/ambiguous receipt must not duplicate.
            return db.execute('INSERT OR IGNORE INTO notify_receipts VALUES(?,?,?,?)',(key,day,'unknown',now)).rowcount == 1

    def delivered(self, key, day, now):
        with self.store.transaction() as db:
            db.execute('UPDATE notify_receipts SET status=?,updated_at=? WHERE route_key=? AND day=?',('delivered',now,key,day))

def identity(service, row):
    revision = hashlib.sha256(row.cookie_enc.encode()).hexdigest()
    return digest(str(row.game_id),str(row.intl_open_id)), service.owner(str(row.user_id),str(row.bot_id),revision)

def summarize(service, rows, route, day, processed, *, allowed=lambda _:True, invalid=lambda _:False):
    """None means no automatic targets or at least one target is still pending."""
    now = service.clock()
    bot, group = route['bot_id'], route['group_id']
    actors = set(service.store.group_actors(bot,group,now))
    by_actor = {}
    for row in rows:
        if str(row.bot_id) != bot:
            continue
        actor = str(row.user_id)
        by_actor.setdefault(actor,[]).append(row)
        if str(getattr(row,'group_id','') or '') == group:
            actors.add(actor)
    counts = Counter()
    targets = 0
    for actor in actors:
        entries = by_actor.get(actor,[])
        if not allowed(actor):
            counts['权限受限'] += 1
            continue
        if len(entries)>1:
            counts['绑定冲突'] += 1
            continue
        if not entries or not entries[0].cookie_enc or not entries[0].intl_open_id:
            counts['未绑定'] += 1
            continue
        row = entries[0]
        account, owner = identity(service,row)
        state = service.store.state(account)
        if state.get('owner') != owner or not state.get('enabled'):
            counts['未开启'] += 1
            continue
        targets += 1
        if state.get('lease_until',0)>now:
            return None
        receipt = service.store.signin_status(account,owner,day)
        if receipt['confirmed']:
            counts['成功'] += 1
            if state.get('paused'):
                counts['后续任务暂停'] += 1
        elif invalid(row):
            counts['失败'] += 1
        elif receipt.get('uncertain'):
            counts['未确认'] += 1
        elif state.get('paused'):
            counts['暂停'] += 1
        elif (actor,bot) not in processed and state.get('last_day') != day:
            return None
        else:
            # A run can finish without a confirmed sign-in. Never invent failure/success.
            counts['未确认'] += 1
    if not targets:
        return None
    return counts

def message(counts, day, now):
    complete = not any(counts[k] for k in ('失败','未确认','暂停','未执行'))
    today = cycle_day(now) == day
    title = ('今日' if today else day+'周期') + ('自动签到已完成！' if complete else '自动签到处理结束。')
    text = ('✅' if complete else '⚠️') + ' [AliceUID] NIKKE' + title
    text += f'\n📝 本群共签到成功{counts["成功"]}人，共签到失败{counts["失败"]}人，{counts["未开启"]}人尚未开启自动签到。'
    extra = '，'.join(f'{label}{counts[label]}人' for label in ('未确认','暂停','未执行','未绑定','权限受限','绑定冲突','后续任务暂停') if counts[label])
    if extra:
        text += '\n' + extra + '。'
    text += f'\n统计范围：本群绑定或近30天使用过{command_prefix()}命令的已知用户。'
    if not today:
        text += '\n' + cycle_label(day)
    return text

class GroupNotifier:
    def __init__(self, service, rows, sender, permitted, *, invalid=lambda _:False):
        self.service,self.rows,self.sender,self.permitted = service,rows,sender,permitted
        self.invalid = invalid
        self.store = NotificationStore(service.store)
        self._lock = asyncio.Lock()

    async def progress(self, day, processed):
        if self._lock.locked() or not self.service.allowed():
            return
        async with self._lock:
            # A crossed cycle is not a successful batch; leave it unannounced.
            if cycle_day(self.service.clock()) != day:
                return
            rows = await self.rows()
            for route in self.store.routes(self.service.clock()):
                if not await self.permitted(route):
                    continue
                counts = summarize(self.service,rows,route,day,processed,
                                   allowed=self.service.user_allowed,invalid=self.invalid)
                if counts is None:
                    continue
                if not await self.permitted(route) or not self.service.allowed():
                    continue
                if not self.store.reserve(route['route_key'],day,self.service.clock()):
                    continue
                try:
                    receipt = await asyncio.wait_for(self.sender(route,message(counts,day,self.service.clock())),timeout=30)
                    if isinstance(receipt,(list,tuple)) and receipt and all(isinstance(x,str) and x.strip() for x in receipt):
                        self.store.delivered(route['route_key'],day,self.service.clock())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # One group's transport failure cannot stop sign-in or another group.
                    import logging
                    logging.getLogger(__name__).warning('AliceUID group summary delivery unconfirmed')
