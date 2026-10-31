"""Bounded private image snapshots, persisted and verified before transmission."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import re
import tempfile
from threading import RLock
from time import time

MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 32
TTL_SECONDS = 900
_lock = RLock()
_name = re.compile(r'[a-f0-9]{64}\.bin')


def _entries(root):
    return [path for path in root.iterdir()
            if _name.fullmatch(path.name) and path.is_file() and not path.is_symlink()]


def snapshot(data: bytes, root: Path) -> tuple[bytes, bool]:
    if not data or len(data) > MAX_BYTES or MAX_FILES < 1:
        raise ValueError('outbox snapshot exceeds bounds')
    with _lock:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink():
            raise ValueError('outbox directory must not be a symlink')
        root = root.resolve()
        for path in root.glob('stage-*.tmp'):
            if path.is_file() and not path.is_symlink() and time() - path.stat().st_mtime >= TTL_SECONDS:
                path.unlink()
        checksum = sha256(data).hexdigest()
        target = root / (checksum + '.bin')
        if target.is_symlink():
            raise ValueError('outbox snapshot must not be a symlink')
        for path in _entries(root):
            if time() - path.stat().st_mtime >= TTL_SECONDS:
                path.unlink()
        hit = target.exists() and target.stat().st_size == len(data)
        if hit and sha256(target.read_bytes()).hexdigest() != checksum:
            hit = False
        entries = sorted((path for path in _entries(root) if path != target),
                         key=lambda path: path.stat().st_mtime)
        total = sum(path.stat().st_size for path in entries) + len(data)
        while entries and (total > MAX_BYTES or len(entries) + 1 > MAX_FILES):
            oldest = entries.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()
        if not hit:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=root, prefix='stage-', suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    os.chmod(temporary, 0o600)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        else:
            os.utime(target, None)
        cached = target.read_bytes()
        if sha256(cached).hexdigest() != checksum:
            raise ValueError('outbox snapshot verification failed')
        return cached, hit
