"""blablalink CDN 资源路径。

站点把逻辑路径哈希成两段：
- 非最后一段: <2 letters>-<2 digits>，djb2(fullPath, prime) 取模
- 最后一段: md5(fullPath).<ext>
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ResourceType:
    """Public source and cache layout; embed_size is a bound, not source dimensions."""

    logical_path_template: str
    directory: str
    description: str
    embed_size: tuple[int, int]

    def logical_path(self, resource_id: int, skin_index: int = 0) -> str:
        resource_id, skin_index = validate_resource_key(resource_id, skin_index)
        return self.logical_path_template.format(resource_id=resource_id, skin_index=skin_index)


# Preserve the existing icons/portraits directories; no cache migration is needed.
# Actual source dimensions vary with the asset. These limits only resize embedded images.
RESOURCE_TYPES = MappingProxyType({
    'icons': ResourceType('/character/si/si_c{resource_id:03d}_{skin_index:02d}_s.png',
                          'characters/icons', 'SI 方形头像；实际尺寸由资源决定', (256, 256)),
    'portraits': ResourceType('/character/mi/mi_c{resource_id:03d}_{skin_index:02d}_s.png',
                              'characters/portraits', 'MI 半身像；实际尺寸由资源决定', (600, 900)),
    'full': ResourceType('/character/full/c{resource_id:03d}_{skin_index:02d}.png',
                         'characters/full', '完整立绘；实际尺寸由资源决定', (1200, 1800)),
})


def validate_resource_key(resource_id: int, skin_index: int = 0) -> tuple[int, int]:
    """Accept integer IDs (including digit strings), never truncate floats or bools."""
    def integer(value):
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError('unsupported resource key')
        if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
            raise ValueError('unsupported resource key')
        return int(value)

    resource_id, skin_index = integer(resource_id), integer(skin_index)
    if resource_id <= 0 or not 0 <= skin_index <= 999:
        raise ValueError('unsupported resource key')
    return resource_id, skin_index

CDN = "https://sg-tools-cdn.blablalink.com"
PRIMES = [224737, 1000639, 2654435761, 2654435769, 1000621, 4294967291]


def _i32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _djb2(text: str, prime: int) -> int:
    acc = prime
    for ch in text:
        acc = _i32(acc * 33 + ord(ch))
    return acc


def obfuscate_path(path: str) -> str:
    clean = path.lstrip("/")
    parts = [p for p in clean.split("/") if p]
    segs = []
    for i, part in enumerate(parts):
        if i != len(parts) - 1:
            prime = PRIMES[i] if i < len(PRIMES) else 1
            r = ((_djb2(clean, prime) % prime) + prime) % prime
            segs.append(f"{chr(97 + (r // 26) % 26)}{chr(97 + r % 26)}-{str(r % 99).zfill(2)}")
        else:
            ext = ".".join(part.split(".")[1:])
            segs.append(f"{hashlib.md5(clean.encode()).hexdigest()}.{ext}")
    return CDN + "/" + "/".join(segs)


def character_resource_url(kind: str, resource_id: int, skin_index: int = 0) -> str:
    """Build a public CDN URL for an explicitly selected resource type."""
    if not isinstance(kind, str) or kind not in RESOURCE_TYPES:
        raise ValueError('unsupported resource kind')
    return obfuscate_path(RESOURCE_TYPES[kind].logical_path(resource_id, skin_index))


def character_icon_url(resource_id: int, skin_index: int = 0) -> str:
    """SI 方形头像，实际尺寸由资源决定。"""
    return character_resource_url('icons', resource_id, skin_index)


def character_portrait_url(resource_id: int, skin_index: int = 0) -> str:
    """MI 半身像，实际尺寸由资源决定。"""
    return character_resource_url('portraits', resource_id, skin_index)


def character_full_url(resource_id: int, skin_index: int = 0) -> str:
    """完整立绘，实际尺寸由资源决定；仅在明确请求时下载。"""
    return character_resource_url('full', resource_id, skin_index)
