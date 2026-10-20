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
    context = await get_resources().prepare_profile(context)
    html = render_profile_html(context)
    return await render_html(html, root_width=720)
