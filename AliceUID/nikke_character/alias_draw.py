"""Public character alias card; no game account or private API is needed."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme

_env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent/'templates')),
                   autoescape=select_autoescape(['html']))


def render_alias_html(context):
    from datetime import datetime, timedelta, timezone
    from ..nikke_render.fonts import apply_font_html
    from ..nikke_render.theme import v2_theme_tokens
    height = max(800,450 + (len(context['aliases'])+len(context['automatic_aliases']))*44)
    themed = apply_theme(context, context.get('card_theme'), scene_width=640, scene_height=height)
    themed.update(v2_theme_tokens(None, themed['card_theme']))
    themed['font_family'] = 'MiSans'
    themed['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')
    return apply_font_html(_env.get_template('aliases.html').render(**themed), embed=False)


async def draw_alias(context):
    from ..nikke_render.render import render_html
    from ..nikke_resource.service import get_resources
    from ..nikke_render.cache import get_card_cache, fingerprint, card_key
    resources = get_resources()
    cache = get_card_cache()
    slot = fingerprint(['aliases', context['name_code']])
    dependencies = cache.dependencies(slot)
    key = lambda: card_key(context, resources, dependencies=dependencies)
    async def build():
        prepared = dict(context)
        from ..nikke_resource.cache import track_assets
        with track_assets() as paths:
            if context.get('resource_id'):
                icon = await resources.images.resolved_source('icons', context['resource_id'], 0)
                prepared['icon_url'] = icon.source
        dependencies[:] = sorted(paths)
        dependency = key()
        return await render_html(render_alias_html(prepared),root_width=640), dependency
    return await cache.get(slot, key, build, ttl=30*86400, dependencies=dependencies)
