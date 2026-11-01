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

    def latest_roster(self, key, snapshot=None):
        """Compare ownership timestamps without refreshing unrelated profile fields."""
        from ..nikke_resource.cache import read_metadata
        snapshot = self.read(key) if snapshot is None else snapshot
        light = read_metadata(self.path(key, 'profile.json'))
        light_profile = light.get('profile')
        light_rows = light_profile.get('chars') if isinstance(light_profile, dict) else None
        candidates = [(snapshot.get('roster_checked_at', snapshot.get('profile_checked_at', snapshot.get('saved_at', 0))),
                       snapshot.get('roster')),
                      (light.get('roster_checked_at', light.get('checked_at', 0)), light_rows)]
        import math
        for stamp, rows in sorted(((stamp, rows) for stamp, rows in candidates
                                   if type(stamp) in (int, float) and math.isfinite(stamp)), reverse=True, key=lambda row:row[0]):
            if isinstance(rows, list):
                from .builder import integer
                combined = {str(row.get('name_code')):row for row in rows if isinstance(row, dict)}
                if len(combined) != len(rows):
                    return stamp, rows
                checks = snapshot.get('row_checked_at', {})
                if isinstance(checks, dict):
                    for row in snapshot.get('roster', []):
                        if not isinstance(row, dict) or integer(row.get('name_code')) in (None, 0):
                            continue
                        key = str(row['name_code'])
                        checked = checks.get(key)
                        if type(checked) in (int, float) and math.isfinite(checked) and checked > stamp:
                            combined[key] = row
                return stamp, list(combined.values())
        return 0, []

    def write(self,key,data):
        from ..nikke_resource.cache import atomic_write
        body=dict(data,schema=1,saved_at=time.time())
        from ..nikke_time import time_metadata
        profile = body.get('profile') or {}
        basic = profile.get('basic') or {} if isinstance(profile, dict) else {}
        area = body.get('_area_id', basic.get('area_id') if isinstance(basic, dict) else None)
        body['time_metadata'] = {
            field: time_metadata(body[field], area)
            for field in ('saved_at', 'profile_checked_at', 'roster_checked_at') if field in body
        }
        body['time_metadata']['details'] = {
            str(code): time_metadata(entry.get('checked_at'), area)
            for code, entry in body.get('details', {}).items() if isinstance(entry, dict)
        }
        encoded=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        if len(encoded)>16*1024*1024:
            raise ValueError('panel snapshot exceeds size budget')
        atomic_write(self.path(key,'snapshot.json'),encoded)

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

    def save_image(self,key,code,digest,image,*,dependencies=None):
        from ..nikke_resource.cache import atomic_write,validate_image
        validate_image(image)
        atomic_write(self.path(key,f'render-{code}.png'),image)
        atomic_write(self.path(key,f'render-{code}.json'),json.dumps(dict(
            fingerprint=digest,sha256=hashlib.sha256(image).hexdigest(),dependencies=dependencies)).encode())


def get_panel_cache():
    from ..nikke_config.config import MAIN_PATH
    return PanelCache(MAIN_PATH/'cache'/'panels')
