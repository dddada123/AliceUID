"""Independent shadow layers and light-theme monochrome icon inversion."""
import base64
import io
from functools import lru_cache
from PIL import Image, ImageFilter, ImageChops, ImageOps

LIGHT_INVERT_KEYS = frozenset({'skills', 'role_icons', 'recycling_levels'})


@lru_cache(maxsize=128)
def invert_icon_light(source, floor=26):
    """Invert white monochrome icon RGB to ~90% dark gray while preserving alpha."""
    if not isinstance(source, str) or not source.startswith('data:image/png;base64,'):
        return source
    try:
        data = base64.b64decode(source.split(',', 1)[1], validate=True)
        with Image.open(io.BytesIO(data)) as original:
            if original.width * original.height > 4_000_000:
                return source
            icon = original.convert('RGBA')
        r, g, b, a = icon.split()
        inv_rgb = ImageOps.invert(Image.merge('RGB', (r, g, b)))
        soft_rgb = inv_rgb.point(lambda p: round(floor + p * (255 - floor) / 255))
        result = soft_rgb.convert('RGBA')
        result.putalpha(a)
        out = io.BytesIO()
        result.save(out, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
    except (ValueError, OSError):
        return source


@lru_cache(maxsize=128)
def icon_effect(source, theme='light', maxed=False, *, light_glow=False):
    if not isinstance(source, str) or not source.startswith('data:image/png;base64,'):
        return None
    try:
        data = base64.b64decode(source.split(',', 1)[1], validate=True)
        with Image.open(io.BytesIO(data)) as original:
            if original.width * original.height > 4_000_000:
                return None
            icon = original.convert('RGBA')
        w, h = icon.size
        # Extra transparent space keeps the Gaussian tail away from image bounds.
        px, py = round(w / 4), round(h / 4)
        size = (w + 2 * px, h + 2 * py)
        mask = Image.new('L', size)
        if light_glow and theme == 'light':
            mask.paste(icon.getchannel('A'), (px, py))
            color = (255, 255, 255)
            radius = min(w, h) * 0.015
            alpha = mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda a: min(255, round(a * 0.92)))
        else:
            shift = 0 if maxed or theme == 'dark' else max(1, round(h * .035))
            mask.paste(icon.getchannel('A'), (px, py + shift))
            color = (246, 193, 92) if (maxed and theme == 'dark') else (200, 12, 96) if maxed else (16, 57, 123) if theme == 'dark' else (0, 0, 0)
            radius = min(w, h) * (.045 if maxed else .025)
            alpha = mask.filter(ImageFilter.GaussianBlur(radius))
            alpha = alpha.point(lambda a: round(a * (.90 if maxed else .65 if theme == 'dark' else .70)))
            if maxed:
                inner = mask.filter(ImageFilter.GaussianBlur(min(w, h) * .018))
                alpha = ImageChops.lighter(alpha, inner.point(lambda a: round(a * .80)))
        result = Image.new('RGBA', size, color + (0,))
        result.putalpha(alpha)
        out = io.BytesIO()
        result.save(out, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
    except (ValueError, OSError):
        return None


def prepare_light_icon(source, theme='light', *, maxed=False):
    """Return (foreground_uri, shadow_uri) with 90% gray inversion + tight white glow on light theme."""
    if not source:
        return source, None
    if theme == 'light':
        return invert_icon_light(source), icon_effect(source, theme, maxed, light_glow=True)
    return source, icon_effect(source, theme, maxed)


def apply_icon_effects(context):
    result = dict(context)
    theme = result['card_theme']
    for key in ('gear', 'skills', 'role_icons', 'recycling_levels'):
        rows = []
        invert_light = key in LIGHT_INVERT_KEYS
        for original in result.get(key) or []:
            row = dict(original)
            maxed = key == 'gear' and type(row.get('tier')) is int and row['tier'] == 10 and type(row.get('lv')) is int and row['lv'] == 5
            if invert_light and row.get('icon_url'):
                fg, sh = prepare_light_icon(row.get('icon_url'), theme, maxed=maxed)
                row['icon_url'] = fg
                row['icon_shadow_url'] = sh
            else:
                row['icon_shadow_url'] = icon_effect(row.get('icon_url'), theme, maxed)
            rows.append(row)
        result[key] = rows
    for key in ('collection_display', 'cube_display'):
        row = dict(result[key])
        row['icon_shadow_url'] = icon_effect(row.get('icon_url'), theme)
        result[key] = row
    if result.get('corp_watermark_url'):
        fg, sh = prepare_light_icon(result.get('corp_watermark_url'), theme)
        result['corp_watermark_url'] = fg
        result['corp_watermark_shadow_url'] = sh
    return result


@lru_cache(maxsize=16)
def portrait_shadow(source, placement, *, glow=False):
    """Local black shadow or white glow; preserve original art and placement."""
    import re, math
    values={key:float(value) for key,value in re.findall(r'(width|height|left|top):(-?[0-9.]+)px', placement)}
    if set(values)!={'width','height','left','top'} or not isinstance(source,str) or not source.startswith('data:image/png;base64,'):
        return None, ''
    try:
        data=base64.b64decode(source.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(data)) as original:
            if original.width*original.height>8_000_000:
                return None, ''
            alpha=original.convert('RGBA').getchannel('A')
        w,h=alpha.size
        sx,sy=values['width']/w,values['height']/h
        if min(sx,sy)<=0:
            return None, ''
        # Three CSS pixels of blur and a small down/right offset, independent of art size.
        radius=3/min(sx,sy)
        px,py=math.ceil(15/sx),math.ceil(15/sy)
        mask=Image.new('L',(w+2*px,h+2*py))
        mask.paste(alpha,(px if glow else px+round(2/sx),py if glow else py+round(3/sy)))
        mask=mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda a:round(a*(.60 if glow else .65)))
        shadow=Image.new('RGBA',mask.size,(255,255,255,0) if glow else (0,0,0,0));shadow.putalpha(mask)
        out=io.BytesIO();shadow.save(out,'PNG')
        style=f"width:{values['width']+2*px*sx:.2f}px;height:{values['height']+2*py*sy:.2f}px;left:{values['left']-px*sx:.2f}px;top:{values['top']-py*sy:.2f}px"
        return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode('ascii'),style
    except (ValueError,OSError):
        return None, ''
