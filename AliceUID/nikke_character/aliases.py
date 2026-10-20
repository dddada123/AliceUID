"""Public character aliases, atomically stored by the Bot owner's commands."""
import json
from pathlib import Path
from threading import RLock
import unicodedata
from .builder import _converter, _name_key, resolve_character


class AliasStore:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=RLock()

    def read(self):
        with self.lock:
            if not self.path.exists(): return {}
            data=json.loads(self.path.read_text('utf-8'))
            if not isinstance(data,dict) or any(not isinstance(k,str) or type(v) is not int for k,v in data.items()):
                raise ValueError('角色别名文件格式异常，请Bot主检查；未覆盖原文件。')
            return data

    def add(self,character,alias,static):
        alias=alias.strip()
        if not 1<=len(alias)<=32 or any(unicodedata.category(c).startswith('C') for c in alias):
            raise ValueError('别名须为1～32个可见字符。')
        code=resolve_character(character,static,aliases=self.read())
        convert=_converter()
        key=_name_key(alias,convert)
        if not key: raise ValueError('别名不能只包含标点或空格。')
        for official in static.characters:
            if _name_key(static.name(official),convert)==key:
                raise ValueError('别名与官方角色名冲突，请换一个别名。')
        with self.lock:
            rows=self.read()
            for name,other in rows.items():
                if _name_key(name,convert)==key and other!=code:
                    raise ValueError('别名已用于其他角色，未修改。')
            rows[alias]=code
            from ..nikke_resource.cache import atomic_write
            atomic_write(self.path,json.dumps(rows,ensure_ascii=False,sort_keys=True).encode('utf-8'))
        return code

    def lookup(self, query, static):
        rows = self.read()
        code = resolve_character(query,static,aliases=rows)
        name = static.name(code)
        # Keep the display spelling, removing punctuation and whitespace only.
        compact = ''.join(c for c in name if not unicodedata.category(c).startswith(('P','Z')) and not c.isspace())
        aliases = sorted({alias for alias,target in rows.items() if target == code},key=str.casefold)
        automatic = [compact] if compact and compact != name and compact not in aliases else []
        return dict(name_code=code,name=name,aliases=aliases,automatic_aliases=automatic)


def get_alias_store():
    from ..nikke_config.config import MAIN_PATH
    return AliasStore(MAIN_PATH/'character_aliases.json')


def current_aliases():
    try: return get_alias_store().read()
    except ImportError: return {}
