"""Character-card extras built only from reported equipment and reviewed static rows."""
from __future__ import annotations

from ..nikke_api.parser import static_weapon_type
from ..nikke_resource.cache import image_data_uri
from ..nikke_resource.base_icons import ELEMENT_KEYS, WEAPON_URLS, POWER_PRESENTATION
from ..nikke_resource.collections import CollectionMetadata, WEAPONS, TOKEN, identifier


async def _icon(images, kind, key, prefix):
    if not isinstance(key, str) or not TOKEN.fullmatch(key):
        return None
    if kind in {'attributes', 'corporations'} and callable(getattr(images, 'get_base_icon', None)):
        data = await images.get_base_icon(kind, key)
    else:
        data = await images.get_asset(kind, key, prefix + key + '.png')
    return image_data_uri(data, (256, 256)) if data else None


def _base(fact, label):
    tid, lv = identifier(fact.get('tid')), identifier(fact.get('lv'))
    result = {'status': 'unknown', 'name': '未知' + label, 'rarity': None,
              'display_level': None, 'raw_level': lv, 'icon_url': None,
              'notice': '接口未报告有效装备记录', 'type_label': label}
    if tid == 0:
        result.update(status='not_equipped', name='未装备' + label, notice='接口报告未装备')
    return tid, lv, result


async def equipment_info(context, metadata, images, *, cube=False):
    label = '魔方' if cube else '收藏品'
    fact = context.get('cube' if cube else 'favorite')
    tid, lv, result = _base(fact if isinstance(fact, dict) else {}, label)
    if not tid:
        return result
    row = await metadata.get('cubes' if cube else 'collections', tid)
    if row is None:
        result.update(status='unknown' if cube else 'metadata_unavailable', name=f'未知{label} #{tid}',
                      notice='已报告装备，公开元数据暂不可用')
        return result
    rarity = row['item_rare' if cube else 'favorite_rare']
    label = '魔方' if cube else '珍藏品' if rarity == 'SSR' else '收藏品'
    result.update(status='equipped', name=row['name_localkey'], rarity=rarity, type_label=label, notice='')
    if not cube:
        exclusive = identifier(row.get('name_code'))
        weapon = context.get('weapon_type')
        if exclusive and exclusive != identifier(context.get('name_code')):
            result.update(status='mismatch', notice='专属角色与当前角色不匹配')
            return result
        if weapon and weapon != row['weapon_type']:
            result.update(status='mismatch', notice='适用武器与当前角色不匹配')
            return result
        if not weapon:
            result['notice'] = '角色武器资料缺失，适用武器未核对'
    index = lv - 1 if cube and lv is not None else lv
    bounds = [len(row[key]) for key in ('atk', 'def', 'hp', 'powers', 'grade') if isinstance(row.get(key), list)]
    valid = index is not None and index >= 0 and (not bounds or index < min(bounds))
    if not cube:
        valid = valid and lv <= row['max_level']
    if valid:
        result['display_level'] = lv if cube or rarity != 'SSR' else lv + 1
    else:
        result['notice'] = (result['notice'] + ' · ' if result['notice'] else '') + ('等级未知' if lv is None else '等级越界或无效')
    key = f"ie_{row['resource_id']}" if cube else str(row['icon_resource_id'])
    result['icon_url'] = await _icon(images, 'cubes' if cube else 'favorites', key,
                                     '/icon/equip/' if cube else '/icon/favoriteitem/')
    if result['icon_url'] is None:
        result['notice'] = (result['notice'] + ' · ' if result['notice'] else '') + '图标暂不可用'
    return result


