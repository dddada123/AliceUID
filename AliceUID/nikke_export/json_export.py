"""Versioned numerical JSON; deliberately excludes spreadsheet layout and secrets."""
import json
import math
from ..version import VERSION
from ..nikke_character.attributes import FORMULA_VERSION
from .model import ExportError


def safe_attributes(value):
    """Only character data is passed here; strip credentials even in extensions."""
    if isinstance(value, dict):
        return {str(k): safe_attributes(v) for k, v in value.items()
                if not any(word in str(k).lower() for word in
                    ('cookie', 'token', 'password', 'secret', 'openid', 'open_id', 'credential', 'email'))
                and str(k).lower() not in ('uid', 'user_id', 'role_id', 'account')}
    if isinstance(value, list):
        return [safe_attributes(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ExportError('角色原始属性含无效数值，请刷新面板。')
    return value

def build_json(data):
    columns = [c for c in data.columns if not c.hidden and not c.key.startswith('sum_')]
    characters = []
    effects, equipment, effect_keys, equipment_keys = [], [], {}, {}
    raw_characters = {}
    def intern(value, values, keys):
        value = safe_attributes(value)
        key = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if key not in keys:
            keys[key] = len(values)
            values.append(value)
        return keys[key]
    for row in data.rows:
        item = {}
        for column in columns:
            value = row.get(column.key)
            if column.kind != 'text' and isinstance(value, str) and value in ('未知', '未提供', ''):
                value = None
            item[column.key] = value
        attr = data.metadata.get('attributes', {}).get(str(row['code']), {})
        # These numbers/versions already exist in the character row or header.
        item['attributes_metadata'] = {k:v for k,v in attr.items() if k not in
            ('attack','defense','hp','actual_level','target_level','formula_version','source','original')}
        item['overload_totals'] = [dict(function_type=key, unit=unit,
            value=float(group['total'] / 10000 if unit == 'Percent' else group['total']),
            complete=not group['unknown'] and not row['_unparsed'])
            for (key, unit), group in row['_groups'].items()]
        characters.append(item)
        raw = data.metadata.get('raw_characters', {}).get(str(row['code']), {})
        public = dict(attr.get('original') or {})
        for kind in ('cube', 'favorite'):
            if kind in public:
                public[kind+'_ref'] = intern(public.pop(kind), equipment, equipment_keys)
        raw_characters[str(row['code'])] = dict(roster=safe_attributes(raw.get('roster', {})),
            detail=safe_attributes(raw.get('detail', {})), public_attributes=safe_attributes(public),
            effect_refs=[intern(effect, effects, effect_keys) for effect in raw.get('effects', [])])
    document = dict(schema_version=2, plugin_version=VERSION, formula_version=FORMULA_VERSION,
                    exported_at=data.exported_at.isoformat(), snapshot_saved_at=data.cache_time.isoformat(),
                    source=data.metadata.get('source', 'owner_cache'), target_level=data.metadata.get('target_level'),
                    commander=data.commander, character_count=len(characters),
                    complete=True, attributes_complete=all(r['attribute_status'] == '完整' for r in data.rows),
                    field_dictionary={c.key: dict(label=c.label, type=c.kind) for c in columns},
                    units=dict(Percent='比例数值；0.1181表示11.81%', integer='整数',
                               level='实际等级；target_level为本次计算等级', combat='实际服务器战力，非模拟战力',
                               cube_lv='接口原始等级', favorite_lv='接口原始等级；珍藏品显示阶段另列',
                               null='未知或未提供，不代表0', critical_ratio='官网原始值乘0.0001为基础暴击率',
                               critical_damage='public_attributes中为官网原始值；characters中为倍率比例',
                               raw='raw_character_data保留接口属性及当前等级公开属性；完整公开成长资料在本地公共缓存',
                               refs='effect_refs/cube_ref/favorite_ref为对应共享数组的0基索引'),
                    characters=characters, raw_character_data=raw_characters,
                    state_effects=effects, equipment_metadata=equipment)
    body = json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(body) > 12 * 1024 * 1024:
        raise ExportError('JSON练度文件超出12MB上限，已停止发送。')
    return body
