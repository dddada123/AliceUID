"""On-demand anonymous equipment metadata. Public rows never imply ownership."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

import httpx

from ..nikke_api.resource import obfuscate_path
from .cache import atomic_write, public_stream, read_metadata

MAX_JSON_BYTES = 1024 * 1024
TOKEN = re.compile(r'[A-Za-z0-9_-]{1,128}')
WEAPONS = {'AR': '突击步枪', 'MG': '机枪', 'SG': '霰弹枪', 'RL': '火箭发射器',
           'SMG': '冲锋枪', 'SR': '狙击步枪'}


def identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value)
    return int(text) if text.isascii() and text.isdecimal() and len(text) <= 10 and int(text) < 2**31 else None


def validate_row(row, kind, tid):
    if not isinstance(row, dict) or identifier(row.get('id')) != tid:
        raise ValueError('equipment ID mismatch')
    rarity = row.get('favorite_rare' if kind == 'collections' else 'item_rare')
    icon = row.get('icon_resource_id' if kind == 'collections' else 'resource_id')
    if rarity not in {'R', 'SR', 'SSR'} or not isinstance(row.get('name_localkey'), str) or not 0 < len(row['name_localkey']) <= 256:
        raise ValueError('invalid equipment description')
    if isinstance(icon, bool) or not isinstance(icon, (str, int)) or not TOKEN.fullmatch(str(icon)):
        raise ValueError('invalid icon resource')
    if kind == 'collections':
        if identifier(row.get('name_code')) is None or row.get('weapon_type') not in WEAPONS:
            raise ValueError('invalid favorite applicability')
        if type(row.get('max_level')) is not int or not 0 <= row['max_level'] <= 100:
            raise ValueError('invalid favorite max level')
    for field in ('atk', 'def', 'hp', 'powers', 'grade', 'level1', 'level2', 'level3'):
        if field in row and (not isinstance(row[field], list) or len(row[field]) > 101
                             or any(type(v) not in (int, float) or not 0 <= v <= 10**18 for v in row[field])):
            raise ValueError('invalid level array')
    return row


class CollectionMetadata:
    """Valid local objects are immutable cache hits; failures have persisted cooldown."""
    def __init__(self, root: Path, *, http=None, clock=time.time):
        self.root, self.http, self.clock = Path(root), http, clock
        self._locks = {}
        self._slot = asyncio.Lock()

    async def get(self, kind, tid):
        tid = identifier(tid)
        if kind not in {'collections', 'cubes'} or tid is None or tid <= 0:
            return None
        path = self.root / 'static' / kind / f'{tid}.json'
        async with self._locks.setdefault(str(path), asyncio.Lock()):
            try:
                if path.stat().st_size > MAX_JSON_BYTES:
                    raise ValueError('cached object exceeds byte limit')
                return validate_row(json.loads(path.read_text(encoding='utf-8-sig')), kind, tid)
            except (OSError, ValueError, TypeError):
                pass
            stamp = path.with_suffix('.meta.json')
            stop = self.root / 'static' / 'collection-public.meta.json'
            async with self._slot:
                now = self.clock()
                if now < max(read_metadata(stamp).get('retry_after', 0), read_metadata(stop).get('retry_after', 0)):
                    return None
                logical = f'/equip/zh-tw/{"favorite" if kind == "collections" else "cube"}_{tid}.json'
                try:
                    if self.http is not None:
                        row = await self._download(self.http, logical, kind, tid)
                    else:
                        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as http:
                            row = await self._download(http, logical, kind, tid)
                    atomic_write(path, json.dumps(row, ensure_ascii=False, allow_nan=False).encode())
                    return row
                except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
                    retry = {'retry_after': now + 1800}
                    try:
                        atomic_write(stamp, json.dumps(retry).encode())
                        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {403, 429}:
                            atomic_write(stop, json.dumps(retry).encode())
                    except OSError:
                        pass
                    return None

    @staticmethod
    async def _download(http, logical, kind, tid):
        async with public_stream(http, obfuscate_path(logical), {'Accept': 'application/json'}) as response:
            response.raise_for_status()
            if not response.headers.get('content-type', '').lower().startswith('application/json'):
                raise ValueError('non-JSON equipment response')
            chunks = bytearray()
            async for part in response.aiter_bytes():
                chunks.extend(part)
                if len(chunks) > MAX_JSON_BYTES:
                    raise ValueError('equipment JSON exceeds byte limit')
        return validate_row(json.loads(chunks.decode('utf-8-sig')), kind, tid)
