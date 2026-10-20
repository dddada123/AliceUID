"""Bounded forward image transport without changing source renders or caches.

Opaque long PNG cards follow the successful roster JPEG route at configurable
quality (default 95) / 4:4:4. Pages retain every original pixel row and column.
Existing roster JPEGs within limits are sent byte-for-byte; QR login is excluded
by the caller. Transparent images keep lossless PNG to preserve their appearance.
"""
from __future__ import annotations

import base64
from io import BytesIO
import math

from PIL import Image

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 64_000_000
MAX_HEIGHT = 4096
MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
MAX_PAGES = 32
JPEG_QUALITY = 95


class ForwardImageError(ValueError):
    pass


def encode_forward_pages(data, quality=JPEG_QUALITY):
    if type(quality) is not int or not 0 <= quality <= 100:
        quality = JPEG_QUALITY
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ForwardImageError('forward source size out of bounds')
    with Image.open(BytesIO(data)) as source:
        width, height = source.size
        if source.format not in ('PNG', 'JPEG', 'WEBP') or width * height > MAX_PIXELS:
            raise ForwardImageError('forward image geometry out of bounds')
        if getattr(source, 'n_frames', 1) != 1:
            raise ForwardImageError('animated cards are unsupported')
        if source.format == 'JPEG' and height <= MAX_HEIGHT and len(data) <= MAX_PAGE_BYTES:
            source.verify()
            return [data]
        source.load()
        dpi = source.info.get('dpi')
        metadata = {}
        if (isinstance(dpi, (tuple, list)) and len(dpi) == 2
                and all(isinstance(x, (int, float)) and math.isfinite(x) and 0 < x <= 2400 for x in dpi)):
            metadata['dpi'] = tuple(dpi)
        if isinstance(source.info.get('icc_profile'), bytes):
            metadata['icc_profile'] = source.info['icc_profile']
        transparent = ('transparency' in source.info or
                       ('A' in source.getbands() and source.getchannel('A').getextrema()[0] < 255))
        image = source.convert('RGBA' if transparent else 'RGB')
        pages = []
        total = 0

        def encode(top, bottom):
            nonlocal total
            page = image.crop((0, top, width, bottom))
            output = BytesIO()
            if transparent:
                page.save(output, format='PNG', optimize=True, **metadata)
            else:
                page.save(output, format='JPEG', quality=quality, subsampling=0,
                          optimize=True, progressive=False, **metadata)
            encoded = output.getvalue()
            if len(encoded) > MAX_PAGE_BYTES:
                if bottom - top <= 1:
                    raise ForwardImageError('one image row exceeds page limit')
                middle = (top + bottom) // 2
                encode(top, middle)
                encode(middle, bottom)
                return
            total += len(encoded)
            pages.append(encoded)
            if len(pages) > MAX_PAGES or total > MAX_TOTAL_BYTES:
                raise ForwardImageError('complete forward exceeds transport bounds')

        for top in range(0, height, MAX_HEIGHT):
            encode(top, min(top + MAX_HEIGHT, height))
        return pages


def prepare_forward_content(content):
    """Only transform inline image bytes; never fetch URLs or touch cache files."""
    from gsuid_core.segment import MessageSegment
    from gsuid_core.logger import logger
    from ..nikke_config.config import AliceUIDConfig
    quality = AliceUIDConfig.get_config('AliceUID_ForwardJpegQuality').data
    result = []
    for item in content:
        data = getattr(item, 'data', None)
        if getattr(item, 'type', None) != 'image' or not isinstance(data, str) or not data.startswith('base64://'):
            result.append(item)
            continue
        # Bound before decoding the Base64 to avoid an additional huge allocation.
        if len(data) > MAX_INPUT_BYTES * 4 // 3 + 32:
            raise ForwardImageError('inline image is too large')
        raw = base64.b64decode(data[9:], validate=True)
        pages = encode_forward_pages(raw, quality=quality)
        logger.info(f'[AliceUID] 转发图片处理 input_bytes={len(raw)} output_bytes={sum(map(len, pages))} pages={len(pages)}')
        result.extend(MessageSegment.image(page) for page in pages)
    return result
