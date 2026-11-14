"""Decorate raid portraits from reported progression, then member-scoped cache.

No extra account requests. Missing cached progression omits the badge rather
than inventing stars or painting an unknown marker.
"""
from ..nikke_resource.card_meta import integer, card_metadata


def decorate(character, static, cached=None):
    cached = cached or {}
    row = static.character(character.get('name_code')) if character.get('name_code') else {}
    rarity = row.get('original_rare')
    maximum = {'SSR': 3, 'SR': 2, 'R': 0}.get(rarity)
    values, sources = {}, []
    for key, limit in (('grade', maximum), ('core', 7 if rarity == 'SSR' else 0)):
        reported = integer(character.get(key))
        local = integer(cached.get(key))
        if limit is not None and reported is not None and 0 <= reported <= limit:
            values[key] = reported
            sources.append('record')
        elif limit is not None and local is not None and 0 <= local <= limit:
            values[key] = local
            sources.append('cache')
    character.update(card_metadata(values, row))
    character['progression_source'] = 'cache' if 'cache' in sources else 'record'
    if character['progression_known'] and 'cache' in sources:
        character['progression_notice'] = '星级与核心参考本地缓存，可能与出刀时不同'
    return character


def cached_rows(context, bind, candidates, store):
    """Match game, area, bot and openid before reading a binding's cache."""
    targets = {str(m.get('openid')) for m in context.get('details', [])}
    result, stamps = {}, {}
    for candidate in candidates:
        if (str(candidate.game_id) != str(bind.game_id)
                or int(candidate.area_id) != int(bind.area_id)
                or str(candidate.bot_id) != str(bind.bot_id)
                or str(candidate.intl_open_id) not in targets):
            continue
        from ..nikke_character.cache import panel_identity
        scope = panel_identity(candidate)
        stamp, rows = store.latest_roster(scope)
        member = str(candidate.intl_open_id)
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = integer(row.get('name_code'))
            key = (member, code)
            if code and stamp >= stamps.get(key, -1):
                result.setdefault(member, {})[str(code)] = {
                    key: row[key] for key in ('grade', 'core') if key in row}
                stamps[key] = stamp
    return result


async def attach_cached_progression(context, bind):
    if context.get('view') != 'detail' or not context.get('details'):
        return
    from ..nikke_character.cache import get_panel_cache
    from ..nikke_user.models import AliceBind
    # Read only matching members from local bindings; never borrow the sender's
    # roster for another member or trigger an online member-profile request.
    others = await AliceBind.get_all_binds() if any(not m.get('own') for m in context['details']) else []
    context['progression_cache'] = cached_rows(context, bind, [bind, *others], get_panel_cache())
