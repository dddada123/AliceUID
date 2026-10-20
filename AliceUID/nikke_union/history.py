"""Atomic, guild/region/season-scoped data snapshots, with no credentials."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..nikke_resource.cache import atomic_write


class UnionHistory:
    def __init__(self, root):
        self.root = Path(root)

    def _path(self, group, season):
        key = hashlib.sha256(json.dumps([*group, str(season)], ensure_ascii=True).encode()).hexdigest()
        return self.root / (key + '.json')

    def read(self, group, season):
        path = self._path(group, season)
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                return None
            data = json.loads(path.read_text('utf-8'))
            if data.get('scope') != [*group, str(season)] or data.get('version') != 1:
                return None
            snapshot = data.get('snapshot')
            return snapshot if isinstance(snapshot, dict) else None
        except (OSError, ValueError, TypeError):
            return None

    def save(self, group, season, snapshot):
        public_fields = ('attacks', 'members', 'guild_name', 'fetched_at', 'level_payload')
        saved = {key: snapshot[key] for key in public_fields}
        saved['members_reference'] = bool(snapshot.get('members_reference', False))
        saved['finalized'] = bool(snapshot.get('finalized', False))
        # Never erase a useful end-of-season record with an empty response.
        old = self.read(group, season)
        if old:
            if not saved['attacks']:
                saved['attacks'], saved['members'] = old['attacks'], old['members']
                saved['members_reference'] = bool(old.get('members_reference', False))
                saved['finalized'] = bool(old.get('finalized', False))
            if not saved['level_payload'].get('level_info'):
                saved['level_payload'] = old['level_payload']
        if not saved['attacks'] and not saved['level_payload'].get('level_info'):
            return
        atomic_write(self._path(group, season), json.dumps(
            dict(version=1, scope=[*group, str(season)], snapshot=saved),
            ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
