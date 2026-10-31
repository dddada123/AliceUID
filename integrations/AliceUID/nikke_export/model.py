"""Export the same normalized equipment values as character panels, without IO."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import re
import unicodedata

from ..nikke_character.builder import build_character_context, integer, overload_display_number
from ..nikke_character.draw import aggregate_options, _LABELS
from ..nikke_character.service import CharacterQueryService

TZ = timezone(timedelta(hours=8))
MAX_CHARACTERS = 500
UNKNOWN = '未知'


class ExportError(ValueError):
    pass


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = 'text'
    hidden: bool = False


@dataclass
class ExportData:
    commander: dict
    rows: list[dict]
    columns: list[Column]
    exported_at: datetime
    cache_time: datetime
    filename: str


def display(value):
    return UNKNOWN if value is None or value == '' else str(value)


def clean_text(value):
    # Keep user text literal and valid in XML; credentials are never accepted here.
    return ''.join(c for c in str(value or '') if c in '\n\t' or unicodedata.category(c) != 'Cc')[:512]


def file_part(value):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', clean_text(value)).strip(' .')
    return (text or UNKNOWN)[:48]


def burst_label(value):
    return {'1': 'Ⅰ', '2': 'Ⅱ', '3': 'Ⅲ', 'AllStep': '全阶段'}.get(str(value), UNKNOWN)


def matches(row, burst='全部', role='全部', company='全部', element='全部'):
    stage = row['burst']
    return ((burst == '全部' or stage == burst or (stage == '全阶段' and burst in ('Ⅰ', 'Ⅱ', 'Ⅲ')))
            and (role == '全部' or row['role'] == role)
            and (company == '全部' or row['company'] == company)
            and (element == '全部' or row['element'] == element))


def _line_values(line):
    if line.get('status') == 'empty':
        return '未开启', '', '', ''
    functions = line.get('functions', [])
    if len(functions) == 1:
        fn = functions[0]
        number = overload_display_number(fn.get('key'), fn.get('raw_value'), fn.get('value_type'))
        unit = fn.get('value_type')
        value = float(number / 10000 if unit == 'Percent' else number) if number is not None and unit else UNKNOWN
        return clean_text(line.get('name') or UNKNOWN), value, line.get('level') or UNKNOWN, unit or UNKNOWN
    return (clean_text(line.get('name') or UNKNOWN), clean_text(line.get('value') or UNKNOWN),
            line.get('level') or UNKNOWN, '复合' if functions else UNKNOWN)


def _aggregates(gear):
    # Keep exact raw arithmetic and separate units, as aggregate_options does.
    groups = {}
    for item in gear:
        if item.get('tier') != 10:
            continue
        for line in item.get('lines', []):
            if line.get('status') == 'empty':
                continue
            for fn in line.get('functions', []):
                key, unit = fn.get('key'), fn.get('value_type')
                group = groups.setdefault((key, unit), dict(name=fn.get('name') or key or UNKNOWN,
                                                           total=Decimal(0), known=0, unknown=0))
                value = overload_display_number(key, fn.get('raw_value'), unit)
                if value is None or key is None or unit is None:
                    group['unknown'] += 1
                else:
                    group['total'] += value
                    group['known'] += 1
    return groups


def prepare(snapshot, bind, static, *, region, now=None, equipment=None):
    if not isinstance(snapshot, dict) or snapshot.get('complete') is not True:
        raise ExportError('没有完整的本地练度缓存，请先刷新面板。')
    roster, details, profile = snapshot.get('roster'), snapshot.get('details'), snapshot.get('profile')
    try:
        codes = CharacterQueryService.roster_codes(roster)
    except ValueError as exc:
        raise ExportError('本地角色列表无效，请先刷新面板。') from exc
    if (not isinstance(details, dict) or set(details) != {str(c) for c in codes}
            or not isinstance(profile, dict) or profile.get('chars') != roster
            or not all(isinstance(profile.get(k), dict) for k in ('basic', 'saved', 'player', 'outpost'))):
        raise ExportError('本地角色详情不完整，请先刷新面板。')
    if not codes:
        raise ExportError('本地缓存中没有已拥有的妮姬，请先刷新面板。')
    if len(codes) > MAX_CHARACTERS:
        raise ExportError('角色数量超出当前导出上限，请联系管理员检查。')
    stamp = snapshot.get('saved_at')
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or stamp <= 0:
        raise ExportError('本地缓存缺少有效更新时间，请先刷新面板。')
    try:
        cache_time = datetime.fromtimestamp(stamp, TZ)
    except (ValueError, OverflowError, OSError) as exc:
        raise ExportError('缓存更新时间无效，请先刷新面板。') from exc
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError('export clock must be timezone-aware')
    now = now.astimezone(TZ)
    basic, saved, player = profile['basic'], profile['saved'], profile['player']
    commander = dict(name=clean_text(basic.get('nickname') or saved.get('role_name') or bind.nickname or '未知指挥官'),
                     uid=clean_text(saved.get('role_id') or getattr(bind, 'uid', '') or UNKNOWN),
                     region=clean_text(region), level=integer(basic.get('lv')) or integer(player.get('player_level')),
                     count=len(codes))
    columns = [Column(k, label, kind) for k, label, kind in (
        ('code', '妮姬编号', 'integer'), ('name', '妮姬名称', 'text'), ('burst', '爆裂阶段', 'text'),
        ('role', '角色定位', 'text'), ('company', '企业', 'text'), ('rarity', '稀有度', 'text'),
        ('element', '属性代码', 'text'), ('weapon', '武器类型', 'text'),
        ('level', '角色等级', 'integer'), ('combat', '战力', 'integer'), ('arena_combat', '竞技场战力', 'integer'),
        ('grade', '突破', 'integer'), ('core', '核心', 'integer'), ('bond', '好感等级', 'integer'),
        ('skill1', '技能一等级', 'integer'), ('skill2', '技能二等级', 'integer'), ('burst_skill', '爆裂技能等级', 'integer'),
        ('cube', '魔方ID', 'text'), ('cube_lv', '魔方原始等级', 'integer'),
        ('favorite', '收藏品ID', 'text'), ('favorite_lv', '收藏品原始等级', 'integer'),
        ('attack', '最终攻击力', 'integer'), ('defense', '最终防御力', 'integer'), ('hp', '最终生命值', 'integer'),
        ('tier_total', '已知词条阶数合计', 'integer'), ('unknown_lines', '未知阶数词条数', 'integer'),
        ('max_lines', '15阶词条数', 'integer'), ('rare_lines', '12至14阶词条数', 'integer'),
    )]
    for kind, title in (('cube', '魔方'), ('favorite', '收藏品')):
        columns.extend([Column(kind+'_name', title+'名称'), Column(kind+'_display_lv', title+'面板显示等级', 'integer'),
                        Column(kind+'_rarity', title+'稀有度'), Column(kind+'_notice', title+'资料状态')])
    for slot, label in (('head', '头部'), ('torso', '躯干'), ('arm', '手臂'), ('leg', '腿部')):
        columns.extend([Column(slot+'_tier', label+'品级', 'integer'), Column(slot+'_lv', label+'强化等级', 'integer'),
                        Column(slot+'_id', label+'装备ID')])
        for i in (1, 2, 3):
            prefix = f'{slot}_{i}'
            columns.extend([Column(prefix+'_name', f'{label}词条{i}属性'), Column(prefix+'_value', f'{label}词条{i}数值', 'affix'),
                            Column(prefix+'_level', f'{label}词条{i}阶数', 'integer'), Column(prefix+'_unit', f'{label}词条{i}单位')])
    rows, group_definitions = [], {}
    for owned in sorted(roster, key=lambda row: int(row['name_code'])):
        code = int(owned['name_code'])
        entry = details[str(code)]
        if (not isinstance(entry, dict) or not isinstance(entry.get('detail'), dict)
                or integer(entry['detail'].get('name_code')) != code or not isinstance(entry.get('effects'), list)
                or not all(isinstance(effect, dict) for effect in entry['effects'])):
            raise ExportError('本地角色详情不匹配，请先刷新面板。')
        context = build_character_context(owned, entry['detail'], entry['effects'], static)
        aggregate = aggregate_options(context['gear'])
        row = dict(code=code, name=clean_text(context['name']), burst=burst_label(context['burst']),
                   role=_LABELS.get(context['char_class'], context['char_class'] or UNKNOWN),
                   company=_LABELS.get(context['corporation'], context['corporation'] or UNKNOWN),
                   rarity=context['rarity'] or UNKNOWN, element=_LABELS.get(context['element'], context['element'] or UNKNOWN),
                   weapon=context['weapon_type'] or UNKNOWN, **{k: context[k] if context[k] is not None else UNKNOWN for k in
                       ('level', 'combat', 'arena_combat', 'grade', 'core', 'bond')},
                   skill1=context['skills'][0]['level'], skill2=context['skills'][1]['level'], burst_skill=context['skills'][2]['level'],
                   cube=str(context['cube']['tid']) if context['cube']['tid'] is not None else UNKNOWN, cube_lv=context['cube']['lv'],
                   favorite=str(context['favorite']['tid']) if context['favorite']['tid'] is not None else UNKNOWN,
                   favorite_lv=context['favorite']['lv'], attack='未提供', defense='未提供', hp='未提供',
                   tier_total=int(aggregate['level']) if aggregate['level'] != UNKNOWN else UNKNOWN,
                   unknown_lines=aggregate['unknown_lines'], max_lines=0, rare_lines=0)
        for item in context['gear']:
            slot = item['slot']
            row.update({slot+'_tier': item['tier'], slot+'_lv': item['lv'], slot+'_id': str(item['tid']) if item['tid'] is not None else UNKNOWN})
            label = '未装备' if item['tid'] == 0 else f'T{display(item["tier"])} · Lv.{display(item["lv"])}'
            row['_'+slot] = item['label']+'\n'+label
            for i in (1, 2, 3):
                if item['tier'] == 10:
                    values = _line_values(item['lines'][i-1])
                else:
                    values = (('未装备' if item['tid'] == 0 else '无超载词条' if item['tier'] is not None else '装备未知'), '', '', '')
                row.update({f'{slot}_{i}_{key}': value for key, value in zip(('name','value','level','unit'), values)})
                row['max_lines'] += values[2] == 15
                row['rare_lines'] += isinstance(values[2], int) and 12 <= values[2] <= 14
        equipment_text = {}
        for kind, title in (('cube', '魔方'), ('favorite', '收藏品')):
            info = (equipment or {}).get(code, {}).get(kind, {})
            row[kind+'_name'] = clean_text(info.get('name') or ('未装备'+title if row[kind] == '0' else title+'资料未知'))
            row[kind+'_display_lv'] = info.get('display_level', UNKNOWN)
            row[kind+'_rarity'] = info.get('rarity') or UNKNOWN
            row[kind+'_notice'] = clean_text(info.get('notice') or ('本地元数据未提供' if not info else info.get('status')))
            if info.get('display_level') is not None:
                equipment_text[kind] = f'{row[kind+"_name"]}  Lv.{info["display_level"]}'
            elif row[kind] == '0':
                equipment_text[kind] = '未装备'+title
            else:
                equipment_text[kind] = f'{title} #{row[kind]}  原始Lv.{display(row[kind+"_lv"])}'
        row['_unparsed'] = any(line.get('status') != 'empty' and not line.get('functions')
                               for item in context['gear'] for line in item.get('lines', []))
        groups = _aggregates(context['gear'])
        row['_groups'] = groups
        group_definitions.update({key: value['name'] for key, value in groups.items()})
        row['_title'] = f'{code}  {row["name"]}'
        row['_meta'] = f'{row["rarity"]}  爆裂{row["burst"]}  {row["role"]}  {row["company"]}  {row["element"]}'
        row['_power'] = '战力  '+ (f'{row["combat"]:,}' if isinstance(row['combat'], int) else UNKNOWN)
        lines = [f'等级 {display(row["level"])}    突破 {display(row["grade"])}    核心 {display(row["core"])}',
                 f'技能 {display(row["skill1"])}/{display(row["skill2"])}/{display(row["burst_skill"])}    好感 {display(row["bond"])}',
                 equipment_text['cube'], equipment_text['favorite'],
                 '最终攻 / 防 / 生命：缓存未提供',
                 f'词条阶数合计 {row["tier_total"]}'+('（含未知）' if row['unknown_lines'] else ''),
                 f'15阶 {row["max_lines"]}条    12～14阶 {row["rare_lines"]}条',
                 '', '四件装备 · 同类词条汇总']
        lines.extend(f'{item["name"]}  {item["value"]}' for item in aggregate['rows'])
        if not aggregate['rows']:
            lines.append('无有效超载词条')
        row['_summary'] = '\n'.join(lines)
        rows.append({k: UNKNOWN if v is None else v for k, v in row.items()})
    for index, (group, name) in enumerate(sorted(group_definitions.items(), key=lambda item: str(item[0]))):
        key, unit = group
        colkey = f'sum_{index}'
        columns.append(Column(colkey, f'{name}合计（{unit or UNKNOWN}）', 'percent' if unit == 'Percent' else 'number'))
        columns.append(Column(colkey+'_state', f'{name}汇总状态（{unit or UNKNOWN}）'))
        for row in rows:
            item = row['_groups'].get(group)
            if item is None:
                row[colkey], row[colkey+'_state'] = (UNKNOWN, '含未解析词条') if row['_unparsed'] else (0, '无此词条')
            elif not item['known'] or item['unknown'] or row['_unparsed']:
                row[colkey] = float(item['total'] / 10000 if unit == 'Percent' else item['total']) if item['known'] else UNKNOWN
                row[colkey+'_state'] = '部分已知' if item['known'] else UNKNOWN
            else:
                row[colkey] = float(item['total'] / 10000 if unit == 'Percent' else item['total'])
                row[colkey+'_state'] = '完整'
    for key in ('_title', '_meta', '_power', '_summary', '_head', '_torso', '_arm', '_leg', '_match', '_rank', '_position'):
        columns.append(Column(key, key, hidden=True))
    name = '·'.join(file_part(commander[k]) for k in ('name', 'region', 'uid'))
    filename = f'[AliceUID]{name}·NIKKE练度表_{now:%Y%m%d%H%M}.xlsx'
    return ExportData(commander, rows, columns, now, cache_time, filename)
