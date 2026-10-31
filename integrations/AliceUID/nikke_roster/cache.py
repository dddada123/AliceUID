"""Restricted, atomically published local roster images and sliding send expiry."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

TTL = 7 * 86400
HEX = re.compile(r'^[a-f0-9]{64}$')


def identity(actor, bot, bind):
    from ..nikke_community.runtime import binding_revision
    account = [str(bind.game_id), str(bind.intl_open_id), str(bind.area_id)]
    owner = hashlib.sha256(json.dumps([str(actor), str(bot)], separators=(',', ':')).encode()).hexdigest()
    key = hashlib.sha256(json.dumps([owner, account, binding_revision(bind)], separators=(',', ':')).encode()).hexdigest()
    return key, owner


@dataclass(frozen=True)
class CachedRoster:
    key: str
    fingerprint: str
    path: Path
    owner: str
    reused: bool = False


class RosterCache:
    def __init__(self, root, *, clock=time.time):
        self.root = Path(root).absolute()
        self.clock = clock

    def _safe(self, path):
        path = Path(path).absolute()
        if path != self.root and self.root not in path.parents:
            raise ValueError('roster path outside managed root')
        # Reject every symlink ancestor, including the managed root itself.
        if any(part.is_symlink() or (getattr(part, 'is_junction', lambda: False)())
               for part in [path, *path.parents]):
            raise ValueError('roster symlink refused')
        return path

    def _directory(self, key):
        if not HEX.fullmatch(key):
            raise ValueError('invalid roster key')
        return self._safe(self.root / key)

    def _atomic(self, path, data):
        self._safe(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._safe(path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp'))
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def metadata(self, key):
        path = self._safe(self._directory(key) / 'meta.json')
        try:
            result = json.loads(path.read_text('utf-8'))
            return result if isinstance(result, dict) else {}
        except (OSError, ValueError):
            return {}

    def lookup(self, key, digest, owner):
        directory = self._directory(key)
        meta = self.metadata(key)
        if meta.get('fingerprint') != digest or meta.get('owner') != owner:
            self.invalidate_key(key)
            return None
        now = self.clock()
        last = meta.get('last_sent', 0) or meta.get('created_at', 0)
        if not isinstance(last, (int, float)) or not 0 <= now - last < TTL:
            self.invalidate_key(key)
            return None
        name = meta.get('image')
        if name != digest + '.jpg':
            return None
        image = self._safe(directory / name)
        try:
            if hashlib.sha256(image.read_bytes()).hexdigest() != meta.get('image_hash'):
                self.invalidate_key(key)
                return None
        except OSError:
            return None
        return CachedRoster(key, digest, image, owner, True)

    def store(self, key, digest, owner, image, *, semantic='', resources=None, dependencies=None):
        if not HEX.fullmatch(digest):
            raise ValueError('invalid roster fingerprint')
        directory = self._directory(key)
        path = self._safe(directory / (digest + '.jpg'))
        self._atomic(path, image)
        self._atomic(directory / 'meta.json', json.dumps(dict(fingerprint=digest, owner=owner,
            image=path.name, image_hash=hashlib.sha256(image).hexdigest(), semantic=semantic,
            resources=resources, dependencies=dependencies, created_at=self.clock(), last_sent=0)).encode())
        # Keep the previous published pair intact until the new pair commits.
        for old in directory.glob('*.jpg'):
            if old.name != path.name:
                self._safe(old).unlink(missing_ok=True)
        return CachedRoster(key, digest, path, owner)

    def mark_sent(self, prepared):
        meta = self.metadata(prepared.key)
        if meta.get('fingerprint') != prepared.fingerprint or meta.get('owner') != prepared.owner:
            return False
        self._safe(prepared.path)
        if not prepared.path.is_file():
            return False
        meta['last_sent'] = self.clock()
        self._atomic(self._directory(prepared.key) / 'meta.json', json.dumps(meta).encode())
        return True

    def invalidate_key(self, key):
        directory = self._directory(key)
        if not directory.exists():
            return
        # Flat directories only. Never recursively traverse anything supplied on disk.
        entries = list(directory.iterdir())
        for entry in entries:
            self._safe(entry)
            if not entry.is_file():
                raise ValueError('unexpected directory in managed roster cache')
        for entry in entries:
            entry.unlink()
        directory.rmdir()

    def invalidate_actor(self, actor, bot):
        owner = hashlib.sha256(json.dumps([str(actor), str(bot)], separators=(',', ':')).encode()).hexdigest()
        for key in self.keys():
            if self.metadata(key).get('owner') == owner:
                self.invalidate_key(key)

    def keys(self):
        self._safe(self.root)
        if not self.root.exists():
            return []
        return [entry.name for entry in self.root.iterdir() if HEX.fullmatch(entry.name) and not entry.is_symlink() and entry.is_dir()]

    def cleanup(self):
        deleted = 0
        for key in self.keys():
            meta = self.metadata(key)
            last = meta.get('last_sent', 0) or meta.get('created_at', 0)
            if not isinstance(last, (int, float)) or self.clock() - last >= TTL:
                try:
                    self.invalidate_key(key)
                    deleted += 1
                except (OSError, ValueError):
                    pass
        return deleted
