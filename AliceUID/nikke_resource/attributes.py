"""Small public numerical dependencies, cached separately from private panels."""
from __future__ import annotations
import asyncio
import json
import time
import httpx
from .cache import atomic_write, public_stream, read_metadata
from .collections import CollectionMetadata, identifier, validate_row
from ..nikke_api.resource import obfuscate_path
from ..nikke_api.parser import static_weapon_type
from ..nikke_character.attributes import calculate, fingerprint

ROLE_KEYS = ('name_code', 'resource_id', 'original_rare', 'class', 'corporation', 'shot_id',
             'stat_enhance_detail', 'character_level_hp_list', 'character_level_attack_list',
             'character_level_defence_list')
WARM_TIMEOUT = 45
PUBLIC_ATTRIBUTE_SCHEMA = 2


def original_attributes(owned, bundle):
    """Current public gameplay attributes; full source stays in the public cache."""
    role = bundle.get('role') if isinstance(bundle.get('role'), dict) else {}
    result = {key: role[key] for key in (
        'critical_ratio', 'critical_damage', 'bonusrange_min', 'bonusrange_max',
        'burst_apply_delay', 'burst_duration', 'change_burst_step', 'element_details',
        'shot_detail', 'stat_enhance_detail', 'skill1_detail', 'skill2_detail', 'ulti_skill_detail'
    ) if key in role}
    level = identifier(owned.get('lv'))
    result['level_base'] = {key: values[level-1] for key in ('hp', 'attack', 'defence')
                           if level and isinstance(values := role.get('character_level_'+key+'_list'), list)
                           and level <= len(values)}
    for kind in ('cube', 'favorite'):
        if isinstance(bundle.get(kind), dict):
            result[kind] = bundle[kind]
    return result

