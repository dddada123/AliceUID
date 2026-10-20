"""Renderer-independent frosted backplanes; foreground is never filtered.

All distances are CSS pixels. Only newly allocated Pillow images are modified.
"""
from __future__ import annotations
import base64
import io
from functools import lru_cache
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

BLUR = 16
RADIUS = 20
SATURATION = 1.25


def image_uri(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def abstract_scene(width: int, height: int, theme: str = 'dark') -> Image.Image:
    """Original aurora, fine diagonals and grain; no source character assets."""
    import numpy as np
    y, x = np.mgrid[:height, :width]
    u, v = x / max(width, 1), y / max(width, 1)
    dark = theme == 'dark'
    base = np.array([13, 24, 42] if dark else [217, 230, 244], dtype=float)
    blue = np.exp(-((u-.18)**2 / .16 + (v-.30)**2 / .26))
    violet = np.exp(-((u-.94)**2 / .20 + (v-.82)**2 / .40))
    ribbon = np.exp(-((u+.38*v-.78)**2) / .003)
    grain = ((x*17+y*29) % 19 - 9) * .32
    lines = (((x+y*2) % 56) < 2) * (12 if dark else -9)
    rgb = base + blue[...,None]*np.array([12,49,66] if dark else [-35,6,11]) + violet[...,None]*np.array([48,19,63] if dark else [16,-22,2]) + ribbon[...,None]*np.array([17,28,39] if dark else [-15,-6,8]) + (grain+lines)[...,None]
    return Image.fromarray(np.clip(rgb,0,255).astype('uint8'), 'RGB').convert('RGBA')


def frost_panel(background: Image.Image, box: tuple[int,int,int,int], *, theme='dark', blur=BLUR, radius=RADIUS, decorate=True) -> Image.Image:
    """Crop an expanded ROI, blur, saturate, tint and edge-light it, nonmutating.

    box is (x,y,width,height). Expansion avoids Gaussian edge seams. Returned
    RGBA layer contains only background pixels; HTML draws sharp text on top.
    """
    x,y,w,h = box
    pad = int(blur*3)
    expanded = background.convert('RGBA').crop((x-pad,y-pad,x+w+pad,y+h+pad))
    filtered = expanded.filter(ImageFilter.GaussianBlur(blur))
    filtered = ImageEnhance.Color(filtered).enhance(SATURATION)
    filtered = ImageEnhance.Brightness(filtered).enhance(1.08 if theme=='dark' else 1.02)
    panel = filtered.crop((pad,pad,pad+w,pad+h))
    tint = (12,23,39,192) if theme=='dark' else (249,253,255,193)
    panel = Image.alpha_composite(panel, Image.new('RGBA',(w,h),tint))
    if not decorate:
        return panel
    mask = Image.new('L',(w,h)); draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=255)
    panel.putalpha(mask)
    edge = ImageDraw.Draw(panel)
    edge.rounded_rectangle((0,0,w-1,h-1),radius=radius,outline=(211,235,255,65) if theme=='dark' else (255,255,255,220),width=1)
    edge.line((radius,1,w-radius,1),fill=(231,245,255,75) if theme=='dark' else (255,255,255,245),width=1)
    return panel


def compose_frost(background: Image.Image, boxes, *, theme='dark', blur=BLUR) -> Image.Image:
    """Place soft shadows and frosted ROIs on a copy of the original scene."""
    result = background.convert('RGBA').copy()
    for box in boxes:
        x,y,w,h = box
        shadow=Image.new('RGBA',result.size)
        ImageDraw.Draw(shadow).rounded_rectangle((x,y+8,x+w,y+h+8),radius=RADIUS,fill=(0,7,20,85 if theme=='dark' else 35))
        result=Image.alpha_composite(result,shadow.filter(ImageFilter.GaussianBlur(12)))
        result.alpha_composite(frost_panel(background,box,theme=theme,blur=blur),(x,y))
    return result


@lru_cache(maxsize=12)
def scene_uri(width=1000, height=1400, theme='dark', inset=24) -> str:
    return image_uri(abstract_scene(width,height,theme))


@lru_cache(maxsize=4)
def panel_uri(theme='dark') -> str:
    """Reusable 512px ROI for flow-layout panels without a browser measure pass."""
    # Flow panels resize only the filtered interior. Their 1px border and rim
    # are drawn at final CSS dimensions, avoiding stretched double corners.
    return image_uri(frost_panel(abstract_scene(640,640,theme),(64,64,512,512),theme=theme).crop((24,24,488,488)))


@lru_cache(maxsize=4)
def character_panel_uri(art_uri: str, theme='dark') -> str:
    """Poster ROI matches its static CSS art rectangle, without measuring DOM.

    The same prepared data URI feeds the visible HTML img and this local crop.
    No cached image file is opened for writing. Invalid prepared sources fail.
    """
    from PIL import ImageOps
    if not art_uri.startswith('data:image/') or ';base64,' not in art_uri:
        raise ValueError('Prepared current-skin art must be an embedded image')
    try:
        raw=base64.b64decode(art_uri.split(';base64,',1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as source:
            art=source.convert('RGBA')
    except Exception as error:
        raise ValueError('Cannot decode prepared current-skin art for frost') from error
    scene=abstract_scene(1000,1600,theme)
    # Page inset24 + outer border1 + poster inset32; hero art top152.
    # Cover crop starts at image top, leaving face/upper body before data y825.
    art=ImageOps.fit(art,(886,1100),method=Image.Resampling.LANCZOS,centering=(.5,0))
    scene.alpha_composite(art,(57,177))
    return image_uri(frost_panel(scene,(41,825,918,640),theme=theme,decorate=False))

