"""Read-only local group report. No member cookies, private API calls or invented roster."""
from ..nikke_commands import command_prefix
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import math
from .cycle import BJT, cycle_day, cycle_label
from .schedule import normalized_time, clock_parts
from .store import digest

PAGE_SIZE = 40


def clean_label(value, limit=32):
    value = ''.join(ch for ch in str(value or '') if ch >= ' ' and ch not in '\r\n')
    return value.replace('[CQ:', '［CQ：').replace('<', '＜').replace('>', '＞')[:limit]


def pending_label(day, now, sign_time):
    hour, minute = clock_parts(sign_time)
    planned = datetime.fromisoformat(day).replace(tzinfo=BJT, hour=hour, minute=minute)
    if hour < 8:
        planned += timedelta(days=1)
    return ('待定时', '等待' + normalized_time(sign_time)) if now < planned.timestamp() else ('待执行', '尚无本周期确认')


def group_report_text(service, bindings, *, bot_id, group_id, page=1, sign_time='08:33', user_allowed=lambda _: True, credential_invalid=lambda _: False):
    now = service.clock()
    day = cycle_day(now)
    actors = set(service.store.group_actors(bot_id, group_id, now))
    by_actor = {}
    for row in bindings:
        if str(getattr(row, 'bot_id', '')) != bot_id:
            continue
        actor = str(getattr(row, 'user_id', ''))
        if not actor:
            continue
        by_actor.setdefault(actor, []).append(row)
        if str(getattr(row, 'group_id', '') or '') == group_id:
            actors.add(actor)
    lines = []
    for actor in sorted(actors):
        rows = by_actor.get(actor, [])
        nickname, detail = '', ''
        if not user_allowed(actor):
            label = '权限受限'
        elif len(rows) > 1:
            label = '绑定冲突'
        elif not rows or not getattr(rows[0], 'cookie_enc', '') or not getattr(rows[0], 'intl_open_id', ''):
            label = '未绑定'
        else:
            row = rows[0]
            nickname = clean_label(getattr(row, 'nickname', ''))
            revision = hashlib.sha256(row.cookie_enc.encode()).hexdigest()
            account = digest(str(row.game_id), str(row.intl_open_id))
            owner = service.owner(actor, bot_id, revision)
            state = service.store.state(account)
            receipt = service.store.signin_status(account, owner, day)
            if state.get('owner') != owner:
                label = '未授权'
            elif receipt['confirmed']:
                label = '已签到'
                detail = datetime.fromtimestamp(receipt['confirmed_at'], BJT).strftime('%H:%M')
                if state.get('paused'):
                    detail += '，后续任务暂停'
                if credential_invalid(row):
                    detail += '，凭据需更新'
            elif credential_invalid(row):
                label, detail = '登录失效', f'请本人{command_prefix()}重新登录'
            elif state.get('paused'):
                label = '暂停'
                detail = '签到结果未确认' if receipt.get('uncertain') else '需本人查看自动社区状态'
            elif state.get('lease_until', 0) > now:
                label = '执行中'
            elif receipt.get('uncertain') or state.get('last_day') == day:
                label, detail = '未确认', '存在处理记录，不能认定已签到'
            elif not state.get('enabled'):
                label = '自动关闭'
            else:
                label, detail = pending_label(day, now, sign_time)
        display = clean_label(actor,64) + (' · ' + nickname if nickname else '')
        lines.append((label,display,detail))
    counts = Counter(item[0] for item in lines)
    total = len(lines)
    pages = max(1, math.ceil(total/PAGE_SIZE))
    if page > pages:
        return f'本群记录共{pages}页，请使用 {command_prefix()}签到查询 1～{pages}。'
    out = ['本群签到记录（本地）', cycle_label(day),
           f'每日自动时间：北京时间{normalized_time(sign_time)}',
           f'范围：本群绑定或近30天使用过{command_prefix()}命令的账号；不是实时全员名单。',
           f'本插件已知{total}人，确认已签到{counts["已签到"]}人。']
    other = '，'.join(f'{key}{value}' for key,value in sorted(counts.items()) if key!='已签到')
    if other:
        out.append(other + '。')
    if not total:
        out.append('暂无本群记录；未记录的成员不能判断签到情况。')
    for label,display,detail in lines[(page-1)*PAGE_SIZE:page*PAGE_SIZE]:
        out.append(f'{display}：{label}' + (f'（{detail}）' if detail else ''))
    if pages>1:
        out.append(f'第{page}/{pages}页；{command_prefix()}签到查询 页码 可翻页。')
    out.append('只显示本插件可确认的记录；在官网自行签到但尚未被本插件读取时可能仍显示未确认。')
    return '\n'.join(out)
