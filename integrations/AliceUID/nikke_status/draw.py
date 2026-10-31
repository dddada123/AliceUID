"""Local assets and shared glass; reuse a snapshot's image before random theme."""
import asyncio
import base64
from collections import OrderedDict
import copy
import hashlib
import json
from pathlib import Path

from jinja2 import Environment,FileSystemLoader,select_autoescape
from ..nikke_render.theme import apply_theme,get_card_theme_mode,get_card_theme

PACKAGE=Path(__file__).resolve().parent.parent
ENV=Environment(loader=FileSystemLoader(str(PACKAGE/'templates')),autoescape=select_autoescape(['html']))
_images=OrderedDict()
_inflight={}
_epochs={}
MAX_BYTES=24*1024*1024


def _resource_store():
    try:
        from ..nikke_config.config import MAIN_PATH
    except (ImportError,AttributeError,RuntimeError):
        return None
    from ..nikke_character.cache import PanelCache
    return PanelCache(MAIN_PATH/'cache'/'resource_images')


def invalidate_status_images(owner_key):
    owner=hashlib.sha256(json.dumps(owner_key,sort_keys=True,default=str).encode()).hexdigest()
    _epochs[owner]=_epochs.get(owner,0)+1
    _images.clear()
    store=_resource_store()
    if store is not None:store.purge(owner)


def status_style_key():
    """Presentation changes invalidate the resource ready-image window too."""
    from ..nikke_render.language import get_card_language
    from ..nikke_render.fonts import resolve_font
    from ..nikke_render.glass_settings import get_glass_strength
    from ..nikke_render.cache import style_version
    return style_version()


def status_html(context,theme=None):
    context=copy.deepcopy(context)
    if context['kind']=='resources':
        for item in context['items']:
            path=PACKAGE.parent/'assets/status'/item['icon_name']
            item['icon_url']='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')
    height=max(900,520+155*len(context.get('bosses',[])))
    context=apply_theme(context,theme or context.get('card_theme'),scene_width=1000,scene_height=height)
    return ENV.get_template('status.html').render(**context)


async def draw_status(context,*,owner_key):
    from ..nikke_render.render import render_html
    from ..nikke_render.language import get_card_language
    from ..nikke_render.fonts import resolve_font
    from ..nikke_render.glass_settings import capture_glass
    context=capture_glass(context)
    mode=get_card_theme_mode()
    font=resolve_font()
    stable=dict(context,render_version='alice-v100-status-footer-2',theme_mode=mode,
                language=get_card_language(),font=font.fingerprint,owner=owner_key)
    stable['presentation'] = status_style_key()
    key=hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    store=_resource_store() if context.get('kind')=='resources' else None
    owner=hashlib.sha256(json.dumps(owner_key,sort_keys=True,default=str).encode()).hexdigest()
    epoch=_epochs.get(owner,0)
    if key in _images:
        _images.move_to_end(key)
        return _images[key]
    if store is not None:
        cached=store.image(owner,'resources',key)
        if cached is not None:return cached
    async def render():
        png=await render_html(status_html(context,get_card_theme(mode)),root_width=1000)
        if _epochs.get(owner,0)!=epoch:
            raise ValueError('绑定已更新，旧状态图已失效。')
        if store is not None:store.save_image(owner,'resources',key,png)
        _images[key]=png
        while sum(map(len,_images.values()))>MAX_BYTES and _images:
            _images.popitem(last=False)
        return png
    task=_inflight.get(key)
    if task is None:
        task=asyncio.create_task(render())
        _inflight[key]=task
        def done(finished):
            if _inflight.get(key) is finished:_inflight.pop(key,None)
            # Retrieve errors even if every awaiting command was cancelled.
            if not finished.cancelled():finished.exception()
        task.add_done_callback(done)
    return await asyncio.shield(task)