class AttributeMetadata:
    def __init__(self, resources):
        self.resources = resources
        self.root = resources.root / 'static' / 'attributes'
        self.bundled = resources.bundled / 'attributes'
        self.collections = CollectionMetadata(resources.root, http=resources.http)
        self._locks = {}
        self._slots = asyncio.Semaphore(4)

    def read(self, name):
        fallback = None
        for root in (self.root, self.bundled):
            try:
                path = root / name
                if path.stat().st_size > 4 * 1024 * 1024:
                    continue
                obj = json.loads(path.read_text('utf-8'))
                if isinstance(obj, (dict, list)) and obj:
                    if name.startswith('roles/') and isinstance(obj, dict) and not all(
                            key in obj for key in ('critical_ratio', 'critical_damage', 'shot_detail')):
                        fallback = fallback or obj
                        continue
                    return obj
            except (OSError, ValueError):
                pass
        return fallback

    async def get(self, name, logical):
        async with self._locks.setdefault(name, asyncio.Lock()):
            old = self.read(name)
            # Old role caches deliberately omitted combat/weapon fields. They
            # remain usable for cards but must not suppress enrichment for 24h.
            enriched = not name.startswith('roles/') or (isinstance(old, dict) and
                       all(key in old for key in ('critical_ratio', 'critical_damage', 'shot_detail')))
            path = self.root / name
            meta = read_metadata(path.with_suffix('.meta.json'))
            now = time.time()
            validated_at = meta.get('checked_at') or meta.get('bundled_loaded_at', 0)
            if now < meta.get('retry_after', 0) or (old and enriched and 0 <= now - validated_at < 86400):
                return old
            if old and enriched and not path.exists() and not validated_at:
                # The complete installer already has reviewed growth tables.
                # First refresh must not redownload all 206 before publishing.
                atomic_write(path.with_suffix('.meta.json'), json.dumps({'bundled_loaded_at':now}).encode())
                return old
            try:
                async with self._slots:
                    if self.resources.http is not None:
                        obj = await self._download(self.resources.http, logical)
                    else:
                        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as http:
                            obj = await self._download(http, logical)
                if name.startswith('roles/'):
                    if not isinstance(obj, dict) or not all(k in obj for k in ROLE_KEYS):
                        raise ValueError('incomplete role data')
                    # Preserve the complete public role response, including
                    # future attributes, weapon parameters and skill metadata.
                    rid = int(name.split('/')[1].split('.')[0])
                    if obj.get('resource_id') != rid:
                        raise ValueError('wrong role data')
                else:
                    if isinstance(obj, dict):
                        obj = obj.get('records')
                    if not isinstance(obj, list) or not obj or not all(isinstance(r, dict) for r in obj):
                        raise ValueError('invalid attribute table')
                atomic_write(path, json.dumps(obj, ensure_ascii=False, allow_nan=False).encode())
                atomic_write(path.with_suffix('.meta.json'), json.dumps({'checked_at': now}).encode())
                return obj
            except (httpx.HTTPError, OSError, ValueError, TypeError):
                atomic_write(path.with_suffix('.meta.json'), json.dumps({'retry_after': now + 1800}).encode())
                return old

    @staticmethod
    async def _download(http, logical):
        async with public_stream(http, obfuscate_path(logical), {'Accept': 'application/json'}) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError('attribute data too large')
        return json.loads(body.decode('utf-8-sig'))

    def bundle(self, code, detail, static):
        rid = static.character(code).get('resource_id')
        role = self.read(f'roles/{rid}.json') if type(rid) is int and rid > 0 else None
        result = dict(role=role, weapon_type=static_weapon_type(static.character(code)) or static_weapon_type(role),
                      research=self.read('research.json') or [], bond=self.read('bond.json') or [],
                      equipment=self.resources.load_equipment_items())
        for kind, folder, field in (('cube', 'cubes', 'harmony_cube_tid'), ('favorite', 'collections', 'favorite_item_tid')):
            tid = identifier(detail.get(field))
            if tid is not None and tid > 0:
                try:
                    path = self.resources.root / 'static' / folder / f'{tid}.json'
                    if path.stat().st_size <= 1024 * 1024:
                        result[kind] = validate_row(json.loads(path.read_text('utf-8')), folder, tid)
                except (OSError, ValueError, TypeError):
                    pass
        result['version'] = fingerprint(result)
        return result

    async def _warm(self, snapshot, static):
        await asyncio.gather(self.get('research.json', '/character/RecycleResearchStatTable.json'),
                             self.get('bond.json', '/character/AttractiveLevelTable.json'))
        async def one(code, entry):
            detail = entry.get('detail') or {}
            rid = static.character(int(code)).get('resource_id')
            if type(rid) is int and rid > 0:
                await self.get(f'roles/{rid}.json', f'/roledata/{rid}-v2-zh-tw.json')
            for kind, field in (('cubes', 'harmony_cube_tid'), ('collections', 'favorite_item_tid')):
                tid = identifier(detail.get(field))
                if tid is not None and tid > 0:
                    await self.collections.get(kind, tid)
        await asyncio.gather(*(one(code, entry) for code, entry in snapshot.get('details', {}).items()))

    async def prepare(self, snapshot, static):
        # Public metadata is optional enrichment. CDN slowness must not discard
        # successfully fetched private roster/details or prevent card refresh.
        try:
            async with asyncio.timeout(WARM_TIMEOUT):
                await self._warm(snapshot, static)
        except TimeoutError:
            pass
        return self.compute(snapshot, static)

    def compute(self, snapshot, static, *, level=None):
        owned = {str(r['name_code']): r for r in snapshot.get('roster', [])}
        outpost = (snapshot.get('profile') or {}).get('outpost') or {}
        result = {}
        for code, entry in snapshot.get('details', {}).items():
            if code not in owned:
                continue
            bundle = self.bundle(int(code), entry['detail'], static)
            attr = calculate(owned[code], entry['detail'], outpost, bundle, level=level)
            attr['original'] = original_attributes(owned[code], bundle)
            attr['public_attribute_schema'] = PUBLIC_ATTRIBUTE_SCHEMA
            attr['detail_checked_at'] = entry.get('checked_at')
            attr['outpost_checked_at'] = snapshot.get('outpost_checked_at', snapshot.get('profile_checked_at'))
            result[code] = attr
        return result

def get_metadata(resources):
    value = getattr(resources, '_attribute_metadata', None)
    if value is None:
        value = resources._attribute_metadata = AttributeMetadata(resources)
    return value

async def prepare_snapshot(snapshot):
    from .service import get_resources
    resources = get_resources()
    static = resources.load_static()
    if any(int(code) not in static.characters for code in snapshot.get('details', {})):
        await resources.update_tables(targets=['nikke_list_zh-TW_v2.json'])
        static = resources.load_static()
    await resources.ensure_character_tables()
    snapshot['attributes'] = await get_metadata(resources).prepare(snapshot, static)
    return snapshot

async def prepare_character(client, roster, detail):
    outpost = await client.get_outpost_info()
    code = str(detail['name_code'])
    snapshot = dict(roster=roster, details={code: {'detail': detail, 'checked_at': time.time()}},
                    profile={'outpost': outpost}, outpost_checked_at=time.time())
    await prepare_snapshot(snapshot)
    return snapshot
