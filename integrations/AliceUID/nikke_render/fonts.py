"""Local card font registry. No network, no system font installation."""
from __future__ import annotations
import base64
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import io
from pathlib import Path
import re
from threading import RLock
from PIL import ImageFont

FONT_ROOT=Path(__file__).resolve().parents[2]/'formts'
FONT_KEY='AliceUID_CardFont'
FALLBACK='黑体（兜底）'
SHIPPED_DEFAULT='AaZongYiYuan-2.ttf'
MAX_FONT_BYTES=32*1024*1024
EXTENSIONS={'.ttf','.otf','.ttc'}
FALLBACK_STACK="'SimHei','Microsoft YaHei','MiSans','Noto Sans CJK SC',sans-serif"
_lock=RLock()
_registered=set()
_registration_renderer=None


@dataclass(frozen=True)
class FontSelection:
    filename: str
    family: str
    fingerprint: str
    data: bytes=field(default=b'',repr=False)
    reason: str=''

    @property
    def custom(self):return bool(self.data)


@lru_cache(maxsize=8)
def _read_font(path_string,mtime_ns,size):
    path=Path(path_string)
    data=path.read_bytes()
    if not 0<len(data)<=MAX_FONT_BYTES:raise ValueError('font size unsupported')
    # FreeType validates the actual font, not merely a renamed extension.
    ImageFont.truetype(io.BytesIO(data),20)
    sha=hashlib.sha256(data).hexdigest()
    return FontSelection(path.name,'AliceUIDFont_'+sha[:16],sha,data)


def scan_fonts():
    found={}
    try:
        paths=sorted(FONT_ROOT.iterdir(),key=lambda item:item.name.casefold())
    except OSError:
        return found
    for path in paths:
        try:
            if path.suffix.lower() not in EXTENSIONS or not path.is_file() or path.is_symlink():continue
            if not path.resolve().is_relative_to(FONT_ROOT.resolve()):continue
            stat=path.stat()
            if not 0<stat.st_size<=MAX_FONT_BYTES:continue
            found[path.name]=_read_font(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
        except (OSError,ValueError,RuntimeError):
            continue
    return found


def font_options():return [*scan_fonts(),FALLBACK]


def factory_default():
    fonts=scan_fonts()
    if SHIPPED_DEFAULT in fonts:return SHIPPED_DEFAULT
    return next(iter(fonts)) if len(fonts)==1 else FALLBACK


def resolve_font(value=None):
    if value is None:
        try:
            from ..nikke_config.config import AliceUIDConfig
            value=AliceUIDConfig.get_config(FONT_KEY).data
        except (ImportError,AttributeError,KeyError,RuntimeError):
            value=factory_default()
        if not isinstance(value,str):value=factory_default()
    if not isinstance(value,str):
        return FontSelection(FALLBACK,'MiSans','fallback-heiti-v1',reason='invalid_font_setting')
    if value==FALLBACK:return FontSelection(FALLBACK,'MiSans','fallback-heiti-v1')
    fonts=scan_fonts()
    return fonts.get(value) or FontSelection(FALLBACK,'MiSans','fallback-heiti-v1',reason='selected_font_unreadable')


def font_stack(selection):
    return (f"'{selection.family}'," if selection.custom else '')+FALLBACK_STACK


def font_css(selection,*,embed=True):
    face=''
    if selection.custom and embed:
        encoded=base64.b64encode(selection.data).decode('ascii')
        face=f"@font-face{{font-family:'{selection.family}';src:url(data:font/ttf;base64,{encoded});font-display:block;}}"
    importance='!important' if embed else ''
    return face+f"html,body,body *{{font-family:{font_stack(selection)}{importance};}}"


def apply_font_html(html,selection=None,*,embed=True):
    from .language import localize_html
    html=localize_html(html)
    selected=selection or resolve_font()
    # Replace our own previous injection (e.g. preview HTML reused for native).
    html=re.sub(r'<style id="nikke-font-style">.*?</style>','',html,flags=re.S)
    if not embed:
        # Rewrite ONLY stylesheet contents, never player names/body text.
        # The pinned native engine ignores !important; a broad selector alone
        # also cannot outrank .page's existing font declaration.
        def native_style(match):
            css=match.group(2)
            css=re.sub(r'font-family\s*:[^;}]+',lambda _: 'font-family:'+font_stack(selected),css,flags=re.I)
            css=re.sub(r'(\bfont\s*:\s*[^;{}]*?\d+(?:\.\d+)?(?:px|pt|em|rem|%)(?:/[^\s;]+)?\s+)[^;{}]+',lambda m:m.group(1)+font_stack(selected),css,flags=re.I)
            return match.group(1)+css+'</style>'
        html=re.sub(r'(<style\b[^>]*>)(.*?)</style>',native_style,html,flags=re.S|re.I)
    style='<style id="nikke-font-style">'+font_css(selected,embed=embed)+'</style>'
    return html.replace('</head>',style+'</head>',1) if '</head>' in html else style+html


def register_native_font(renderer,selection):
    global _registration_renderer
    if not selection.custom:return False
    key=selection.fingerprint
    try:
        with _lock:
            if _registration_renderer is not renderer:
                _registration_renderer=renderer
                _registered.clear()
            if key not in _registered:
                renderer.register_font(selection.data,name=selection.family)
                _registered.add(key)
        return True
    except Exception:
        return False


def refresh_font_options(config):
    options=font_options()
    for mapping in (getattr(config,'config',{}),getattr(config,'config_list',{})):
        item=mapping.get(FONT_KEY)
        if item is not None:item.options=list(options)


class FontAwareDefaults(dict):
    """Core's authenticated config GET iterates config_default directly.

    Refresh options on that exact read path; adding a font needs no Core restart.
    No write and no policy-data mutation happen during a list refresh.
    """
    def __init__(self,values,config):
        super().__init__(values);self.owner=config
    def __iter__(self):
        refresh_font_options(self.owner)
        return super().__iter__()
    def items(self):
        refresh_font_options(self.owner)
        return super().items()
    def keys(self):
        refresh_font_options(self.owner)
        return super().keys()
    def values(self):
        refresh_font_options(self.owner)
        return super().values()


def install_font_options(config):
    config.config_default=FontAwareDefaults(config.config_default,config)
    refresh_font_options(config)
