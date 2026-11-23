"""Public character aliases, built-in markdown defaults, and local blacklist."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from threading import RLock
import unicodedata

from .builder import _converter, _name_key, resolve_character

DEFAULT_ALIAS_MD = Path(__file__).resolve().parent / 'AliceUID_nk_alias.md'
_ALIAS_SPLIT_RE = re.compile(r'[、,，/|]+')
_BUILTIN_CACHE: dict[tuple[str, int, int], dict[str, int]] = {}
_BUILTIN_LOCK = RLock()


def _resolve_code_from_name(name: str, static) -> int | None:
    if static is None or not name:
        return None
    try:
        convert = _converter()
        key = _name_key(name, convert)
        for code in static.characters:
            if _name_key(static.name(code), convert) == key:
                return int(code)
    except Exception:
        return None
    return None


def parse_alias_markdown(text: str, static=None) -> dict[str, int]:
    """Parse Markdown table rows (`| code | official_name | alias1、alias2 |`) into {alias: name_code}."""
    parsed: dict[str, int] = {}
    for raw_line in str(text or '').splitlines():
        line = raw_line.strip()
        if not line.startswith('|') or line.count('|') < 3:
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) < 3:
            continue
        code_cell, name_cell, alias_cell = cells[0], cells[1], cells[2]
        if not code_cell and not name_cell:
            continue
        if code_cell in ('角色编号', 'name_code', '编号') or set(code_cell) <= {'-', ':'}:
            continue
        code: int | None = None
        if code_cell.isascii() and code_cell.isdecimal():
            code = int(code_cell)
        elif name_cell:
            code = _resolve_code_from_name(name_cell, static)
        if code is None or code <= 0:
            continue
        for token in _ALIAS_SPLIT_RE.split(alias_cell):
            alias = token.strip()
            if not alias or len(alias) > 32 or any(unicodedata.category(c).startswith('C') for c in alias):
                continue
            parsed.setdefault(alias, code)
    return parsed


class AliasStore:
    def __init__(self, path, *, builtin_path=None, disabled_path=None):
        self.path = Path(path)
        self.builtin_path = Path(builtin_path) if builtin_path is not None else DEFAULT_ALIAS_MD
        self.disabled_path = Path(disabled_path) if disabled_path is not None else self.path.with_name('character_aliases_disabled.json')
        self.lock = RLock()

    def read_local(self) -> dict[str, int]:
        with self.lock:
            if not self.path.exists():
                return {}
            data = json.loads(self.path.read_text('utf-8'))
            if not isinstance(data, dict) or any(not isinstance(k, str) or type(v) is not int for k, v in data.items()):
                raise ValueError('角色别名文件格式异常，请Bot主检查；未覆盖原文件。')
            return data

    def read_disabled(self) -> list[str]:
        with self.lock:
            if not self.disabled_path.exists():
                return []
            data = json.loads(self.disabled_path.read_text('utf-8'))
            if not isinstance(data, list) or any(not isinstance(item, str) for item in data):
                raise ValueError('角色别名黑名单格式异常，请Bot主检查；未覆盖原文件。')
            return data

    def read_builtin(self, static=None) -> dict[str, int]:
        if not self.builtin_path.is_file():
            return {}
        try:
            stat = self.builtin_path.stat()
            cache_key = (str(self.builtin_path.resolve()), stat.st_mtime_ns, stat.st_size)
            with _BUILTIN_LOCK:
                if static is None and cache_key in _BUILTIN_CACHE:
                    return dict(_BUILTIN_CACHE[cache_key])
            data = parse_alias_markdown(self.builtin_path.read_text('utf-8-sig'), static=static)
            with _BUILTIN_LOCK:
                _BUILTIN_CACHE[cache_key] = dict(data)
            return data
        except OSError:
            return {}

    def read(self, static=None) -> dict[str, int]:
        with self.lock:
            local = self.read_local()
            builtin = self.read_builtin(static=static)
            disabled = self.read_disabled()
            if not builtin and not disabled:
                return local
            convert = _converter()
            disabled_keys = {_name_key(item, convert) for item in disabled if item.strip()}
            merged: dict[str, int] = {}
            local_keys = {_name_key(k, convert) for k in local}
            for alias, code in builtin.items():
                key = _name_key(alias, convert)
                if key in disabled_keys or key in local_keys:
                    continue
                merged[alias] = code
            for alias, code in local.items():
                key = _name_key(alias, convert)
                if key in disabled_keys:
                    continue
                merged[alias] = code
            return merged

    def _write_local(self, rows: dict[str, int]) -> None:
        from ..nikke_resource.cache import atomic_write
        atomic_write(self.path, json.dumps(rows, ensure_ascii=False, sort_keys=True).encode('utf-8'))

    def _write_disabled(self, rows: list[str]) -> None:
        from ..nikke_resource.cache import atomic_write
        atomic_write(self.disabled_path, json.dumps(sorted(set(rows)), ensure_ascii=False).encode('utf-8'))

    def add(self, character, alias, static):
        alias = alias.strip()
        if not 1 <= len(alias) <= 32 or any(unicodedata.category(c).startswith('C') for c in alias):
            raise ValueError('别名须为1～32个可见字符。')
        convert = _converter()
        key = _name_key(alias, convert)
        if not key:
            raise ValueError('别名不能只包含标点或空格。')
        for official in static.characters:
            if _name_key(static.name(official), convert) == key:
                raise ValueError('别名与官方角色名冲突，请换一个别名。')
        with self.lock:
            merged = self.read(static=static)
            code = resolve_character(character, static, aliases=merged)
            for name, other in merged.items():
                if other not in static.characters:
                    continue
                if _name_key(name, convert) == key and other != code:
                    raise ValueError('别名已用于其他角色，未修改。')
            local = self.read_local()
            local[alias] = code
            self._write_local(local)
            disabled = self.read_disabled()
            filtered = [item for item in disabled if _name_key(item, convert) != key]
            if len(filtered) != len(disabled):
                self._write_disabled(filtered)
        return code

    def remove(self, alias: str, static=None) -> tuple[str, int | None]:
        alias = str(alias or '').strip()
        if not 1 <= len(alias) <= 32 or any(unicodedata.category(c).startswith('C') for c in alias):
            raise ValueError('请提供要注销的可见别名（1～32个字符）。')
        convert = _converter()
        key = _name_key(alias, convert)
        if not key:
            raise ValueError('别名不能只包含标点或空格。')
        with self.lock:
            active = self.read(static=static)
            matched_entries = [(name, code) for name, code in active.items() if _name_key(name, convert) == key]
            if not matched_entries:
                raise ValueError(f'未找到生效中的别名「{alias}」或已注销。')
            local = self.read_local()
            new_local = {name: code for name, code in local.items() if _name_key(name, convert) != key}
            if len(new_local) != len(local):
                self._write_local(new_local)
            builtin = self.read_builtin(static=static)
            in_builtin = any(_name_key(name, convert) == key for name in builtin)
            disabled = self.read_disabled()
            if in_builtin or any(_name_key(item, convert) == key for item in disabled):
                if not any(_name_key(item, convert) == key for item in disabled):
                    disabled.append(matched_entries[0][0])
                    self._write_disabled(disabled)
            return matched_entries[0][0], matched_entries[0][1]

    def aliases_for(self, code: int, static=None) -> list[str]:
        rows = self.read(static=static)
        return sorted({alias for alias, target in rows.items() if target == code}, key=str.casefold)

    def lookup(self, query, static):
        rows = self.read(static=static)
        code = resolve_character(query, static, aliases=rows)
        name = static.name(code)
        # Keep the display spelling, removing punctuation and whitespace only.
        compact = ''.join(c for c in name if not unicodedata.category(c).startswith(('P', 'Z')) and not c.isspace())
        aliases = sorted({alias for alias, target in rows.items() if target == code}, key=str.casefold)
        automatic = [compact] if compact and compact != name and compact not in aliases else []
        return dict(name_code=code, name=name, aliases=aliases, automatic_aliases=automatic)

    def export_markdown(self, static) -> bytes:
        rows = self.read(static=static)
        grouped: dict[int, list[str]] = defaultdict(list)
        for alias, code in rows.items():
            grouped[int(code)].append(alias)
        lines = [
            '# AliceUID 默认角色别名表',
            '',
            '> 将本文件放置于 `AliceUID/AliceUID/nikke_character/AliceUID_nk_alias.md`，插件启动时自动读取并合并；用户本地自定义别名与注销黑名单优先。',
            '',
            '| 角色编号 | 官方名称 | 别名列表 |',
            '| --- | --- | --- |',
        ]
        for code in sorted(grouped):
            official = static.name(code) if static is not None and code in static.characters else f'角色{code}'
            aliases = sorted(set(grouped[code]), key=lambda s: (len(s), s.casefold()))
            safe_official = str(official).replace('|', '｜')
            safe_aliases = '、'.join(a.replace('|', '｜') for a in aliases)
            lines.append(f'| {code} | {safe_official} | {safe_aliases} |')
        lines.append('')
        return '\n'.join(lines).encode('utf-8')


def preload_builtin_aliases() -> int:
    """Validate and warm the built-in AliceUID_nk_alias.md cache on plugin startup."""
    try:
        return len(get_alias_store().read_builtin())
    except Exception as exc:
        try:
            from gsuid_core.logger import logger
            logger.warning(f'[AliceUID] 内置别名表读取异常 error_type={type(exc).__name__}')
        except ImportError:
            pass
        return 0


def get_alias_store():
    from ..nikke_config.config import MAIN_PATH
    return AliasStore(MAIN_PATH / 'character_aliases.json')


def current_aliases():
    try:
        return get_alias_store().read()
    except (ImportError, ValueError, OSError):
        return {}


def aliases_for_code(code: int | None) -> list[str]:
    if type(code) is not int or code <= 0:
        return []
    try:
        return get_alias_store().aliases_for(code)
    except (ImportError, ValueError, OSError):
        return []
