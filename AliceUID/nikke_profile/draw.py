"""个人名片 HTML 渲染。"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_profile_html(context: dict) -> str:
    scene_height = 1140
    return _env.get_template("profile.html").render(**apply_theme(context, context.get("card_theme"), scene_width=720, scene_height=scene_height))


async def draw_profile(context: dict) -> bytes:
    from ..nikke_render.render import render_html
    from ..nikke_resource.service import get_resources
    from ..nikke_render.cache import get_card_cache, fingerprint, card_key
    resources = get_resources()
    cache = get_card_cache() if context.get('_cache_scope') else None
    slot = fingerprint(['profile', context.get('_cache_scope')])
    dependencies = cache.dependencies(slot) if cache else []
    key = lambda: card_key(context, resources, dependencies=dependencies)
    async def build():
        from ..nikke_resource.cache import track_assets
        with track_assets() as paths:
            prepared = await resources.prepare_profile(context)
        dependencies[:] = sorted(paths)
        dependency = key()
        image = await render_html(render_profile_html(prepared), root_width=720)
        return image, dependency
    if not context.get('_cache_scope'):
        return (await build())[0]
    return await cache.get(slot, key, build, current=context.get('_current'), dependencies=dependencies)
