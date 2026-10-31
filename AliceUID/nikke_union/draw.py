"""Union HTML card; SI icons follow the costume reported in each attack record."""
from __future__ import annotations

import asyncio
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme

_env = Environment(loader=FileSystemLoader(str(Path(__file__).parent.parent / 'templates')),
                   autoescape=select_autoescape(['html', 'xml']))


def render_union_html(context):
    detail_attacks=sum(len(member.get('attacks',[])) for member in context.get('details',[]))
    scene_height=max(1600,2000+72*len(context.get('rows',[]))+64*((len(context.get('missing',[]))+1)//2)
                     +80*len(context.get('tails',[]))+440*detail_attacks)
    scene_height=min(23000,scene_height)
    return _env.get_template('union.html').render(**apply_theme(context, context.get("card_theme"),scene_height=scene_height))


async def draw_union(context):
    from ..nikke_render.cache import get_card_cache, fingerprint, card_key
    from ..nikke_resource.service import get_resources
    resources = get_resources()
    cache = get_card_cache() if context.get('_cache_scope') else None
    slot = fingerprint(['union', context.get('_cache_scope'), context.get('view'), context.get('day')])
    dependencies = cache.dependencies(slot) if context.get('_cache_scope') else []
    key = lambda: card_key(context, resources, dependencies=dependencies)
    async def build():
        return await _draw_union(context, resources, key, dependencies)
    if not context.get('_cache_scope'):
        return (await build())[0]
    # The slot deliberately excludes season: new months replace old battle pictures.
    return await cache.get(slot, key, build, current=context.get('_current'), dependencies=dependencies)


async def _draw_union(context, resources, key, dependencies):
    from ..nikke_render.render import render_html
    from ..nikke_resource.service import get_resources
    import copy
    context = copy.deepcopy(context)
    static = resources.load_static()
    from ..nikke_resource.skins import resolve_skin
    async def prepare(character):
        if character.get('resource_id') is not None:
            selection = resolve_skin(character, static)
            requested = selection.skin_index if selection.reported and selection.mapped else 0
            resolved = await resources.images.resolved_source('icons', character['resource_id'], requested)
            character.update(icon_url=resolved.source, icon_skin_index=resolved.skin_index,
                             icon_fallback=resolved.fallback, icon_missing=resolved.missing,
                             skin_notice='出刀记录外观 · ' + selection.notice)
            if resolved.fallback:
                character['skin_notice'] += '；记录皮肤头像缺失，使用基础头像'
    from ..nikke_resource.cache import track_assets
    with track_assets() as paths:
        await asyncio.gather(*(prepare(character) for member in context.get('details', [])
                               for attack in member['attacks'] for character in attack['characters']))
    dependencies[:] = sorted(paths)
    dependency = key()
    return await render_html(render_union_html(context), root_width=1000), dependency
