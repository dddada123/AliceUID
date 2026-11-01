"""Atomic, guild/region/season-scoped data snapshots, with no credentials."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..nikke_resource.cache import atomic_write
from ..nikke_time import time_metadata


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
        saved['season'] = snapshot.get('season', {})
        saved['time_metadata'] = time_metadata(saved['fetched_at'], group[1])
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
        try:
            if saved['finalized']:
                self._save_result(group, season, saved)
            self._compact(group)
        except (OSError, ValueError, TypeError, KeyError):
            # A failed archival write must retain full source data and not break a query.
            import logging
            logging.getLogger(__name__).warning('AliceUID raid result compaction deferred')

    def result(self, group, season):
        """Data interface only; no annual/quarter/month summary command is registered."""
        path = self.root/'results'/self._path(group, season).name
        try:
            if path.stat().st_size > 1024*1024:
                return None
            data = json.loads(path.read_text('utf-8'))
            return data if data.get('scope') == [*group, str(season)] and data.get('version') == 1 else None
        except (OSError, ValueError, TypeError):
            return None

    def _save_result(self, group, season, snapshot):
        previous = self.result(group, season)
        if previous and previous.get('finalized') and not snapshot.get('finalized'):
            return  # An earlier observation cannot replace a settled result.
        members = {}
        days = {}
        for attack in snapshot.get('attacks', []):
            day = str(attack['day'])
            total = days.setdefault(day, dict(records=0, damage=0, final_hits=0,
                kind='boss_clear_records' if day == '0' else 'personal_attacks'))
            total['records'] += 1
            total['damage'] += attack['damage']
            total['final_hits'] += int(attack['is_final_hit'])
            if day == '0':
                continue  # Day1 is boss progress, never personal attendance/knife counts.
            member = hashlib.sha256(json.dumps([*group[:2], attack['openid']]).encode()).hexdigest()
            row = members.setdefault(member, dict(name=attack['nickname'], days={}))
            stats = row['days'].setdefault(day, dict(attacks=0, damage=0, final_hits=0))
            stats['attacks'] += 1
            stats['damage'] += attack['damage']
            stats['final_hits'] += int(attack['is_final_hit'])
        body = dict(version=1, scope=[*group, str(season)], finalized=bool(snapshot.get('finalized')),
                    guild_name=snapshot.get('guild_name'), fetched_at=snapshot.get('fetched_at'),
                    time_metadata=time_metadata(snapshot.get('fetched_at'), group[1]),
                    season=snapshot.get('season', {}), members_reference=bool(snapshot.get('members_reference')),
                    days=days, members=members)
        encoded = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
        if len(encoded) > 1024*1024:
            raise ValueError('compact raid result exceeds budget')
        atomic_write(self.root/'results'/self._path(group, season).name, encoded)

    def _compact(self, group):
        """Keep only current/previous full snapshots, after saving compact observations."""
        entries = []
        for path in self.root.glob('*.json'):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16*1024*1024:
                continue
            try:
                data = json.loads(path.read_text('utf-8'))
                scope = data['scope']
                if data.get('version') == 1 and scope[:-1] == list(group) and str(scope[-1]).isdigit():
                    entries.append((int(scope[-1]), path, data['snapshot']))
            except (OSError, ValueError, TypeError, KeyError):
                continue
        for season, path, snapshot in sorted(entries, reverse=True)[2:]:
            self._save_result(group, season, snapshot)
            if self.result(group, season) is not None:
                path.unlink()
