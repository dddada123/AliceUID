"""Local photo backdrops in CSS pixels, with no network or source writes.

Call wallpaper_scene once per frame and reuse that RGBA image for the visible
background and glass crops. Missing themed sources raise FileNotFoundError;
the caller owns any fallback. No external directories are searched. Finished
scenes and decoded sources are deliberately not cached: each render chooses a
fresh sequence without retaining large images for the lifetime of the bot.
"""
from __future__ import annotations

import base64
import io
import random
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image, ImageFilter, ImageOps

from .background_sources import get_background_provider

MAX_PIXELS = 24_000_000
CROSSFADE = 128
SEAM_BLUR = 8
_PREFIXES = {'dark': '暗色背景', 'light': '亮色背景'}
_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
Chooser = Callable[[Sequence[Path]], Path]


def _validate(width: int, height: int, theme: str) -> None:
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise ValueError('Wallpaper dimensions must be positive integers')
    if width * height > MAX_PIXELS:
        raise ValueError(f'Wallpaper exceeds {MAX_PIXELS:,} pixels')
    if theme not in _PREFIXES:
        raise ValueError("Wallpaper theme must be 'dark' or 'light'")


def _sources(theme: str) -> tuple[Path, ...]:
    provider = get_background_provider()
    paths = tuple(sorted(set(p for p in provider.candidates(theme)
                             if p.is_file() and p.name.startswith(_PREFIXES[theme])
                             and p.suffix.lower() in _EXTENSIONS)))
    if not paths:
        raise FileNotFoundError(f'No {theme} wallpaper photos from background provider')
    return paths


def _tile(path: Path, width: int, limit: int, *, center: bool) -> tuple[Image.Image, int]:
    with Image.open(path) as source:
        photo = ImageOps.exif_transpose(source)
        natural = max(1, round(photo.height * width / photo.width))
        used = min(limit, natural)
        # Crop before resizing: even an extremely wide, one-row output never
        # allocates an enormous width-scaled portrait just to discard its rows.
        needed = min(photo.height, used * photo.width / width)
        top = (photo.height - needed) / 2 if center else 0
        tile = photo.resize((width, used), Image.Resampling.LANCZOS,
                            box=(0, top, photo.width, top + needed)).convert('RGBA')
    return tile, natural


def _row_mask(width: int, values: list[int]) -> Image.Image:
    mask = Image.new('L', (1, len(values)))
    mask.putdata(values)
    return mask.resize((width, len(values)))


def _join(previous: Image.Image, incoming: Image.Image) -> Image.Image:
    """Smoothstep has exact 0/1 endpoints and zero slope at both ends.

    Local blur is feathered with a second smooth mask that is exactly zero at
    each boundary. Thus neither the photo weights nor the blur jump there.
    """
    width, height = previous.size
    t = [i / (height - 1) if height > 1 else 1.0 for i in range(height)]
    weights = [round(255 * v * v * (3 - 2 * v)) for v in t]
    mixed = Image.composite(incoming, previous, _row_mask(width, weights))
    blur_weights = [round(255 * (4 * v * (1 - v)) ** 2) for v in t]
    blurred = mixed.filter(ImageFilter.GaussianBlur(min(SEAM_BLUR, height / 8)))
    return Image.composite(blurred, mixed, _row_mask(width, blur_weights))


def wallpaper_scene(width: int, height: int, theme: str = 'dark',
                    chooser: Chooser | None = None) -> Image.Image:
    """Return a fresh RGBA scene; dimensions and overlap are CSS pixels.

    chooser is a random.choice-compatible callable, useful for deterministic
    tests. Its candidates strictly match theme and exclude the preceding photo
    when alternatives exist. A missing theme or corrupt photo raises explicitly.
    With only one available photo repetition is unavoidable; packaged themes
    contain three. No full-scene cache, network, original-file writes, or font
    changes are involved.
    """
    _validate(width, height, theme)
    paths = _sources(theme)
    choose = chooser if chooser is not None else random.choice

    def pick(previous: Path | None) -> Path:
        candidates = tuple(p for p in paths if p != previous) or paths
        selected = choose(candidates)
        if selected not in candidates:
            raise ValueError('Wallpaper chooser returned a non-candidate path')
        return selected

    previous = pick(None)
    tile, natural = _tile(previous, width, height, center=True)
    if natural >= height:
        return tile
    scene = Image.new('RGBA', (width, height))
    scene.paste(tile, (0, 0))
    bottom = tile.height
    while bottom < height:
        path = pick(previous)
        # A tiny image still makes forward progress; normal portraits use 128.
        with Image.open(path) as source:
            oriented = ImageOps.exif_transpose(source)
            incoming_natural = max(1, round(oriented.height * width / oriented.width))
        overlap = min(CROSSFADE, bottom // 4, incoming_natural // 4)
        start = bottom - overlap
        tile, _ = _tile(path, width, height - start, center=False)
        visible_overlap = min(overlap, tile.height)
        if visible_overlap:
            old = scene.crop((0, start, width, start + visible_overlap))
            blend = _join(old, tile.crop((0, 0, width, visible_overlap)))
            scene.paste(blend, (0, start))
        if tile.height > visible_overlap:
            scene.paste(tile.crop((0, visible_overlap, width, tile.height)),
                        (0, start + visible_overlap))
        bottom = start + tile.height
        previous = path
    return scene


def wallpaper_uri(width: int, height: int, theme: str = 'dark',
                  chooser: Chooser | None = None) -> str:
    """Encode one newly selected scene as a PNG data URI (not cached)."""
    output = io.BytesIO()
    wallpaper_scene(width, height, theme, chooser).save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
