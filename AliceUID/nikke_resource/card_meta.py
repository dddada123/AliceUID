"""Shared, reported-only progression and role art for profile and collection cards."""
from __future__ import annotations
import base64
import hashlib
from ..nikke_api.parser import static_weapon_type


def integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def progression(rarity, grade, core):
    grade, core = integer(grade), integer(core)
    maximum = {'SSR': 3, 'SR': 2, 'R': 0}.get(rarity)
    valid = (maximum is not None and grade is not None and core is not None
             and 0 <= grade <= maximum and 0 <= core <= (7 if rarity == 'SSR' else 0))
    if not valid:
        return dict(star_states=[],core_display='',progression_known=False,
                    progression_notice='突破资料未知' if grade is None or core is None else '突破资料异常')
    total = grade + core
    extra = max(0, total - maximum)
    return dict(star_states=[i < total for i in range(maximum)],
                core_display='MAX' if extra == 7 else f'{extra:02}' if extra else '',
                progression_known=True,progression_notice='')


def card_metadata(raw, row):
    rarity = row.get('original_rare')
    rarity = rarity if isinstance(rarity, str) else ''
    # Keep only metadata which affects visible role icons, never a full static row.
    element_id = row.get('element_id')
    element = element_id.get('element') if isinstance(element_id, dict) else None
    details = row.get('element_details')
    if not isinstance(element, dict):
        element = details[0] if isinstance(details, list) and details and isinstance(details[0], dict) else {}
    element = {k: element[k] for k in ('element','element_icon') if isinstance(element.get(k),str)}
    spec = {k: row[k] for k in ('class','use_burst_skill') if isinstance(row.get(k),str)}
    spec.update(element_id={'element':element},weapon_type=static_weapon_type(row))
    return dict(rarity=rarity,role_spec=spec,**progression(rarity,raw.get('grade'),raw.get('core')))


def frame(color):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="34" viewBox="0 0 30 34">'
           '<path d="M15 1 L28.5 8.5 L28.5 25.5 L15 33 L1.5 25.5 L1.5 8.5Z" '
           f'fill="#233041" fill-opacity="0.94" stroke="{color}" stroke-width="2"/></svg>')
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


NEUTRAL_FRAME = frame('#d8dfe5')
ELEMENT_COLORS = {'Fire':'#ed6754','Iron':'#ffb13b','Electronic':'#df48ea',
                  'Electric':'#df48ea','Water':'#62bcff','Wind':'#64d99b'}


async def prepare_card_icons(card, images):
    from ..nikke_character.collection import role_icons
    spec = card.get('role_spec') or {}
    icons = await role_icons(spec, images) if callable(getattr(images, 'get_asset', None)) else []
    by_kind = {item['kind']:item for item in icons}
    result = {'role_icons':[item for item in icons if item['kind'] in {'element','class','burst'}],
              'role_hashes':{item['kind']: hashlib.sha256(item['icon_url'].encode()).hexdigest()
                             if item['icon_url'] else None for item in icons}}
    for kind in ('weapon','burst','element'):
        item = by_kind.get(kind,{})
        result[kind + '_icon'] = item.get('icon_url') or ''
        result[kind + '_label'] = item.get('label') or ''
    element = spec.get('element_id',{}).get('element',{}).get('element')
    result['element_frame'] = frame(ELEMENT_COLORS.get(element,'#bdcce0'))
    return result


async def prepare_badges(images):
    from .badges import badge_sources
    sources, hashes = await badge_sources(images)
    return dict(star_on=sources.get('star_active',''),star_off=sources.get('star_inactive',''),
                core_icon=sources.get('core',''),badge_hashes=hashes,neutral_frame=NEUTRAL_FRAME)
