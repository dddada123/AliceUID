"""Pure local panel attributes, following Blablalink's level-slider formula.

Source: cube-icon-DhuJqjHc.js / setting-Da2XWN7e.js, reviewed 2026-11-09.
Missing/hidden dependencies never become zero. No network or credentials here.
"""
from __future__ import annotations
import math
import hashlib
import json
from ..nikke_api.parser import static_weapon_type

FORMULA_VERSION = 'blablalink-slider-combat-20261110-v2'
KEYS = {'attack': ('attack', 'atk', 'Atk'), 'defense': ('defence', 'def', 'Defence'), 'hp': ('hp', 'hp', 'Hp')}
RESEARCH = {'Attacker': 1101, 'Defender': 1102, 'Supporter': 1103,
            'ELYSION': 1201, 'MISSILIS': 1202, 'TETRA': 1203, 'PILGRIM': 1204, 'ABNORMAL': 1205}
CORPS = {1: 'ELYSION', 2: 'MISSILIS', 3: 'TETRA', 4: 'PILGRIM', 7: 'ABNORMAL'}

class AttributeUnavailable(ValueError):
    pass

def number(value, label, *, integral=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise AttributeUnavailable(label + '缺失')
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        raise AttributeUnavailable(label + '无效') from None
    if not math.isfinite(n) or n < 0 or n > 10**15 or (integral and not n.is_integer()):
        raise AttributeUnavailable(label + '隐藏或无效')
    return int(n) if integral else n

def js_round(n):
    return math.floor(n + .5)

def fingerprint(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def calculate_combat(attributes, detail, effects, bundle):
    """Website panel power; count effects by equipped occurrence, never unique ID."""
    result = dict(value=None, status='unavailable', reason='')
    try:
        if attributes.get('status') != 'complete':
            raise AttributeUnavailable(attributes.get('reason') or '攻防生命资料缺失')
        role = bundle.get('role') or {}
        critical = number(role.get('critical_ratio'), '基础暴击率') / 10000
        damage = number(role.get('critical_damage'), '基础暴击伤害') / 10000 - 1
        if damage < 0:
            raise AttributeUnavailable('基础暴击伤害无效')
        index = {}
        if not isinstance(effects, list):
            raise AttributeUnavailable('超载效果资料缺失')
        for effect in effects:
            if not isinstance(effect, dict):
                raise AttributeUnavailable('超载效果格式无效')
            key = str(effect.get('id'))
            if key in index and index[key] != effect:
                raise AttributeUnavailable('超载效果ID存在冲突')
            index[key] = effect
        raw_power = 0
        for slot in ('head', 'torso', 'arm', 'leg'):
            tid = number(detail.get(slot + '_equip_tid'), '装备ID', integral=True)
            if not tid:
                continue
            for position in (1, 2, 3):
                oid = number(detail.get(f'{slot}_equip_option{position}_id'), '超载词条ID', integral=True)
                if not oid:
                    continue
                functions = (index.get(str(oid)) or {}).get('function_details')
                if not isinstance(functions, list) or not functions:
                    raise AttributeUnavailable('超载战力效果缺失，请刷新面板')
                for function in functions:
                    value = function.get('function_battlepower') if isinstance(function, dict) else None
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 10**15:
                        raise AttributeUnavailable('超载战力系数缺失或无效，请刷新面板')
                    raw_power += max(value, 0)
        powers = {}
        for kind, field, level_field in (('cube', 'harmony_cube_tid', 'harmony_cube_lv'),
                                         ('favorite', 'favorite_item_tid', 'favorite_item_lv')):
            tid = number(detail.get(field), kind + 'ID', integral=True)
            powers[kind] = 0
            if tid:
                row = bundle.get(kind) or {}
                level = number(detail.get(level_field), kind + '等级', integral=True)
                i = level - 1 if kind == 'cube' else level
                values = row.get('powers')
                if row.get('id') != tid or i < 0 or not isinstance(values, list) or i >= len(values):
                    raise AttributeUnavailable(kind + '战力等级资料缺失')
                powers[kind] = round(number(values[i], kind + '战力系数') / 10000, 8)
        skills = [number(detail.get(key), '技能等级', integral=True)
                  for key in ('skill1_lv', 'skill2_lv', 'ulti_skill_lv')]
        if any(level > 10 for level in skills):
            raise AttributeUnavailable('技能等级超出已核验范围')
        overload = round(raw_power / 10000, 8)
        coefficient = 1.3 + skills[0]*.01 + skills[1]*.01 + skills[2]*.02 + powers['cube'] + powers['favorite'] + overload
        survival = math.floor((attributes['hp'] + attributes['defense']*100)*.7)
        attack = math.floor(attributes['attack']*(1 + critical*damage)*18)
        result.update(value=js_round((survival + attack)*coefficient*.01), status='complete',
                      coefficients=dict(base=1.3, skill1=skills[0]*.01, skill2=skills[1]*.01,
                                        burst=skills[2]*.02, overload=overload, **powers))
    except (AttributeUnavailable, KeyError, TypeError, ValueError, OverflowError) as exc:
        result['reason'] = str(exc) if isinstance(exc, AttributeUnavailable) else '战力依赖格式无效'
    return result

def calculate(owned, detail, outpost, bundle, *, level=None):
    result = dict(attack=None, defense=None, hp=None, status='unavailable', reason='',
                  formula_version=FORMULA_VERSION, source='local_blablalink_formula',
                  target_level=level, static_version=bundle.get('version'), actual_level=None)
    try:
        actual = number(owned.get('lv', detail.get('lv')), '实际等级', integral=True)
        target = actual if level is None else number(level, '模拟等级', integral=True)
        if not 1 <= target <= 10000:
            raise AttributeUnavailable('等级超出支持范围')
        result.update(actual_level=actual, target_level=target)
        role = bundle.get('role')
        if not isinstance(role, dict) or int(role.get('name_code', -1)) != int(detail['name_code']):
            raise AttributeUnavailable('角色成长资料不匹配')
        for t, _, _ in KEYS.values():
            levels = role.get('character_level_' + t + '_list')
            if not isinstance(levels, list) or target > len(levels):
                raise AttributeUnavailable('目标等级没有完整成长数据')
        enhance = role.get('stat_enhance_detail')
        if not isinstance(enhance, dict):
            raise AttributeUnavailable('突破核心系数缺失')
        grade = number(owned.get('grade', detail.get('grade')), '突破', integral=True)
        core = number(owned.get('core', detail.get('core')), '核心', integral=True)
        rare = role.get('original_rare')
        if grade > {'SSR': 3, 'SR': 2, 'R': 0}.get(rare, -1) or core > (7 if rare == 'SSR' else 0):
            raise AttributeUnavailable('突破核心超出范围')
        rows = outpost.get('recycle_room_researches') if isinstance(outpost, dict) else None
        if not isinstance(rows, list) or outpost.get('is_hide'):
            raise AttributeUnavailable('回收室资料缺失或隐藏')
        research = []
        for tid in (1001, RESEARCH.get(role.get('class')), RESEARCH.get(role.get('corporation', '').upper())):
            matches = [r for r in rows if isinstance(r, dict) and r.get('tid') == tid]
            stats = [r for r in bundle.get('research', []) if r.get('id') == tid]
            if tid is None or len(matches) != 1 or len(stats) != 1:
                raise AttributeUnavailable('回收室研究记录缺失或重复')
            research.append((number(matches[0].get('lv'), '回收室等级', integral=True), stats[0]))
        bond_lv = number(detail.get('attractive_lv'), '好感等级', integral=True)
        bond = [r for r in bundle.get('bond', []) if r.get('attractive_level') == bond_lv]
        if rare == 'R' and bond_lv == 0:
            bond = [{role['class'].lower() + '_' + t + '_rate': 0 for t in ('attack', 'defence', 'hp')}]
        if len(bond) != 1:
            raise AttributeUnavailable('好感成长资料缺失')
        gear = []
        for slot in ('head', 'torso', 'arm', 'leg'):
            tid = number(detail.get(slot + '_equip_tid'), '装备ID', integral=True)
            if tid == 0:
                continue
            equip = [r for r in bundle.get('equipment', []) if r.get('id') == tid]
            if len(equip) != 1 or not isinstance(equip[0].get('stat'), list):
                raise AttributeUnavailable('装备基础资料缺失')
            lv = number(detail.get(slot + '_equip_lv'), '装备等级', integral=True)
            corp = number(detail.get(slot + '_equip_corporation_type'), '装备企业', integral=True)
            if lv > 5 or corp not in (0, *CORPS):
                raise AttributeUnavailable('装备等级或企业无效')
            gear.append((equip[0], 1 + (.3 if CORPS.get(corp) == role['corporation'].upper() else 0) + .1 * lv))
        extra = []
        for kind, idkey, lvkey in (('cube', 'harmony_cube_tid', 'harmony_cube_lv'),
                                   ('favorite', 'favorite_item_tid', 'favorite_item_lv')):
            tid = number(detail.get(idkey), kind + 'ID', integral=True)
            if tid == 0:
                continue
            row = bundle.get(kind)
            if not isinstance(row, dict) or row.get('id') != tid:
                raise AttributeUnavailable(kind + '资料缺失')
            lv = number(detail.get(lvkey), kind + '等级', integral=True)
            index = lv - 1 if kind == 'cube' else lv
            if index < 0:
                raise AttributeUnavailable(kind + '等级无效')
            if kind == 'favorite':
                exclusive = number(row.get('name_code'), '收藏品适用角色', integral=True)
                weapon = bundle.get('weapon_type') or static_weapon_type(role)
                if not weapon:
                    raise AttributeUnavailable('角色武器资料缺失，无法核对收藏品')
                if (exclusive and exclusive != int(detail['name_code'])) or row.get('weapon_type') != weapon:
                    raise AttributeUnavailable('收藏品适用角色或武器不匹配')
            extra.append((row, index))
        values = {}
        for key, (t, short, gear_type) in KEYS.items():
            levels = role.get('character_level_' + t + '_list')
            if not isinstance(levels, list) or target > len(levels):
                raise AttributeUnavailable('目标等级没有完整成长数据')
            base = number(levels[target - 1], '等级成长值')
            base = math.floor(base * (1 + grade * number(enhance.get('grade_ratio'), '突破比例') * 1e-4)
                              + grade * number(enhance.get('grade_' + t), '突破固定值'))
            recycle_field = {'attack': 'attack', 'defence': 'defence', 'hp': 'hp'}[t]
            recycle = math.floor(sum(lv * number(row.get(recycle_field), '回收室系数') for lv, row in research))
            attractive = js_round(number(bond[0].get(role['class'].lower() + '_' + t + '_rate'), '好感加成'))
            value = js_round((base + recycle + attractive) * (1 + core * number(enhance.get('core_' + t), '核心系数') * 1e-4))
            for item, multiplier in gear:
                value += js_round(sum(number(s.get('stat_value'), '装备属性') for s in item['stat']
                                      if s.get('stat_type') == gear_type) * multiplier)
            for item, index in extra:
                array = item.get(short)
                if not isinstance(array, list) or index >= len(array):
                    raise AttributeUnavailable('魔方或收藏品等级属性缺失')
                value += number(array[index], '魔方收藏品属性', integral=True)
            values[key] = value
        result.update(values, status='complete')
    except (AttributeUnavailable, KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        result['reason'] = str(exc) if isinstance(exc, AttributeUnavailable) else '属性依赖格式无效'
    return result
