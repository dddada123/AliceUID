"""Strict Union Raid normalization. No sample or historical records are supplied."""
from __future__ import annotations

from collections import Counter
from ..nikke_time import beijing_text


class UnionDataError(ValueError):
    """Community schema is incomplete or ambiguous; never turn it into zero."""


def integer(value, field='整数', *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise UnionDataError(f'联盟{field}格式异常，无法统计。')
    if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
        raise UnionDataError(f'联盟{field}格式异常，无法统计。')
    result = int(value)
    if result < minimum:
        raise UnionDataError(f'联盟{field}格式异常，无法统计。')
    return result


def identifier(value, field='成员标识'):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise UnionDataError(f'联盟{field}缺失，无法统计。')
    return str(value)


def nickname(value):
    if not isinstance(value, str) or not value.strip():
        raise UnionDataError('联盟成员昵称格式异常，无法统计。')
    return value


def normalize_attacks(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('participate_data'), list):
        raise UnionDataError('联盟出刀响应格式变化，无法统计；不会按0刀处理。')
    attacks = []
    names = {}
    for row in payload['participate_data']:
        if not isinstance(row, dict):
            raise UnionDataError('联盟出刀记录格式异常，无法统计。')
        day = integer(row.get('day'), '日期')
        if day not in (0, 1):
            raise UnionDataError('联盟记录含未知Day，停止统计，请联系管理员核对。')
        uid = identifier(row.get('openid'))
        name = nickname(row.get('nickname'))
        if uid in names and names[uid] != name:
            raise UnionDataError('同一成员存在冲突昵称，无法确认记录。')
        names[uid] = name
        tail = row.get('is_final_hit')
        if type(tail) is not bool:
            raise UnionDataError('联盟尾刀标记格式异常，无法统计。')
        squad = row.get('squad')
        if not isinstance(squad, list) or len(squad) != 5:
            raise UnionDataError('联盟队伍应为5名角色，响应异常。')
        team, slots = [], set()
        for character in squad:
            if not isinstance(character, dict):
                raise UnionDataError('联盟队伍格式异常。')
            slot = integer(character.get('slot'), '角色位置', minimum=1)
            if slot > 5 or slot in slots:
                raise UnionDataError('联盟队伍位置重复或超出范围。')
            slots.add(slot)
            team.append({'slot': slot, 'tid': integer(character.get('tid'), '角色ID', minimum=1),
                         'lv': integer(character.get('lv'), '角色等级'),
                         'combat': integer(character.get('combat'), '角色战力'),
                         'costume_id': integer(character.get('costume_id'), '皮肤ID')})
        local = row.get('name_localvalues')
        if not isinstance(local, dict) or any(not isinstance(v, str) for v in local.values()):
            raise UnionDataError('联盟Boss名称格式异常。')
        attacks.append({'openid': uid, 'nickname': name, 'day': day,
                        'difficulty': integer(row.get('difficulty'), '难度'),
                        'level': integer(row.get('level'), 'Boss等级', minimum=1),
                        'boss_id': identifier(row.get('boss_id'), 'Boss标识'),
                        'boss_name': local.get('zh-tw') or local.get('zh-TW') or local.get('en') or '未知Boss',
                        'damage': integer(row.get('total_damage'), '伤害'), 'is_final_hit': tail,
                        'squad': sorted(team, key=lambda x: x['slot'])})
    return attacks


def normalize_members(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise UnionDataError('联盟名单响应格式变化，无法统计；不会按0刀处理。')
    members = {}
    for row in payload['items']:
        if not isinstance(row, dict):
            raise UnionDataError('联盟名单成员格式异常。')
        uid = identifier(row.get('member_id'))
        if uid in members:
            raise UnionDataError('联盟名单存在重复成员，无法统计。')
        members[uid] = nickname(row.get('nickname'))
    if not members:
        raise UnionDataError('联盟名单为空，无法确认完整成员。')
    return members


def _progress(attacks):
    # The reviewed Day1 event uses five bosses and ten levels. Never infer a
    # complete level universe from a partial level_info response of unknown day.
    bosses = {}
    for attack in attacks:
        if attack['day'] != 0:
            continue
        row = bosses.setdefault(attack['boss_id'], {'name': attack['boss_name'], 'kills': set()})
        if attack['is_final_hit']:
            row['kills'].add(attack['level'])
    rows = [{'name': row['name'], 'killed': len(row['kills']), 'levels': sorted(row['kills'])}
            for row in bosses.values()]
    full = len(bosses) == 5 and all(row['kills'] == set(range(1, 11)) for row in bosses.values())
    day2 = any(a['day'] == 1 for a in attacks)
    return rows, bool(full or day2)


def build_union_context(attacks, members, *, own_openid, fetched_at, guild_name='当前联盟',
                        view='quick', day=1, static=None, character_map=(), warnings=(), members_reference=False, raid_active=False, target_rank=None):
    if day not in (0, 1):
        raise UnionDataError('仅支持Day1或Day2。')
    progress, cleared = _progress(attacks)
    day2 = [a for a in attacks if a['day'] == 1]
    known = members is not None
    members_reference = bool(known and members_reference)
    names = dict(members or {})
    if known and any(a['openid'] not in names for a in day2):
        raise UnionDataError('出刀记录与当前成员名单不一致，无法可靠统计0刀。')
    for attack in day2:
        names.setdefault(attack['openid'], attack['nickname'])
    rows = []
    for uid, name in names.items():
        own = [a for a in day2 if a['openid'] == uid]
        count = len(own)
        rows.append({'openid': uid, 'name': name, 'count': count, 'damage': sum(a['damage'] for a in own),
                     'tail_damage': sum(a['damage'] for a in own if a['is_final_hit']),
                     'tails': sum(a['is_final_hit'] for a in own), 'attacks': own,
                     'status': '异常：超过3刀' if count > 3 else ('完成' if count == 3 else (('待出刀' if raid_active else '漏刀') if count == 0 else '未出完')),
                     'own': uid == str(own_openid)})
    rows.sort(key=lambda x: (-x['damage'], -x['count'], x['name'], x['openid']))
    for rank, row in enumerate(rows, 1):
        row['rank'] = rank
        row['status_color'] = ('ok' if row['count'] == 3 else 'bad' if row['count'] > 3
                               else ('warm' if raid_active else 'bad') if row['count'] == 0
                               else 'pending' if raid_active else 'warm')
    counts = Counter(row['count'] for row in rows)
    context = {'title': 'Day 1 简单模式' if day == 0 else 'Day 2 困难模式', 'day': day,
               'guild_name': guild_name, 'source': '社区当前可用记录 · 赛季未知',
               'fetched_at': beijing_text(fetched_at), 'fetched_at_epoch': fetched_at,
               'members_known': known, 'coverage': '完整成员名单' if known else '仅已出刀成员；0刀未知',
               'rows': rows if day == 1 else [], 'counts': counts, 'progress': progress, 'day1_cleared': cleared,
               'day1_note': '已通关（有Day2记录或5 Boss×10级击杀证据）' if cleared else '未确认通关；仅列当前已记录击杀进度',
               'day2_active': bool(day2), 'total_attacks': len(day2), 'tail_count': sum(a['is_final_hit'] for a in day2),
               'missing': [r for r in rows if r['count'] < 3] if day == 1 else [],
               'tails': [a for a in day2 if a['is_final_hit']] if day == 1 else [],
               'warnings': list(warnings), 'view': view, 'details': [],
               'damage_leaders': sorted((r for r in rows if r['count']>0), key=lambda r:(-r['damage'],r['openid']))[:3] if day==1 else [],
               'kill_leaders': sorted((r for r in rows if r['tails']>0), key=lambda r:(-r['tails'],-r['tail_damage'],r['openid']))[:3] if day==1 else [],
               'completion': ('全员完成' if known and rows and all(r['count'] == 3 for r in rows) else
                              ('0刀未知，不判断全员完成' if not known else '仍有未完成或异常成员'))}
    if day == 0:
        context['completion'] = 'Day1不统计个人出刀、漏刀或尾刀'
        context['coverage'] = 'Boss通关记录 · 不统计个人刀数'
        context['warnings'] = []
    context['members_reference'] = members_reference
    if day == 1 and members_reference:
        context['coverage'] = '当前完整名单对照上期记录（含历史出刀成员）'
        context['completion'] = ('当前对照名单均有3条Day2记录' if rows and all(r['count'] == 3 for r in rows)
                                 else '仍有未完成或异常成员（按当前名单对照上期记录）')
    missing = context['missing']
    middle = (len(missing) + 1) // 2
    context['missing_columns'] = [missing[:middle], missing[middle:]]
    context['target_rank'] = target_rank
    if view == 'detail':
        if day == 0:
            raise UnionDataError('Day1只看Boss通关进度，不统计个人详情。')
        if target_rank is not None:
            if type(target_rank) is not int or not 1 <= target_rank <= len(rows):
                raise UnionDataError(f'当前伤害榜共{len(rows)}名成员，请输入1～{len(rows)}的排名；不带数字查询本人。')
            own = rows[target_rank - 1]
        else:
            own = next((row for row in rows if row['own']), None)
        if own is None:
            if known:
                raise UnionDataError('当前绑定成员不在联盟名单中，无法确认本人详情。')
            context['warnings'].append('本人没有当前Day2记录；成员名单不可用，不能确认0刀。')
        else:
            mapping = {}
            for item in character_map:
                tid = integer(item.get('id'), '映射ID', minimum=1)
                code = integer(item.get('name_code'), '角色编码', minimum=1)
                resource = integer(item.get('resource_id'), '资源编码', minimum=1)
                if tid in mapping and mapping[tid] != (code, resource):
                    raise UnionDataError('角色ID映射冲突。')
                mapping[tid] = (code, resource)
            teams = []
            for attack in own['attacks']:
                team = dict(attack)
                characters = []
                for character in attack['squad']:
                    code, resource = mapping.get(character['tid'], (None, None))
                    info = static.character(code) if static is not None and code is not None else {}
                    name = ((info.get('name_localkey') or {}).get('name') or f'未知角色（tid {character["tid"]}）')
                    characters.append({**character, 'name': name, 'name_code': code, 'resource_id': resource,
                                       'icon_url': '', 'unknown': code is None})
                team['characters'] = characters
                teams.append(team)
            context['details'] = [{**own, 'attacks': teams}]
    return context
