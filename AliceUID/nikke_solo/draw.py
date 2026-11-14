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
from .selection import label, BY_CODE
from .site import season_notice
from dataclasses import replace

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

def attribute_codes(meta):
    """Website season and actual reference are independent of the query/native default."""
    query = meta.get('code')
    query = query if isinstance(query, str) and query in BY_CODE else None
    reference = meta.get('reference_code', query)
    reference = reference if isinstance(reference, str) and reference in BY_CODE else None
    current = None
    raid = meta.get('current_raid')
    listing = meta.get('_listing')
    rows = listing.get('seasons') if isinstance(listing, dict) else None
    if type(raid) is int and isinstance(rows, list):
        matching = [row for row in rows if isinstance(row, dict) and type(row.get('raid')) is int and row['raid'] == raid]
        if len(matching) == 1 and isinstance(matching[0].get('weakness_code'), str) and matching[0]['weakness_code'] in BY_CODE:
            current = matching[0]['weakness_code']
    return {'query': query, 'current': current, 'reference': reference}


async def prepare_attribute_presentation(image, images):
    from ..nikke_resource.cache import image_data_uri
    names = {'fire':'fire','water':'water','wind':'wind','electric':'elect','iron':'iron'}
    codes = attribute_codes(image.site)
    sources = {}
    for code in sorted({code for code in codes.values() if code}):
        try:
            data = await images.get_base_icon('attributes', 'icn_element_' + names[BY_CODE[code]])
            sources[code] = image_data_uri(data, (128, 128)) if data else ''
        except Exception:
            sources[code] = ''
    presentation = dict(image.presentation)
    for kind, key in [('query','element_icon'), ('current','current_element_icon'), ('reference','reference_element_icon')]:
        # Clear stale decorations rather than copying a different season's symbol.
        presentation[key] = sources.get(codes[kind], '')
    return presentation


def solo_html(image, bind, region, theme=None):
    with Image.open(io.BytesIO(image.png)) as im:
        height = round(im.height * 960 / im.width)
    source_time = image.site.get('fetched_at','')
    if source_time:
        try:
            source_stamp = datetime.fromisoformat(source_time.replace('Z','+00:00'))
            if source_stamp.tzinfo is None:
                raise ValueError('unspecified timezone')
            source_time = source_stamp.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S') + '（北京时间）'
        except (ValueError, TypeError):
            source_time = '网站未提供可确认的时间'
    from ..nikke_resource.cache import PLACEHOLDER
    presentation = image.presentation if isinstance(image.presentation, dict) else {}
    codes = attribute_codes(image.site)
    recommendation = image.site.get('recommended')
    if recommendation:
        simulation_settings = '已套用推荐设置 · ' + str(recommendation.get('label') or recommendation.get('code') or '')
    elif image.site.get('recommendation_status'):
        simulation_settings = '网站默认配置（未读取到匹配配置或导入入口）'
    else:
        simulation_settings = '网站现有模拟配置'
    ctx = apply_theme(dict(commander_name=bind.nickname or '昵称未知',commander_uid=bind.uid or '未知',
        commander_region=region.label,weakness=image.weakness,rank_season=image.rank_season,
        query_mode='自动跟随赛季' if image.site.get('mode', 'default') == 'default' else '手动指定',
        avatar_url=presentation.get('avatar_url') or PLACEHOLDER,
        avatar_hint=presentation.get('avatar_hint') or '头像暂不可用',
        element_icon=presentation.get('element_icon') or '',
        current_element_icon=presentation.get('current_element_icon') or '',
        reference_element_icon=presentation.get('reference_element_icon') or '',
        current_element_label=label(codes['current']) if codes['current'] else '属性未确认',
        reference_element_label=label(codes['reference']) if codes['reference'] else '属性未确认',
        season_notice=season_notice(image.site), simulation_settings=simulation_settings,
        default_weakness=label(image.site.get('default_code')),boss=image.site.get('boss',''),
        site_current_raid=image.site.get('current_raid'),source_time=source_time,
        captured_at=datetime.fromtimestamp(image.captured_at, ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
        notes=image.notes,image_height=height,
        image_uri='data:image/png;base64,'+base64.b64encode(rounded_png(image.png)).decode()),
        get_card_theme(theme if theme in ('light','dark','random') else get_solo_theme_mode()),scene_width=1072,scene_height=height+500)
    return ENV.get_template('solo.html').render(**ctx)

async def draw_solo(image, bind, region, theme=None):
    from ..nikke_render.render import render_html
    from ..nikke_resource.service import get_resources
    presentation = await prepare_attribute_presentation(image, get_resources().images)
    image = replace(image, presentation=presentation)
    return await render_html(solo_html(image,bind,region,theme),root_width=1072)
