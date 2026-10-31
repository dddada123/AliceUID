"""Independent light/dark/random preference; shared glass and four-corner alpha mask."""
import base64
import io
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme, get_card_theme
from .service import validate_png

ENV = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent/'templates')),
                  autoescape=select_autoescape(['html']))

THEME_KEY = 'AliceUID_SoloCardTheme'

def get_solo_theme_mode():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(THEME_KEY).data
    except (ImportError,AttributeError,KeyError,RuntimeError,TypeError):
        return 'dark'
    return value if value in ('light','dark','random') else 'dark'

def rounded_png(data, radius=22):
    validate_png(data)
    with Image.open(io.BytesIO(data)) as im:
        out = im.convert('RGBA')
    # Match the CSS radius at the 960px content width, smooth the alpha edge.
    r = max(1, round(radius * out.width / 960))
    mask = Image.new('L', (out.width*3, out.height*3), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,out.width*3-1,out.height*3-1), radius=r*3, fill=255)
    out.putalpha(mask.resize(out.size, Image.Resampling.LANCZOS))
    stream = io.BytesIO()
    out.save(stream, format='PNG')
    return stream.getvalue()

def solo_html(image, bind, region, theme=None):
    with Image.open(io.BytesIO(image.png)) as im:
        height = round(im.height * 960 / im.width)
    ctx = apply_theme(dict(commander_name=bind.nickname or '昵称未知',commander_uid=bind.uid or '未知',
        commander_region=region.label,weakness=image.weakness,rank_season=image.rank_season,
        captured_at=datetime.fromtimestamp(image.captured_at, ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
        notes=image.notes,image_height=height,
        image_uri='data:image/png;base64,'+base64.b64encode(rounded_png(image.png)).decode()),
        get_card_theme(theme if theme in ('light','dark','random') else get_solo_theme_mode()),scene_width=1072,scene_height=height+500)
    return ENV.get_template('solo.html').render(**ctx)

async def draw_solo(image, bind, region, theme=None):
    from ..nikke_render.render import render_html
    return await render_html(solo_html(image,bind,region,theme),root_width=1072)
