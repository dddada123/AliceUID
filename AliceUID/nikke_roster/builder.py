"""Main-squad and full-codex icon roster; fingerprint only fields used by the current sheet."""
from __future__ import annotations

import hashlib
import json

from ..nikke_resource.card_meta import card_metadata, integer
from ..nikke_resource.skins import resolve_skin

MAIN_SKILL_THRESHOLD = 7
_RARITY_ORDER = {'SSR': 0, 'SR': 1, 'R': 2}


def number(value):
    if isinstance(value, bool):
        raise ValueError('角色数据格式无效')
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        raise ValueError('角色数据格式无效') from None


def columns_for_main_count(count: int) -> int:
    if count <= 49:
        return 7
    if count <= 96:
        return 8
    return 10


def max_skill_level(detail_entry: dict | None) -> int:
    if not isinstance(detail_entry, dict):
        return 0
    detail = detail_entry.get('detail') if isinstance(detail_entry.get('detail'), dict) else detail_entry
    if not isinstance(detail, dict):
        return 0
    return max(
        integer(detail.get('skill1_lv')) or 0,
        integer(detail.get('skill2_lv')) or 0,
        integer(detail.get('ulti_skill_lv')) or 0,
    )


def _owned_card(raw: dict, static) -> dict:
    code = number(raw.get('name_code'))
    skin = resolve_skin(raw, static)
    grade = integer(raw.get('grade'))
    core = integer(raw.get('core'))
    grade = grade if grade is None or grade >= 0 else None
    core = core if core is None or core >= 0 else None
    stars = '突破未知' if grade is None else '未突破' if grade == 0 else f'★×{grade}'
    core_text = ('MAX' if core == 7 else f'+{core}') if core else ''
    return dict(
        name_code=code,
        name=static.name(code),
        resource_id=static.resource_id(code),
        grade=grade,
        core=core,
        stars=stars,
        core_text=core_text,
        **card_metadata(raw, static.character(code)),
        skin_index=skin.skin_index,
        costume_id=skin.costume_id,
        skin_source=skin.source,
        skin_reported=skin.reported,
        skin_mapped=skin.mapped,
        skin_notice=skin.notice,
        _sort_combat=number(raw.get('combat')),
    )


def _unowned_card(code: int, ch: dict, static) -> dict:
    rarity = str(ch.get('original_rare') or '').upper()
    return dict(
        name_code=code,
        name=static.name(code),
        resource_id=static.resource_id(code),
        grade=None,
        core=None,
        stars='未解锁',
        core_text='',
        unowned=True,
        **card_metadata({}, ch),
        skin_index=0,
        costume_id=0,
        skin_source='base',
        skin_reported=0,
        skin_mapped=True,
        skin_notice='未解锁妮姬',
        _sort_rarity=_RARITY_ORDER.get(rarity, 9),
        _sort_order=integer(ch.get('order')) or 999999,
    )


def build_roster_context(
    basic,
    owned,
    static,
    *,
    nickname='',
    uid='',
    area_label='',
    mode='owned',
    details=None,
    command_prefix='nk',
):
    if not isinstance(basic, dict) or not isinstance(owned, list):
        raise ValueError('角色列表响应格式发生变化')
    seen, owned_cards = set(), []
    for raw in owned:
        if not isinstance(raw, dict):
            raise ValueError('角色列表响应格式发生变化')
        code = number(raw.get('name_code'))
        if code <= 0 or code in seen:
            raise ValueError('角色列表存在无效或重复记录')
        seen.add(code)
        owned_cards.append(_owned_card(raw, static))
    owned_cards.sort(key=lambda row: (-row['_sort_combat'], row['name_code']))
    # Combat determines visible order, but its numeric value is not displayed.
    # A value-only change must not invalidate the icon sheet; reorder still does.
    for row in owned_cards:
        row.pop('_sort_combat')

    owned_count = len(owned_cards)
    detail_map = details if isinstance(details, dict) else {}

    if mode == 'main':
        cards = [
            row for row in owned_cards
            if max_skill_level(detail_map.get(str(row['name_code']))) >= MAIN_SKILL_THRESHOLD
        ]
        columns = columns_for_main_count(len(cards))
        unowned_cards = []
    elif mode == 'codex':
        cards = owned_cards
        columns = 10
        unowned_cards = []
        for raw_code, ch in sorted(static.characters.items()):
            code = int(raw_code)
            if code in seen or not isinstance(ch, dict):
                continue
            if ch.get('is_visible') is False or static.resource_id(code) <= 0:
                continue
            unowned_cards.append(_unowned_card(code, ch, static))
        unowned_cards.sort(key=lambda row: (row['_sort_rarity'], row['_sort_order'], row['name_code']))
        for row in unowned_cards:
            row.pop('_sort_rarity')
            row.pop('_sort_order')
    else:
        cards = owned_cards
        columns = 10
        unowned_cards = []

    return dict(
        nickname=str(basic.get('nickname') or nickname or '未知指挥官'),
        uid=str(uid or '尚未取得'),
        area_label=area_label,
        mode=mode,
        columns=columns,
        command_prefix=command_prefix,
        cards=cards,
        unowned_cards=unowned_cards,
        count=len(cards),
        owned_count=owned_count,
        unowned_count=len(unowned_cards),
        total=len(static.characters),
        rows_count=(len(cards) + columns - 1) // columns,
        preview_notice='',
    )


def fingerprint(context):
    """Stable ordered image inputs; no fetch/render timestamps or data URIs."""
    frame = {
        key: value
        for key, value in context.items()
        if key not in {'star_on', 'star_off', 'core_icon', 'neutral_frame', 'unowned_rows'}
    }
    for list_key in ('cards', 'unowned_cards'):
        if list_key in frame:
            frame[list_key] = [
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        'icon_source',
                        'portrait_source',
                        'combat',
                        'level',
                        'lv',
                        'role_icons',
                        'weapon_icon',
                        'burst_icon',
                        'element_icon',
                        'element_frame',
                        '_sort_combat',
                    }
                }
                for row in frame[list_key]
            ]
    return hashlib.sha256(json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
