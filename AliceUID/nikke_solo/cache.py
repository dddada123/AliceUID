"""Five-day owned screenshots and rendered cards. No Cookie or share link on disk."""
from __future__ import annotations
import hashlib
import io
import json
import math
import re
import time
from PIL import Image
from ..nikke_character.cache import PanelCache
from ..nikke_resource.cache import atomic_write
from .service import SoloImage, SoloUnavailable, validate_png

TTL = 5 * 86400
SCHEMA = 'solo-crop3-v1'

def identity(bind, actor=None):
    actor = actor or (str(bind.user_id),str(bind.bot_id))
    values = [*map(str,actor),str(bind.game_id),str(bind.intl_open_id),int(bind.area_id),
              hashlib.sha256(bind.cookie_enc.encode()).hexdigest()]
    return hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()

def source_hash(image):return hashlib.sha256(image.png).hexdigest()

def style_key(image,bind,theme):
    from ..nikke_render.fonts import resolve_font
    from ..nikke_render.glass_settings import get_glass_strength
    from ..nikke_render.language import get_card_language
    try:
        from ..nikke_config.config import AliceUIDConfig
        dpi = AliceUIDConfig.get_config('AliceUID_RenderDpi').data
    except (ImportError,AttributeError,KeyError,RuntimeError):dpi=144
    values=[SCHEMA,source_hash(image),image.captured_at,theme,get_glass_strength(),resolve_font().fingerprint,
            get_card_language(),dpi,str(bind.nickname or ''),str(bind.uid or '')]
    from ..nikke_render.cache import style_version
    values.append(style_version(dpi=dpi, theme=theme))
    return hashlib.sha256(json.dumps(values,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def validate_card(data):
    if not isinstance(data,bytes) or not 0<len(data)<=32*1024*1024:raise ValueError('card bytes')
    with Image.open(io.BytesIO(data)) as im:
        if im.format!='PNG' or not 400<=im.width<=4800 or not 300<=im.height<=16000 or im.width*im.height>32_000_000:
            raise ValueError('card dimensions')
        im.verify()

class SoloCache(PanelCache):
    def __init__(self,root,*,clock=time.time):
        super().__init__(root);self.clock=clock;self._swept=0

    def metadata(self,key):
        try:
            p=self.path(key,'snapshot.json')
            if p.stat().st_size>32768:return None
            m=json.loads(p.read_text('utf-8'))
            if not isinstance(m,dict) or type(m.get('captured_at')) not in (int,float):return None
            age=self.clock()-m['captured_at']
            if m.get('schema')!=SCHEMA or not math.isfinite(age) or not 0<=age<TTL:return None
            if not isinstance(m.get('source_sha'),str) or not re.fullmatch('[0-9a-f]{64}',m['source_sha']):return None
            if not isinstance(m.get('weakness'),str) or not isinstance(m.get('rank_season'),str):return None
            if not isinstance(m.get('notes'),list) or not all(isinstance(n,str) for n in m['notes']):return None
            if not isinstance(m.get('renders'),dict) or len(m['renders'])>8:return None
            if not all(isinstance(k,str) and isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',k) and re.fullmatch('[0-9a-f]{64}',v) for k,v in m['renders'].items()):return None
            return m
        except (OSError,ValueError,KeyError,TypeError,SoloUnavailable):return None

    def read(self,key):
        m=self.metadata(key)
        if not m:return None
        try:
            p=self.path(key,'source-'+m['source_sha']+'.png')
            if p.stat().st_size>16*1024*1024:return None
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=m['source_sha']:return None
            validate_png(raw)
            if not isinstance(m['notes'],list) or not all(isinstance(n,str) for n in m['notes']):return None
            return SoloImage(raw,str(m['weakness']),m['captured_at'],str(m['rank_season']),tuple(m['notes']))
        except (OSError,ValueError,KeyError,TypeError,SoloUnavailable):return None

    def card(self,key,image,style):
        m=self.metadata(key)
        if not m or m['captured_at']!=image.captured_at or m['source_sha']!=source_hash(image):return None
        try:
            p=self.path(key,'render-'+style+'.png')
            if p.stat().st_size>32*1024*1024:return None
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=m['renders'][style]:return None
            validate_card(raw)
            return raw
        except (OSError,ValueError,KeyError,TypeError,SoloUnavailable):return None

    def save(self,key,image,style,card):
        validate_png(image.png);validate_card(card)
        sha=source_hash(image)
        previous=self.metadata(key)
        renders = dict(previous['renders']) if previous and previous['source_sha']==sha and previous['captured_at']==image.captured_at else {}
        atomic_write(self.path(key,'source-'+sha+'.png'),image.png)
        atomic_write(self.path(key,'render-'+style+'.png'),card)
        renders.pop(style,None);renders[style]=hashlib.sha256(card).hexdigest()
        renders=dict(list(renders.items())[-8:])
        metadata=dict(schema=SCHEMA,source_sha=sha,captured_at=image.captured_at,weakness=image.weakness,
                      rank_season=image.rank_season,notes=list(image.notes),renders=renders)
        # Publish only after both PNGs exist. Refresh errors leave the old pointer intact.
        atomic_write(self.path(key,'snapshot.json'),json.dumps(metadata,ensure_ascii=False,allow_nan=False).encode())
        keep={'source-'+sha+'.png',*('render-'+k+'.png' for k in renders)}
        for p in self.path(key,'snapshot.json').parent.glob('*.png'):
            if p.name not in keep:
                try:self.path(key,p.name).unlink(missing_ok=True)
                except OSError:pass  # A committed result remains usable if obsolete-file cleanup fails.

    def cleanup(self):
        now=self.clock()
        if now-self._swept<3600 or not self.root.exists():return
        self._swept=now
        for directory in self.root.iterdir():
            if not re.fullmatch('[0-9a-f]{64}',directory.name):continue
            try:
                manifest=self.path(directory.name,'snapshot.json')
                if not directory.is_dir():continue
                # An interrupted first write/corrupt manifest is bounded by its filesystem age.
                stamp=directory.stat().st_mtime
                if manifest.exists():
                    stamp=manifest.stat().st_mtime
                    if manifest.stat().st_size<=32768:
                        try:
                            m=json.loads(manifest.read_text('utf-8'))
                            value=m.get('captured_at') if isinstance(m,dict) else None
                            if type(value) in (int,float) and math.isfinite(value):stamp=value
                        except (ValueError,TypeError):pass
                if now-stamp>=TTL:self.purge(directory.name)
            except (OSError,ValueError,TypeError):continue

_default = None

def get_cache():
    global _default
    from ..nikke_config.config import MAIN_PATH
    root=MAIN_PATH/'cache'/'solo'
    if _default is None or _default.root!=root.absolute():_default=SoloCache(root)
    return _default

def invalidate_binding(bind):
    get_cache().purge(identity(bind))
