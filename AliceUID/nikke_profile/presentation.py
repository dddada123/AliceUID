"""Prepared source art for the wide profile; no player/API writes."""
from pathlib import Path
import asyncio

def profile_slot(row):
    """Accept only reported positions 1..5; zero is an empty placeholder."""
    value = row.get('slot')
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    return value if isinstance(value, int) and 1 <= value <= 5 else None


def profile_lead_index(team):
    """Prefer slot 3; unpositioned combat fallback retains the third member."""
    slots = [profile_slot(row) for row in team]
    if 3 in slots:
        return slots.index(3)
    if any(slot is not None for slot in slots):
        return 0
    return 2 if len(team) >= 3 else 0

async def prepare_profile_art(context, resources):
    result = dict(context)
    team = result.get('top_nikke') or []
    if not team:
        return result
    lead = team[profile_lead_index(team)]
    rid = lead.get('resource_id')
    skin = resources._selected_skin(lead) if callable(getattr(resources, '_selected_skin', None)) else 0
    if not rid:
        return result
    full = await resources.images.resolved_source('full',rid,skin)
    exact = not full.missing and not full.fallback
    result['hero_art_kind'] = 'full' if exact else 'portraits'
    result['hero_art_url'] = full.source if exact else lead.get('portrait_url') if not lead.get('portrait_missing',True) else lead.get('icon_url')
    result['hero_art_notice'] = '基础外观' if not exact and (lead.get('portrait_fallback') if not lead.get('portrait_missing',True) else lead.get('skin_fallback')) else ''
    if exact:
        try:
            from PIL import Image
            path=Path(resources.images.root)/'characters/full'/f'c{rid:03d}_{full.skin_index:02d}.png'
            with Image.open(path) as original:
                if original.width*original.height <= 8_000_000:
                    result['hero_full_bounds']=original.convert('RGBA').getchannel('A').getbbox()
        except (OSError,ValueError,TypeError,AttributeError):
            pass
        if lead.get('portrait_url') and not lead.get('portrait_missing') and not lead.get('portrait_fallback'):
            from ..nikke_resource.framing import cached_anchor
            result['hero_anchor']=await asyncio.to_thread(cached_anchor,resources.images.root,full.source,lead['portrait_url'],full.content_hash,lead.get('portrait_hash'))
    return result
