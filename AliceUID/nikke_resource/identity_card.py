"""Optional portrait decoration from the bound account's existing snapshot only."""
from .commander import avatar_mapping
from .display import display_assets, DisplayAssets


def cached_identity(bind, data=None):
    if data is None:
        from ..nikke_user.panel_refresh import cached_profile
        try:
            data = cached_profile(bind) or {}
        except (AttributeError,ImportError,RuntimeError,ValueError,OSError):
            data = {}
    outpost, saved = data.get('outpost') or {}, data.get('saved') or {}
    def positive(value):
        if isinstance(value, bool) or not isinstance(value,(int,str)):
            return None
        try:
            value = int(value)
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None
    level = positive(outpost.get('synchro_level'))
    if level is None:
        level = max((positive(row.get('lv')) or 0 for row in data.get('chars', []) if isinstance(row, dict)), default=0) or None
    return dict(commander_icon_id=saved.get('icon'), synchro_level=level,
                synchro_text=str(level) if level is not None else '—')


def portrait_mapping(resources, context):
    load = getattr(resources, '_load_rows', None)
    return avatar_mapping(context.get('commander_icon_id'), load('character_avatar_map.json')) if callable(load) else None


async def prepare_portrait(images, mapping):
    result = dict(commander_avatar_url='', commander_avatar_hash='')
    if mapping is None or not isinstance(images, DisplayAssets):
        return result
    kind, rid, skin = 'icons', *mapping
    from ..nikke_api.resource import character_resource_url
    raw, _ = images.local(images.images._path(kind, rid, skin), character_resource_url(kind, rid, skin))
    if raw:
        image = await images.resolved_source(kind, rid, skin)
        if not image.missing and not image.fallback:
            result.update(commander_avatar_url=image.source, commander_avatar_hash=image.content_hash)
    else:
        images.refresh.add(('get', kind, rid, skin))
    return result


async def decorate_identity(context, bind):
    from .service import get_resources
    context.update(cached_identity(bind))
    try:
        resources = get_resources()
    except (AttributeError,ImportError,RuntimeError,KeyError,OSError):
        return
    async with display_assets(resources.images, budget=0) as images:
        context.update(await prepare_portrait(images, portrait_mapping(resources, context)))