async def role_icons(row, images):
    row = row if isinstance(row, dict) else {}
    element_id = row.get('element_id')
    element = element_id.get('element') if isinstance(element_id, dict) else None
    element = element if isinstance(element, dict) else {}
    details = row.get('element_details')
    if not element and isinstance(details, list) and details and isinstance(details[0], dict):
        element = details[0]
    element_key = element.get('element_icon')
    element_key = element_key if isinstance(element_key, str) and element_key in ELEMENT_KEYS else None
    element_name = element.get('element')
    element_name = element_name if isinstance(element_name, str) else None
    element_label = {'Fire': '燃烧', 'Water': '水冷', 'Wind': '风压', 'Electric': '电击', 'Electronic': '电击', 'Iron': '铁甲'}.get(element_name, '属性未知')
    char_class = row.get('class')
    char_class = char_class if isinstance(char_class, str) else None
    class_label = {'Attacker': '火力型', 'Defender': '防御型', 'Supporter': '辅助型'}.get(char_class, '职业未知')
    class_key = 'icn_class_' + char_class.lower() if char_class in {'Attacker', 'Defender', 'Supporter'} else None
    burst = row.get('use_burst_skill')
    burst = burst if isinstance(burst, str) else None
    burst_key = {'Step1': '01', 'Step2': '02', 'Step3': '03', 'AllStep': 'all'}.get(burst)
    burst_label = {'Step1': '爆裂Ⅰ', 'Step2': '爆裂Ⅱ', 'Step3': '爆裂Ⅲ', 'AllStep': '全阶段爆裂'}.get(burst, '爆裂未知')
    corp = row.get('corporation')
    corp = corp.lower() if isinstance(corp, str) else None
    corp_num = {'elysion': '01', 'missilis': '02', 'tetra': '03', 'pilgrim': '04', 'abnormal': '05'}.get(corp)
    corp_label = {'elysion': '极乐净土', 'missilis': '米西利斯', 'tetra': '泰特拉', 'pilgrim': '朝圣者', 'abnormal': '反常'}.get(corp, '企业未知')
    specs = [('element', element_label, element_key, 'attributes'),
             ('class', class_label, class_key, 'attributes'),
             ('burst', burst_label, 'icn_burst_' + burst_key if burst_key else None, 'attributes'),
             ('corporation', corp_label, 'icn_corp_' + corp_num if corp_num else None, 'corporations')]
    result = []
    for kind, label, key, image_kind in specs:
        url = await _icon(images, image_kind, key, '/icon/atlas_common_corp/' if image_kind == 'corporations' else '/icon/atlas_common_class/')
        result.append({'kind': kind, 'label': label, 'icon_url': url, 'missing': url is None})
    weapon = static_weapon_type(row)
    weapon = weapon if isinstance(weapon, str) else None
    weapon_url = WEAPON_URLS.get(weapon)
    data = await images.get_asset('weapons', weapon, weapon_url) if weapon_url else None
    url = image_data_uri(data, (128, 128)) if data else None
    result.append({'kind': 'weapon', 'label': WEAPONS.get(weapon, '武器未知'), 'icon_url': url, 'missing': url is None})
    return result


async def prepare_character_extras(context, resources):
    metadata = getattr(resources, '_collection_metadata', None)
    if metadata is None:
        metadata = resources._collection_metadata = CollectionMetadata(resources.root, http=resources.http, clock=resources.clock)
    row = resources.load_static().character(context.get('name_code') or 0)
    checked = dict(context, weapon_type=static_weapon_type(row) or context.get('weapon_type'))
    from ..nikke_resource.badges import badge_sources
    badges, _ = await badge_sources(resources.images, ('core', 'star_active', 'star_inactive', 'power'))
    return {'collection': await equipment_info(checked, metadata, resources.images),
            'cube_info': await equipment_info(checked, metadata, resources.images, cube=True),
            'role_icons': await role_icons(row, resources.images),
            'core_badge_url': badges.get('core'),
            'breakthrough_badge_url': badges.get('star_active'),
            'breakthrough_empty_badge_url': badges.get('star_inactive'),
            'power_icon_url': badges.get('power'),
            'progression_badges': {'raw_core': context.get('core'), 'raw_grade': context.get('grade'),
                                   'value_source': 'reported_context', 'digits_in_base_image': False},
            'power_presentation': dict(POWER_PRESENTATION, value=context.get('combat'))}
