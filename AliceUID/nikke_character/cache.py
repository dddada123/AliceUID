"""Binding/owner-scoped pure-data panels and derived PNGs; no credentials."""
import hashlib
import json
from pathlib import Path
import time


def panel_identity(bind):
    # The encrypted credential is used only to derive a one-way revision.
    revision=hashlib.sha256(bind.cookie_enc.encode()).hexdigest()
    scope=[str(getattr(bind,'user_id','')),str(getattr(bind,'bot_id','')),
           str(bind.game_id),str(bind.intl_open_id),int(bind.area_id),revision]
    return hashlib.sha256(json.dumps(scope,separators=(',',':')).encode()).hexdigest()


class PanelCache:
    def __init__(self,root): self.root=Path(root).absolute()

    def path(self,key,name):
        import re
        if not re.fullmatch('[0-9a-f]{64}',key) or not re.fullmatch(r'[a-z0-9_-]+\.(json|png)',name):
            raise ValueError('invalid panel cache key')
        path=self.root/key/name
        if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in [path,*path.parents]):
            raise ValueError('panel cache symlink refused')
        return path

    def read(self,key):
        path=self.path(key,'snapshot.json')
        try:
            if path.stat().st_size>16*1024*1024: return {}
            data=json.loads(path.read_text('utf-8'))
            if not isinstance(data,dict) or data.get('schema')!=1: return {}
            if not isinstance(data.get('roster'),list) or not isinstance(data.get('details'),dict): return {}
            return data
        except (OSError,ValueError): return {}

    def write(self,key,data):
        from ..nikke_resource.cache import atomic_write
        body=dict(data,schema=1,saved_at=time.time())
        atomic_write(self.path(key,'snapshot.json'),json.dumps(body,ensure_ascii=False,allow_nan=False).encode())

    def invalidate(self,key):
        self.path(key,'snapshot.json').unlink(missing_ok=True)

    def purge(self,key):
        """Erase a revoked binding's validated cache files without recursive deletion."""
        directory=self.path(key,'snapshot.json').parent
        if not directory.exists():
            return
        for item in directory.iterdir():
            checked=self.path(key,item.name)
            if not checked.is_file():
                raise ValueError('unexpected panel cache entry')
            checked.unlink()
        directory.rmdir()

    def image(self,key,code,digest):
        path=self.path(key,f'render-{code}.png')
        try:
            meta=json.loads(self.path(key,f'render-{code}.json').read_text('utf-8'))
            if meta.get('fingerprint')!=digest or path.stat().st_size>16*1024*1024: return None
            image=path.read_bytes()
            if hashlib.sha256(image).hexdigest()!=meta.get('sha256'): return None
            from ..nikke_resource.cache import validate_image
            validate_image(image)
            return image
        except (OSError,ValueError,TypeError): return None

    def save_image(self,key,code,digest,image):
        from ..nikke_resource.cache import atomic_write,validate_image
        validate_image(image)
        atomic_write(self.path(key,f'render-{code}.png'),image)
        atomic_write(self.path(key,f'render-{code}.json'),json.dumps(dict(
            fingerprint=digest,sha256=hashlib.sha256(image).hexdigest())).encode())


def get_panel_cache():
    from ..nikke_config.config import MAIN_PATH
    return PanelCache(MAIN_PATH/'cache'/'panels')
