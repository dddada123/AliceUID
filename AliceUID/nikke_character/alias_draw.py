"""Public character alias card; no game account or private API is needed."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme

_env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent/'templates')),
                   autoescape=select_autoescape(['html']))


def render_alias_html(context):
    height = max(800,450 + (len(context['aliases'])+len(context['automatic_aliases']))*44)
    return _env.get_template('aliases.html').render(**apply_theme(
        context,context.get('card_theme'),scene_width=760,scene_height=height))


async def draw_alias(context):
    from ..nikke_render.render import render_html
    return await render_html(render_alias_html(context),root_width=760)
