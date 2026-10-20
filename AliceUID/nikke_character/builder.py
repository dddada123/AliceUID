"""Pure character lookup and normalization; no bot, database or network imports."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import re
import unicodedata
from typing import Callable, Iterable

from ..nikke_api.parser import StaticData, STAT_NAMES, parse_character, static_weapon_type
from ..nikke_resource.skins import resolve_skin

SLOTS = (('head', '头部'), ('torso', '躯干'), ('arm', '手臂'), ('leg', '腿部'))
SKILLS = (('skill1', '技能一', 'skill1_lv'), ('skill2', '技能二', 'skill2_lv'), ('burst', '爆裂技能', 'ulti_skill_lv'))


class CharacterLookupError(ValueError):
    pass


class CharacterNotFound(CharacterLookupError):
    pass


class CharacterAmbiguous(CharacterLookupError):
    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__('角色名不唯一，请使用完整名称：' + '、'.join(candidates[:12]))


class CharacterDependencyMissing(CharacterLookupError):
    pass


@lru_cache(maxsize=1)
def _converter():
    try:
        from opencc import OpenCC
    except ImportError:
        raise CharacterDependencyMissing('简繁名称转换组件未安装，请联系管理员安装 opencc-python-reimplemented，或使用完整繁体角色名。') from None
    return OpenCC('t2s').convert


def _name_key(value: str, convert: Callable[[str], str]) -> str:
    normalized = unicodedata.normalize('NFKC', convert(value)).casefold()
    return ''.join(c for c in normalized if not c.isspace() and not unicodedata.category(c).startswith('P'))


def resolve_character(query: str, static: StaticData, *, convert: Callable[[str], str] | None = None,
                      aliases: dict | None = None) -> int:
    """Exact official names win before simplified/traditional or substring lookup.

    Search the whole catalog, not only owned rows: ownership must not silently
    change an ambiguous name into a guess. Numeric name_code is an explicit key.
    """
    query = str(query or '').strip()
    if not query:
        raise CharacterNotFound(f'请填写角色名，例如 {command_prefix()}爱丽丝练度 或 {command_prefix()}练度 红莲。')
    names = {int(code): static.name(code) for code in static.characters}
    exact = [code for code, name in names.items() if name.casefold() == query.casefold()]
    if query.isascii() and query.isdecimal() and int(query) in names:
        return int(query)
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CharacterAmbiguous([f'{names[code]}（{code}）' for code in exact])
    convert = convert or _converter()
    key = _name_key(query, convert)
    normalized = {code: _name_key(name, convert) for code, name in names.items()}
    matches = [code for code, name in normalized.items() if name == key]
    if not matches and aliases:
        matches = list({int(code) for alias, code in aliases.items()
                        if _name_key(alias, convert) == key and int(code) in names})
    if not matches:
        matches = [code for code, name in normalized.items() if key and key in name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CharacterAmbiguous([f'{names[code]}（{code}）' for code in matches])
    raise CharacterNotFound(f'未找到角色「{query}」，请使用完整角色名。')


def integer(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return None


def number(value) -> Decimal | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _first_number(*values) -> int | None:
    return next((parsed for value in values if (parsed := integer(value)) is not None), None)


def _text(value: int | None) -> str:
    return f'{value:,}' if value is not None else '未知'


def _value_text(value, value_type) -> str:
    parsed = number(value)
    if parsed is None:
        return '未知'
    if value_type == 'Percent':
        return f'{parsed / 100:.2f}%'
    if value_type is None:
        return '未知'
    return format(parsed.normalize(), 'f')


def overload_display_number(key, raw, unit):
    """Reduced charge time/reticle size is a positive speed/accuracy bonus.

    Keep raw_value and source_value_type intact for audit and future use.
    Other signed attributes must not silently lose their direction.
    """
    value=number(raw)
    if value is not None and unit=='Percent' and key in {'StatChargeTime','StatHitRate','StatAccuracyCircle','OnHitRatio'}:
        return abs(value)
    return value


def normalize_overload_context(context: dict) -> dict:
    """Copy a saved/fresh context and normalize only reviewed T10 percentages.

    Reviewed T10 function identifiers establish percentage semantics even when
    the local option table lags the API or saved line provenance is incomplete.
    Known overload Integer/Percent values share the raw hundredth-percent scale;
    other units (including custom Number), unknown effects and non-T10 stay as-is.
    Raw values and their signs are never rewritten or inferred from display text.
    """
    result = deepcopy(context)
    gear = result.get('gear')
    if not isinstance(gear, list):
        return result
    for item in gear:
        if not isinstance(item, dict) or item.get('tier') != 10:
            continue
        lines = item.get('lines')
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            functions = line.get('functions')
            if not isinstance(functions, list):
                continue
            changed = False
            for fn in functions:
                if not isinstance(fn, dict):
                    continue
                key = fn.get('key')
                if not isinstance(key, str) or key not in STAT_NAMES:
                    continue
                source_type = fn.get('source_value_type', fn.get('value_type'))
                if source_type not in ('Integer', 'Percent'):
                    continue
                fn.setdefault('source_value_type', source_type)
                fn['value_type'] = 'Percent'
                fn['value'] = _value_text(overload_display_number(key, fn.get('raw_value'), 'Percent'), 'Percent')
                fn['name'] = STAT_NAMES[key]
                changed = True
            if changed:
                line['name'] = ' / '.join(str(fn.get('name', '未知词条')) for fn in functions if isinstance(fn,dict))
                line['value'] = ' / '.join(
                    str(fn.get('value', '未知')) if fn.get('value') is not None else '未知'
                    for fn in functions if isinstance(fn, dict))
    return result


def _option_index(static: StaticData) -> dict[int, dict]:
    """Map explicit static IDs to their reviewed option group rows."""
    out = {}
    for row in static.options:
        if not isinstance(row, dict):
            continue
        ids = row.get('state_effect_id_list')
        if not isinstance(ids, list):
            continue
        for value in ids:
            oid = integer(value)
            if oid is not None:
                out[oid] = row
    return out


def _option_level(oid: int | None, option: dict | None, effect: dict | None) -> tuple[int | None, str]:
    # Reviewed index.resolveOverloadOptionLevel/getOverloadLineLevel:
    # table membership first, effect-ID suffix second, first function level last.
    # This is a per-line 1..15 scale, not the four-piece aggregate 48/60 scale.
    if oid is None or oid == 0:
        return None, 'unknown'
    if option:
        ids = [integer(value) for value in option.get('state_effect_id_list') or []]
        if oid in ids:
            index = ids.index(oid)
            record_id = integer(option.get('id'))
            suffix = record_id % 10 if record_id is not None else 0
            level = (suffix - 1) * 5 + index + 1 if 1 <= suffix <= 3 else index + 1
            if 1 <= level <= 15:
                return level, 'static'
    suffix = oid % 100
    if 1 <= suffix <= 15:
        return suffix, 'effect_id'
    functions = (effect or {}).get('function_details')
    if isinstance(functions, list) and functions and isinstance(functions[0], dict):
        level = integer(functions[0].get('level'))
        if level is not None and 1 <= level <= 15:
            return level, 'function'
    return None, 'unknown'


def _line(index: int, oid: int | None, effects: dict[int, dict], options: dict[int, dict]) -> dict:
    line = {'index': index, 'id': oid, 'name': '未知词条', 'value': '未知',
            'status': 'unknown', 'level': None, 'level_source': 'unknown', 'functions': []}
    if oid == 0:
        return dict(line, name='未获得词条', value='—', status='empty')
    effect = effects.get(oid) if oid is not None else None
    option = options.get(oid) if oid is not None else None
    level, source = _option_level(oid, option, effect)
    line['level'], line['level_source'] = level, source
    if level is not None:
        # cube-icon-DTXVNhSp.js L(level): >14 full, >=12 partial, else none.
        line['status'] = 'max' if level == 15 else 'rare' if level >= 12 else 'normal'
    if option and isinstance(option.get('description_localkey'), str):
        line['name'] = option['description_localkey'].strip('【】') or '未知词条'
    if not isinstance(effect, dict):
        return line
    functions = []
    raw_functions = effect.get('function_details')
    if not isinstance(raw_functions, list):
        return line
    for fn in raw_functions:
        if not isinstance(fn, dict):
            continue
        key = fn.get('function_type')
        key = key if isinstance(key, str) else None
        functions.append({'key': key if isinstance(key, str) else None,
                          'name': STAT_NAMES.get(key, key or '未知词条'),
                          'value': _value_text(fn.get('function_value'), fn.get('function_value_type')),
                          'raw_value': fn.get('function_value'),
                          'source_value_type': fn.get('function_value_type'),
                          'value_type': fn.get('function_value_type'),
                          'level': level,
                          'source_level': integer(fn.get('level'))})
    if functions:
        line['functions'] = functions
        line['name'] = ' / '.join(fn['name'] for fn in functions)
        line['value'] = ' / '.join(fn['value'] for fn in functions)
        if len(functions) == 1:
            line['level'] = functions[0]['level']
    return line


def _table_index(rows: Iterable[dict] | None, key: str) -> dict[int, dict]:
    indexed, duplicates = {}, set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        identifier = integer(row.get(key))
        if identifier is None or identifier == 0:
            continue
        if identifier in indexed:
            duplicates.add(identifier)
        indexed[identifier] = row
    for identifier in duplicates:
        indexed.pop(identifier, None)
    return indexed


def _icon(record: dict | None, field: str, path: str) -> tuple[str | None, str | None]:
    key = (record or {}).get(field)
    if not isinstance(key, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,160}', key) is None:
        return None, None
    return key, f'/icon/{path}/{key}.png'


def build_character_context(roster: dict, detail: dict, state_effects: Iterable[dict], static: StaticData, *,
                            area_label: str = '', nickname: str = '',
                            equipment_items: Iterable[dict] | None = None,
                            skill_icons: Iterable[dict] | None = None) -> dict:
    """Build four slots and preserve per-line IDs, missing values and explicit 0.

    parse_character supplies reviewed static metadata. Its legacy numeric zero
    fallback is replaced here with nullable numbers sourced from actual fields.
    """
    code = _first_number(roster.get('name_code'), detail.get('name_code'))
    if code is None or code <= 0:
        raise ValueError('角色响应缺少有效 name_code')
    detail_code = integer(detail.get('name_code'))
    if detail_code is not None and detail_code != code:
        raise ValueError('角色详情与列表的 name_code 不一致')
    clean_roster = {key: integer(value) for key, value in roster.items() if integer(value) is not None}
    clean_detail = {key: integer(value) for key, value in detail.items() if integer(value) is not None}
    parsed = parse_character(clean_roster, clean_detail, [], static)
    result = {key: parsed[key] for key in ('name_code', 'name', 'rarity', 'char_class', 'burst', 'element', 'corporation')}
    resource_id = integer(static.character(code).get('resource_id'))
    result['weapon_type'] = static_weapon_type(static.character(code))
    selection = resolve_skin(roster, static, detail=detail)
    result.update(resource_id=resource_id if resource_id else None, costume_id=selection.costume_id,
                   skin_index=selection.skin_index, skin_source=selection.source,
                   skin_reported=selection.reported, skin_mapped=selection.mapped, skin_notice=selection.notice,
                  combat=_first_number(roster.get('combat'), detail.get('combat')),
                  level=integer(roster.get('lv')), grade=_first_number(roster.get('grade'), detail.get('grade')),
                  core=_first_number(roster.get('core'), detail.get('core')),
                  arena_combat=integer(detail.get('arena_combat')), bond=integer(detail.get('attractive_lv')),
                  area_label=area_label, nickname=nickname,
                  generated_at=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M'))
    result['combat_text'] = _text(result['combat'])
    result['level_text'] = _text(result['level'])
    skill_record = _table_index(skill_icons, 'resource_id').get(resource_id)
    skill_fields = {'skill1': 'skill1_icon', 'skill2': 'skill2_icon', 'burst': 'ulti_skill_icon'}
    result['skills'] = []
    for slot, label, key in SKILLS:
        icon_key, icon_path = _icon(skill_record, skill_fields[slot], 'skill/char_skill')
        result['skills'].append({'slot': slot, 'name': label, 'level': integer(detail.get(key)),
                                 'icon_key': icon_key, 'icon_path': icon_path})
    equipment = _table_index(equipment_items, 'id')
    effects = {integer(row.get('id')): row for row in state_effects if isinstance(row, dict) and integer(row.get('id')) is not None}
    options = _option_index(static)
    gear = []
    for slot, label in SLOTS:
        tier = integer(detail.get(f'{slot}_equip_tier'))
        ids = [integer(detail.get(f'{slot}_equip_option{i}_id')) for i in (1, 2, 3)]
        tid = integer(detail.get(f'{slot}_equip_tid'))
        icon_key, icon_path = _icon(equipment.get(tid), 'resource_id', 'equip')
        gear.append({'slot': slot, 'label': label, 'tier': tier,
                     'lv': integer(detail.get(f'{slot}_equip_lv')), 'tid': tid,
                     'icon_key': icon_key, 'icon_path': icon_path, 'option_ids': ids,
                     'lines': [_line(index, oid, effects, options) for index, oid in enumerate(ids, 1)] if tier == 10 else []})
    result['gear'] = gear
    result['cube'] = {'tid': integer(detail.get('harmony_cube_tid')), 'lv': integer(detail.get('harmony_cube_lv'))}
    result['favorite'] = {'tid': integer(detail.get('favorite_item_tid')), 'lv': integer(detail.get('favorite_item_lv'))}
    return normalize_overload_context(result)
