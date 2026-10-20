"""Owned-only icon roster; fingerprint only fields used by the current sheet."""
from __future__ import annotations
import hashlib
import json
from ..nikke_resource.skins import resolve_skin
from ..nikke_resource.card_meta import card_metadata, integer


def number(value):
    if isinstance(value, bool):
        raise ValueError('角色数据格式无效')
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        raise ValueError('角色数据格式无效') from None


def build_roster_context(basic, owned, static, *, nickname='', uid='', area_label=''):
    if not isinstance(basic, dict) or not isinstance(owned, list):
        raise ValueError('角色列表响应格式发生变化')
    seen, cards = set(), []
    for raw in owned:
        if not isinstance(raw, dict):
            raise ValueError('角色列表响应格式发生变化')
        code = number(raw.get('name_code'))
        if code <= 0 or code in seen:
            raise ValueError('角色列表存在无效或重复记录')
        seen.add(code)
        skin = resolve_skin(raw, static)
        grade = integer(raw.get('grade'))
        core = integer(raw.get('core'))
        grade = grade if grade is None or grade >= 0 else None
        core = core if core is None or core >= 0 else None
        stars = '突破未知' if grade is None else '未突破' if grade == 0 else f'★×{grade}'
        core_text = ('MAX' if core == 7 else f'+{core}') if core else ''
        cards.append(dict(name_code=code, name=static.name(code), resource_id=static.resource_id(code),
            grade=grade, core=core, stars=stars, core_text=core_text,
            **card_metadata(raw, static.character(code)),
            skin_index=skin.skin_index, costume_id=skin.costume_id, skin_source=skin.source,
            skin_reported=skin.reported, skin_mapped=skin.mapped, skin_notice=skin.notice,
            _sort_combat=number(raw.get('combat'))))
    cards.sort(key=lambda row: (-row['_sort_combat'], row['name_code']))
    # Combat determines visible order, but its numeric value is not displayed.
    # A value-only change must not invalidate the icon sheet; reorder still does.
    for row in cards:
        row.pop('_sort_combat')
    return dict(nickname=str(basic.get('nickname') or nickname or '未知指挥官'), uid=str(uid or '尚未取得'),
                area_label=area_label, cards=cards, count=len(cards), total=len(static.characters),
                rows_count=(len(cards) + 9) // 10, preview_notice='')


def fingerprint(context):
    """Stable ordered image inputs; no fetch/render timestamps or data URIs."""
    frame = {key:value for key,value in context.items()
             if key not in {'star_on','star_off','core_icon','neutral_frame'}}
    if 'cards' in frame:
        frame['cards'] = [{key: value for key, value in row.items()
                           if key not in {'icon_source', 'portrait_source', 'combat', 'level', 'lv',
                                          'role_icons','weapon_icon','burst_icon','element_icon','element_frame','_sort_combat'}}
                          for row in frame['cards']]
    return hashlib.sha256(json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
