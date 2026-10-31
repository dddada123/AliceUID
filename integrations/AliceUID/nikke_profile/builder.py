"""个人名片的数据组装（纯函数，不依赖 gsuid_core）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from ..nikke_api.parser import StaticData, parse_profile, parse_roster
from ..nikke_api.resource import character_icon_url
from ..nikke_resource.skins import resolve_skin
from ..nikke_resource.card_meta import card_metadata, integer

TZ = timezone(timedelta(hours=8))
ELEMENT_CN = {'Fire': '火', 'Water': '水', 'Wind': '风', 'Electric': '电', 'Electronic': '电', 'Iron': '铁', 'Light': '光', 'Dark': '暗'}
CLASS_CN = {'Supporter': '辅助型', 'Attacker': '火力型', 'Defender': '防御型'}


def _num(value: int | str) -> str:
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return str(value or '-')


def build_profile_context(basic: dict, outpost: dict, chars: Iterable[dict], static: StaticData, *,
                          saved_role: dict | None = None, player_info: dict | None = None,
                          area_label: str = '') -> dict:
    profile = parse_profile(basic, outpost, static, saved_role, player_info)
    # Preserve absence in the new presentation rather than showing an invented zero.
    for target, source in [('character_count','character_count'),('costume_count','character_costume_count'),
                           ('team_combat','team_combat'),('overclock','sim_room_overclock_current_sub_season_high_score'),
                           ('tower','progress_tribe_tower'),('tower_elysion','progress_elysion_tower'),
                           ('tower_missilis','progress_missilis_tower'),('tower_tetra','progress_tetra_tower'),
                           ('tower_pilgrim','progress_pilgrim_tower')]:
        if basic.get(source) is None:
            profile[target] = None
    for key in ('synchro_level','outpost_battle_level','infra_core_level'):
        if outpost.get(key) is None:
            profile[key] = None
    if basic.get('lv') is None and (player_info or {}).get('player_level') is None:
        profile['level'] = None
    chars = list(chars)
    reported_by_code = {int(row.get('name_code') or 0): row for row in chars}
    roster = parse_roster([dict(row, grade=integer(row.get('grade')) or 0,
                               core=integer(row.get('core')) or 0) for row in chars], static)
    by_code = {row['name_code']: row for row in roster}
    rows = []
    seen = set()
    for item in profile.get('profile_team') or []:
        code = item['name_code']
        if code in by_code and code not in seen:
            rows.append(by_code[code])
            seen.add(code)
        if len(rows) >= 5:
            break
    team_source = '个人主页展示队伍'
    if not rows:
        rows = roster[:5]
        team_source = '主页未设置队伍 · 按战力展示前五名'
    selections = {row['name_code']: resolve_skin(reported_by_code[row['name_code']], static) for row in rows}
    team = [{
        'name': row['name'],
        'name_code': row['name_code'],
        'icon_url': character_icon_url(row['resource_id'], selections[row['name_code']].skin_index) if row['resource_id'] else '',
        'resource_id': row['resource_id'],
        'costume_id': selections[row['name_code']].costume_id,
        'skin_index': selections[row['name_code']].skin_index,
        'skin_source': selections[row['name_code']].source,
        'skin_reported': selections[row['name_code']].reported,
        'skin_mapped': selections[row['name_code']].mapped,
        'skin_notice': selections[row['name_code']].notice,
        'combat': integer(reported_by_code[row['name_code']].get('combat')),
        'combat_text': _num(integer(reported_by_code[row['name_code']].get('combat'))),
        'level': integer(reported_by_code[row['name_code']].get('lv')) if reported_by_code[row['name_code']].get('lv') is not None else '-',
        'rarity': row['rarity'],
        'element': ELEMENT_CN.get(row['element'], row['element']),
        'class': CLASS_CN.get(row['char_class'], row['char_class']),
        'grade': integer(reported_by_code[row['name_code']].get('grade')),
        'core': integer(reported_by_code[row['name_code']].get('core')),
        **card_metadata(reported_by_code[row['name_code']], static.character(row['name_code'])),
    } for row in rows]
    stats = [
        {'label': '作战人员', 'value': _num(profile['character_count']), 'hint': '名'},
        {'label': '部队战斗力', 'value': _num(profile['team_combat']), 'hint': '', 'kind': 'combat'},
        {'label': '时装', 'value': _num(profile['costume_count']), 'hint': '套'},
        {'label': '苏醒日', 'value': profile['created_at'] or '-', 'hint': '指挥官注册日期', 'kind': 'date'},
        {'label': '同步等级', 'value': _num(profile['synchro_level']), 'hint': ''},
        {'label': '超频模式', 'value': _num(profile['overclock']), 'hint': '层'},
    ]
    progress = [
        {'label': '主线 Normal', 'value': profile['campaign_normal'] or '-'},
        {'label': '主线 Hard', 'value': profile['campaign_hard'] or '-'},
        {'label': '无限塔', 'value': _num(profile['tower'])},
        {'label': '企业塔 极/米/泰/朝', 'value': ' / '.join(_num(profile[key]) for key in ('tower_elysion', 'tower_missilis', 'tower_tetra', 'tower_pilgrim'))},
    ]
    outpost_rows = [
        {'label': '前哨等级', 'value': _num(profile['outpost_battle_level'])},
        {'label': '基础设施核心', 'value': _num(profile['infra_core_level'])},
        {'label': '循环室研究', 'value': f"{len(profile.get('recycle_researches') or [])} 项" if isinstance(outpost.get('recycle_room_researches'), list) else '-'},
    ]
    return {
        'nickname': profile['nickname'] or '未知指挥官', 'uid': profile['uid'] or '-',
        'area_label': area_label or f"区服 {profile['area_id']}", 'level': _num(profile['level']),
        'commander_icon_id': (saved_role or {}).get('icon'),
        'guild_name': profile.get('guild_name') or '', 'avatar_url': team[0]['icon_url'] if team else '',
        'stats': stats, 'progress': progress, 'outpost': outpost_rows, 'top_nikke': team,
        'corp_towers': [{'label': label, 'value': _num(profile[key])}
                        for label, key in [('极乐净土','tower_elysion'),('米西利斯','tower_missilis'),
                                           ('泰特拉','tower_tetra'),('朝圣者','tower_pilgrim')]],
        'team_source': team_source, 'generated_at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M'),
    }
