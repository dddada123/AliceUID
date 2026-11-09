"""Versioned numerical JSON; deliberately excludes spreadsheet layout and secrets."""
import json
from ..version import VERSION
from ..nikke_character.attributes import FORMULA_VERSION
from .model import ExportError

def build_json(data):
    columns = [c for c in data.columns if not c.hidden and not c.key.startswith('sum_')]
    characters = []
    for row in data.rows:
        item = {}
        for column in columns:
            value = row.get(column.key)
            if column.kind != 'text' and isinstance(value, str) and value in ('未知', '未提供', ''):
                value = None
            item[column.key] = value
        item['attributes_metadata'] = data.metadata.get('attributes', {}).get(str(row['code']), {})
        item['overload_totals'] = [dict(function_type=key, unit=unit,
            value=float(group['total'] / 10000 if unit == 'Percent' else group['total']),
            complete=not group['unknown'] and not row['_unparsed'])
            for (key, unit), group in row['_groups'].items()]
        characters.append(item)
    document = dict(schema_version=1, plugin_version=VERSION, formula_version=FORMULA_VERSION,
                    exported_at=data.exported_at.isoformat(), snapshot_saved_at=data.cache_time.isoformat(),
                    source=data.metadata.get('source', 'owner_cache'), target_level=data.metadata.get('target_level'),
                    commander=data.commander, character_count=len(characters),
                    complete=True, attributes_complete=all(r['attribute_status'] == '完整' for r in data.rows),
                    field_dictionary={c.key: dict(label=c.label, type=c.kind) for c in columns},
                    units=dict(Percent='比例数值；0.1181表示11.81%', integer='整数',
                               level='实际等级；target_level为本次计算等级', combat='实际服务器战力，非模拟战力',
                               cube_lv='接口原始等级', favorite_lv='接口原始等级；珍藏品显示阶段另列',
                               null='未知或未提供，不代表0'), characters=characters)
    body = json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(body) > 12 * 1024 * 1024:
        raise ExportError('JSON练度文件超出12MB上限，已停止发送。')
    return body
