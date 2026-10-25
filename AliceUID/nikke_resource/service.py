"""Resource lifecycle and profile preparation; integration imports stay lazy."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

from ..nikke_api.parser import StaticData
from ..nikke_api.resource import obfuscate_path
from .cache import ImageCache, atomic_write, read_metadata, public_stream, PLACEHOLDER

TABLES = {
    'nikke_list_zh-TW_v2.json': ('/character/zh-tw/nikke_list_zh-TW_v2.json', 'name_code'),
    'equip_option_table_v2-zh-tw.json': ('/equip/equip_option_table_v2-zh-tw.json', 'id'),
    'stage_list.json': ('/stage/stage_list.json', 'id'),
    'ItemEquipTable-zh-tw.json': ('/equip/ItemEquipTable-zh-tw.json', 'id'),
    'character_skill_map.json': ('/character/character_skill_map.json', 'resource_id'),
    'character_id_map.json': ('/character/character_id_map.json', 'id'),
    'character_avatar_map.json': ('/character/character_avatar_map.json', 'id'),
}


class ResourceService:
    def __init__(self, root: Path, bundled: Path, *, http=None, clock=time.time):
        self.root = Path(root)
        self.bundled = Path(bundled)
        self.clock = clock
        self.http = http
        self.images = ImageCache(self.root / 'resource', http=http, clock=clock)
        self._static_lock = asyncio.Lock()
        self._update_lock = asyncio.Lock()

    async def update_tables(self, *, force: bool = False, targets=None) -> dict[str, str]:
        async with self._static_lock:
            report = {}
            selected = set(targets) if targets is not None else set(TABLES)
            for filename, (logical, required_key) in TABLES.items():
                if filename not in selected:
                    continue
                path = self.root / 'static' / filename
                stamp = path.with_suffix('.meta.json')
                meta = read_metadata(stamp)
                now = self.clock()
                if now < meta.get('retry_after', 0):
                    report[filename] = 'cooldown'
                    continue
                if not force and path.exists() and meta.get('source') == logical and 0 <= now - meta.get('checked_at', 0) < 86400:
                    report[filename] = 'cached'
                    continue
                try:
                    if self.http is not None:
                        data = await self._table(self.http, logical, required_key)
                    else:
                        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
                            data = await self._table(client, logical, required_key)
                    # Reject truncation / schema drift rather than silently deleting most known rows.
                    baseline = path if path.exists() else self.bundled / filename
                    try:
                        old_rows = json.loads(baseline.read_text(encoding='utf-8-sig'))
                        if isinstance(old_rows, dict):
                            old_rows = old_rows.get('records')
                        old_count = len(old_rows) if isinstance(old_rows, list) else 0
                    except (OSError, ValueError, TypeError):
                        old_count = 0
                    if old_count and len(data) < old_count * .8:
                        raise ValueError('suspiciously small table')
                    encoded = json.dumps(data, ensure_ascii=False).encode()
                    if not path.exists() or path.read_bytes() != encoded:
                        atomic_write(path, encoded)
                    atomic_write(stamp, json.dumps({'checked_at': now, 'count': len(data), 'source': logical}).encode())
                    report[filename] = f'updated:{len(data)}'
                except (httpx.HTTPError, ValueError, OSError):
                    meta['retry_after'] = now + 3600
                    atomic_write(stamp, json.dumps(meta).encode())
                    report[filename] = 'fallback'
            return report

    @staticmethod
    async def _table(client, logical, required_key):
        async with public_stream(client, obfuscate_path(logical), {'Referer': 'https://www.blablalink.com/'}) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for part in response.aiter_bytes():
                chunks.extend(part)
                if len(chunks) > 8 * 1024 * 1024:
                    raise ValueError('table exceeds byte limit')
        rows = json.loads(chunks.decode('utf-8-sig'))
        if logical == '/equip/ItemEquipTable-zh-tw.json' and isinstance(rows, dict):
            rows = rows.get('records')
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) and required_key in row for row in rows):
            raise ValueError('invalid static table')
        if required_key == 'name_code' and not all('resource_id' in row and 'id' in row for row in rows):
            raise ValueError('invalid character mapping')
        for row in rows:
            numeric = (required_key, 'resource_id', 'id') if required_key == 'name_code' else (required_key,)
            for key in numeric:
                value = row[key]
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    raise ValueError('invalid table identifier')
                if not str(value).isascii() or not str(value).isdigit() or not 0 <= int(value) < 2**31:
                    raise ValueError('invalid table identifier')
            local = row.get('name_localkey')
            plain_equipment_name = logical == '/equip/ItemEquipTable-zh-tw.json' and isinstance(local, str)
            if local is not None and not plain_equipment_name and (not isinstance(local, dict) or not isinstance(local.get('name', ''), str)):
                raise ValueError('invalid localized name')
            costumes = row.get('costumes', [])
            if not isinstance(costumes, list):
                raise ValueError('invalid costumes')
            for costume in costumes:
                if not isinstance(costume, dict) or any(type(costume.get(key)) is not int or costume[key] < 0 for key in ('id', 'costume_index')):
                    raise ValueError('invalid costume mapping')
        return rows

    def load_static(self) -> StaticData:
        base = StaticData.load(self.bundled)
        try:
            updated = StaticData.load(self.root / 'static')
        except (ValueError, OSError, KeyError, TypeError, AttributeError):
            return base
        if updated.characters:
            base.characters.update(updated.characters)
        if updated.stages:
            base.stages.update(updated.stages)
        if updated.options:
            base.options = updated.options
        return base

    def _load_rows(self, filename: str) -> list[dict]:
        for path in (self.root / 'static' / filename, self.bundled / filename):
            try:
                rows = json.loads(path.read_text(encoding='utf-8-sig'))
                if isinstance(rows, dict):
                    rows = rows.get('records')
                if isinstance(rows, list) and rows and all(isinstance(row, dict) for row in rows):
                    return rows
            except (OSError, ValueError, TypeError):
                pass
        return []

    def load_equipment_items(self) -> list[dict]:
        return self._load_rows('ItemEquipTable-zh-tw.json')

    def load_skill_icons(self) -> list[dict]:
        return self._load_rows('character_skill_map.json')

    def load_character_tables(self) -> tuple[list[dict], list[dict]]:
        return self.load_equipment_items(), self.load_skill_icons()

    async def ensure_character_tables(self) -> tuple[list[dict], list[dict]]:
        equipment, skills = self.load_character_tables()
        missing = []
        if not equipment:
            missing.append('ItemEquipTable-zh-tw.json')
        if not skills:
            missing.append('character_skill_map.json')
        if missing:
            await self.update_tables(targets=missing)
        return self.load_character_tables()

    @staticmethod
    def _selected_skin(row: dict) -> int:
        skin = row.get('skin_index')
        return skin if (row.get('skin_reported') is True and row.get('skin_mapped') is True
                        and type(skin) is int and 0 <= skin <= 999) else 0

    @staticmethod
    def _image_notice(image, label: str) -> str:
        if image.missing:
            return f'{label}图片暂不可用 · 实际皮肤未知'
        if image.fallback:
            return f'{label}皮肤 {image.requested_skin_index} 图片不可用 · 回退基础外观'
        return f'基础{label}' if image.skin_index == 0 else f'{label} · 接口报告皮肤 {image.skin_index}'

    async def prepare_profile(self, context: dict) -> dict:
        from .card_meta import prepare_card_icons, prepare_badges
        result = dict(context)
        result.update(await prepare_badges(self.images))
        team = [dict(row) for row in context.get('top_nikke', [])[:5]]
        for index, row in enumerate(team):
            resource_id = row.get('resource_id', 0)
            skin = self._selected_skin(row)
            image = await self.images.resolved_source('icons', resource_id, skin)
            row.update(requested_skin_index=skin, avatar_skin_index=image.skin_index,
                       icon_url=image.source, resource_missing=image.missing,
                       skin_fallback=image.fallback, icon_hash=image.content_hash)
            notice = row.get('skin_notice') or '接口未报告有效皮肤，展示基础外观'
            row['skin_notice'] = notice + ' · ' + self._image_notice(image, 'SI头像')
            row['icon_badge'] = ('缺图' if image.missing else '基础' if image.fallback
                                 or not row.get('skin_mapped', True) else '')
            row.update(await prepare_card_icons(row, self.images))
            if index == 0:
                art = await self.images.resolved_source('portraits', resource_id, skin)
                row.update(portrait_url=art.source, portrait_skin_index=art.skin_index,
                           portrait_fallback=art.fallback, portrait_missing=art.missing,
                           portrait_hash=art.content_hash)
                row['skin_notice'] += ' · ' + self._image_notice(art, 'MI立绘')
        result['top_nikke'] = team
        result['avatar_url'] = team[0]['icon_url'] if team else PLACEHOLDER
        result['avatar_hint'] = '展示队伍首位妮姬'
        result['render_version'] = 'alice-profile-v102-portrait'
        return result

    async def prepare_character(self, context: dict) -> dict:
        result = dict(context)
        rid, skin = result.get('resource_id', 0), self._selected_skin(result)
        kinds = ('full', 'portraits', 'icons')
        images = dict(zip(kinds, await asyncio.gather(*(
            self.images.resolved_source(kind, rid, skin) for kind in kinds
        ))))
        # Prefer a selected-skin MI/SI over an unrelated base FULL. If every
        # selected asset is absent, same-type base fallbacks remain explicit.
        chosen = next((kind for kind in kinds if not images[kind].missing and not images[kind].fallback), None)
        if chosen is None:
            chosen = next((kind for kind in kinds if not images[kind].missing), 'full')
        art = images[chosen]
        result['requested_skin_index'] = skin
        result['art_skin_index'] = art.skin_index
        result['art_kind'] = chosen
        result['art_fallback'] = art.fallback
        result['art_missing'] = art.missing
        result['art_content_hash'] = art.content_hash
        result['character_icon_url'] = images['icons'].source
        result['character_icon_skin_index'] = images['icons'].skin_index
        result['character_icon_fallback'] = images['icons'].fallback
        result['character_icon_missing'] = images['icons'].missing
        result['portrait_url'] = images['portraits'].source
        result['portrait_skin_index'] = images['portraits'].skin_index
        result['portrait_fallback'] = images['portraits'].fallback
        result['portrait_missing'] = images['portraits'].missing
        result['full_url'] = images['full'].source
        result['full_skin_index'] = images['full'].skin_index
        result['full_fallback'] = images['full'].fallback
        result['full_missing'] = images['full'].missing
        label = {'full': '立绘', 'portraits': '半身像', 'icons': '头像'}[chosen]
        hint = self._image_notice(art, label)
        if chosen != 'full':
            hint = '所选皮肤立绘暂不可用 · 展示' + hint
        if art.missing:
            hint = '基础图片暂不可用 · 数据库待补全 · 实际皮肤未知'
        result['art_url'] = art.source
        result['art_hint'] = (result.get('skin_notice') or '接口未报告有效皮肤，展示基础外观') + ' · ' + hint
        async def prepare_rows(rows, image_kind):
            prepared = [dict(row) for row in rows]
            async def one(row):
                key, path = row.get('icon_key'), row.get('icon_path')
                src = await self.images.asset_source(image_kind, key, path) if key and path else PLACEHOLDER
                row['icon_missing'] = src == PLACEHOLDER
                row['icon_url'] = src
            await asyncio.gather(*(one(row) for row in prepared))
            return prepared
        result['gear'], result['skills'] = await asyncio.gather(
            prepare_rows(context.get('gear', []), 'equipment'),
            prepare_rows(context.get('skills', []), 'skills'),
        )
        from ..nikke_character.collection import prepare_character_extras
        result.update(await prepare_character_extras(result, self))
        return result

    async def refresh(self) -> dict:
        if self._update_lock.locked():
            return {'busy': True}
        async with self._update_lock:
            tables = await self.update_tables(force=True)
            images = await self.images.refresh_cached()
            return {'tables': tables, 'images': images}


_service: ResourceService | None = None


def get_resources() -> ResourceService:
    global _service
    if _service is None:
        from ..nikke_config.config import MAIN_PATH, PACKAGE_DATA_PATH
        _service = ResourceService(MAIN_PATH, PACKAGE_DATA_PATH)
    return _service
