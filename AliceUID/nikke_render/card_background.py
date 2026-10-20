"""Reviewed local card wallpapers and compact-card geometry, with no HTTP."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import random
from PIL import Image,ImageFilter
from .glass_settings import blur_radius
from .glass import compose_frost, image_uri

BACKGROUND_ROOT = Path(__file__).resolve().parents[2] / 'card_bg'


def background_candidates(theme='dark'):
    from .background_sources import get_background_provider
    prefix = '暗色背景' if theme == 'dark' else '亮色背景'
    return tuple(sorted(path for path in get_background_provider().candidates(theme) if path.is_file() and path.name.startswith(prefix)))


def choose_background(theme='dark'):
    choices=background_candidates(theme)
    if not choices:
        raise ValueError('对应主题card_bg背景缺失，请检查安装素材')
    return random.choice(choices)


@dataclass(frozen=True)
class CompactGeometry:
    width: int
    height: int
    aggregate_height: int
    main_height: int
    boxes: tuple
    portrait_height: int
    tools_top: int
    gear_top: int
    gear_height: int


COMPACT_WIDTH=660


def compact_geometry(aggregate_count=0):
    # Exact 1:2 portrait; five equal data panels. Content is centered inside
    # each panel instead of stretching only the blank area below its rows.
    aggregate_height=gear_height=144
    portrait_height=640
    main_height=760  # 640 portrait + 16 gap + 104 tools; 5*144 + 4*10.
    top=138
    tools_top=top+portrait_height+16
    boxes=[(16,16,628,110),(16,top,320,portrait_height),(16,tools_top,320,104),
           (348,top,296,aggregate_height)]
    gear_top=top+10+aggregate_height
    boxes.extend((348,gear_top+i*(gear_height+10),296,gear_height) for i in range(4))
    return CompactGeometry(COMPACT_WIDTH,top+main_height+50,aggregate_height,main_height,tuple(boxes),portrait_height,tools_top,gear_top,gear_height)


@lru_cache(maxsize=18)
def _backdrop(path_string,mtime_ns,size,width,height,boxes,theme,strength):
    path=Path(path_string)
    with Image.open(path) as original:
        source=original.convert('RGBA')
    # Fill horizontally with uniform scaling, crop vertically; never stretch axes.
    scale=max(width/source.width,height/source.height)
    source=source.resize((round(source.width*scale),round(source.height*scale)),Image.Resampling.LANCZOS)
    x=max(0,(source.width-width)//2)
    y=max(0,round((source.height-height)*.46))
    scene=source.crop((x,y,x+width,y+height))
    scene=scene.filter(ImageFilter.GaussianBlur(blur_radius(strength)))
    # Only a light veil; the actual photo remains visible between glass modules.
    veil=(4,10,22,22) if theme=='dark' else (250,253,255,18)
    scene=Image.alpha_composite(scene,Image.new('RGBA',scene.size,veil))
    return image_uri(compose_frost(scene,boxes,theme=theme,blur=0))


def compact_backdrop(theme,geometry,strength=10):
    chosen=choose_background(theme)
    stat=chosen.stat()
    return {'compact_background_uri':_backdrop(str(chosen.resolve()),stat.st_mtime_ns,stat.st_size,
              geometry.width,geometry.height,geometry.boxes,theme,strength),
            'compact_background_name':chosen.name,'compact_geometry':geometry}
