"""Reuse card equipment presentation using only validated local metadata."""
from __future__ import annotations
import json
from pathlib import Path

from ..nikke_api.parser import static_weapon_type
from ..nikke_character.collection import equipment_info
from ..nikke_resource.collections import MAX_JSON_BYTES, identifier, validate_row


class LocalMetadata:
    def __init__(self, root):
        self.root = Path(root) if root is not None else None
        self.rows = {}

    async def get(self, kind, tid):
        tid = identifier(tid)
        if self.root is None or kind not in ('cubes', 'collections') or not tid:
            return None
        key = (kind, tid)
        if key not in self.rows:
            try:
                path = self.root/'static'/kind/f'{tid}.json'
                if path.stat().st_size > MAX_JSON_BYTES:
                    return None
                self.rows[key] = validate_row(json.loads(path.read_text('utf-8-sig')), kind, tid)
            except (OSError, ValueError, TypeError):
                self.rows[key] = None
        return self.rows[key]


class NoImages:
    async def get_asset(self, *args, **kwargs):
        return None


async def equipment_labels(snapshot, static, root):
    metadata, images, result = LocalMetadata(root), NoImages(), {}
    details = snapshot.get('details', {})
    if not isinstance(details, dict):
        return result
    for code, entry in details.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('detail'), dict):
            continue
        detail = entry['detail']
        name_code = identifier(code)
        if not name_code:
            continue
        context = dict(name_code=name_code, weapon_type=static_weapon_type(static.character(name_code)),
                       cube=dict(tid=detail.get('harmony_cube_tid'), lv=detail.get('harmony_cube_lv')),
                       favorite=dict(tid=detail.get('favorite_item_tid'), lv=detail.get('favorite_item_lv')))
        result[name_code] = dict(cube=await equipment_info(context, metadata, images, cube=True),
                                 favorite=await equipment_info(context, metadata, images))
    return result
