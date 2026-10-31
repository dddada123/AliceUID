"""Per-group confirmed sign-in summaries; no member credentials or remote queries."""
from __future__ import annotations
import asyncio
from collections import Counter
import hashlib
import json
from .report import clean_label
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
            db.execute('CREATE TABLE IF NOT EXISTS notify_batches (route_key TEXT,day TEXT,pages TEXT,PRIMARY KEY(route_key,day))')

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

    def pages(self, key, day, pages):
        with self.store.transaction() as db:
            db.execute('INSERT OR IGNORE INTO notify_batches VALUES(?,?,?)',(key,day,json.dumps(pages,ensure_ascii=False)))
            return json.loads(db.execute('SELECT pages FROM notify_batches WHERE route_key=? AND day=?',(key,day)).fetchone()[0])

    def delivered(self, key, day, now):
        with self.store.transaction() as db:
            db.execute('UPDATE notify_receipts SET status=?,updated_at=? WHERE route_key=? AND day=?',('delivered',now,key,day))

def identity(service, row):
    revision = hashlib.sha256(row.cookie_enc.encode()).hexdigest()
    return digest(str(row.game_id),str(row.intl_open_id)), service.owner(str(row.user_id),str(row.bot_id),revision)

class Summary(Counter):
    def __init__(self):
        super().__init__()
        self.details=[]


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
    counts = Summary()
    targets = 0
    for actor in sorted(actors):
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
        result=service.store.result(account,owner,day)
        if result and result['generation']!=state.get('generation'):
            result=None
        if state.get('owner')!=owner or (not state.get('enabled') and not (result and result['auto_stopped'])):
            counts['未开启']+=1
            continue
        targets+=1
        if state.get('lease_until',0)>now or (result and result['status'] in ('running','retry')):
            return None
        receipt=service.store.signin_status(account,owner,day)
        if (not result and not receipt['confirmed'] and (actor,bot) not in processed
                and not service.store.processed(owner,day) and state.get('last_day')!=day):
            return None
        reason=''
        if receipt['confirmed']:
            counts['成功']+=1
            if state.get('paused') or (result and result['reason']):
                counts['后续任务暂停']+=1
                reason='签到已成功；后续任务：'+(state.get('paused') or result['reason'])
        elif result and result['status']=='failed':
            label='未确认' if receipt.get('uncertain') or result['category'] in ('unconfirmed','schema') else '失败'
            counts[label]+=1
            reason=result['reason']
        elif invalid(row):
            counts['失败']+=1
            reason='本地凭据不可用，请本人重新登录'
        elif receipt.get('uncertain'):
            counts['未确认']+=1
            reason='签到提交结果未确认，未重复提交'
        elif state.get('paused'):
            counts['暂停']+=1
            reason=state['paused']
        elif result and result['status']=='cancelled':
            counts['未执行']+=1
            reason=result['reason'] or '任务条件变化，本周期未继续执行'
        elif (actor,bot) not in processed and state.get('last_day')!=day:
            return None
        else:
            counts['未确认']+=1
            reason='本周期尚未确认签到成功'
        if reason:
            counts.details.append(dict(actor=clean_label(actor,64),nickname=clean_label(getattr(row,'nickname','')),
                reason=reason,attempts=result['attempts'] if result else 0,
                streak=result['streak'] if result else state.get('fail_count',0),
                stopped=bool(result and result['auto_stopped']),signed=receipt['confirmed']))
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

def messages(counts, day, now, *, structured=False):
    header=message(counts,day,now)
    details=getattr(counts,'details',[])
    if not details:
        return [header]
    blocks=[]
    for item in details:
        name=(item['nickname']+' ' if item['nickname'] else '')+f'（QQ：{item["actor"]}）'
        text=name+'\n原因：'+item['reason']
        if item['attempts']:
            text+=f'；共尝试{item["attempts"]}轮。'
        if not item['signed']:
            if item['stopped']:
                text+=f'\n处理：连续{item["streak"]}个周期未能确认成功，已自动关闭自动签到。'
                text+=f'请本人{command_prefix()}重新登录以恢复此前授权；网络恢复后也可{command_prefix()}自动社区 开启。'
            elif item['streak']:
                text+=f'\n处理：连续失败{item["streak"]}/3天，自动签到保持开启，下个周期继续。'
        mentions = []
        if not item['signed']:
            text += f'\nCOOKIE 可能已过期，请发送 {command_prefix()}重新登录；如为网络或服务异常，请稍后检查。'
            actor = str(item['actor'])
            if actor.isascii() and actor.isdigit() and 0 < len(actor) <= 20:
                mentions.append(actor)
        blocks.append((text, mentions))
    pages=[]
    chunk=[];length=0;mentions=[]
    for block, actors in blocks:
        if chunk and (len(chunk)>=10 or length+len(block)>1800):
            pages.append(('\n\n'.join(chunk),mentions));chunk=[];length=0;mentions=[]
        chunk.append(block);length+=len(block);mentions.extend(actors)
    if chunk:pages.append(('\n\n'.join(chunk),mentions))
    output=[]
    for i,(page,actors) in enumerate(pages):
        text=(header if i==0 else '[AliceUID] 签到异常明细')+f'\n\n异常详情（{i+1}/{len(pages)}）：\n'+page
        output.append(dict(text=text,mentions=list(dict.fromkeys(actors))) if structured and actors else text)
    return output


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
                pages=self.store.pages(route['route_key'],day,messages(counts,day,self.service.clock(),structured=True))
                for index,text in enumerate(pages):
                    if not await self.permitted(route) or not self.service.allowed():
                        break
                    key=route['route_key'] if index==0 else route['route_key']+f':page:{index+1}'
                    if not self.store.reserve(key,day,self.service.clock()):
                        continue
                    try:
                        receipt=await asyncio.wait_for(self.sender(route,text),timeout=30)
                        if isinstance(receipt,(list,tuple)) and receipt and all(isinstance(x,str) and x.strip() for x in receipt):
                            self.store.delivered(key,day,self.service.clock())
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        import logging
                        logging.getLogger(__name__).warning('AliceUID group summary delivery unconfirmed')
