"""Classic original-image nodes; JPEG conversion is explicitly optional."""
from __future__ import annotations

import base64
from io import BytesIO
import math

from PIL import Image

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 64_000_000
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
TARGET_FORWARD_BYTES = 1_200_000
AUTO_COMPRESS_RAW_BYTES = 1_500_000
JPEG_QUALITY = 95


class ForwardImageError(ValueError):
    pass


def _save_jpeg(image, quality: int, *, subsampling: int, metadata: dict) -> bytes:
    for optimize in (True, False):
        output = BytesIO()
        try:
            image.save(
                output,
                format='JPEG',
                quality=quality,
                subsampling=subsampling,
                optimize=optimize,
                progressive=False,
                **metadata,
            )
            return output.getvalue()
        except OSError:
            if not optimize:
                raise


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
        if source.format == 'JPEG' and len(data) <= min(MAX_OUTPUT_BYTES, TARGET_FORWARD_BYTES):
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
        if transparent:
            output = BytesIO()
            image.save(output, format='PNG', optimize=True, **metadata)
            encoded = output.getvalue()
        else:
            if width > 65500 or height > 65500:
                raise ForwardImageError('complete image exceeds JPEG dimensions')
            encoded = _save_jpeg(image, quality, subsampling=0, metadata=metadata)
            if len(encoded) > TARGET_FORWARD_BYTES and MAX_OUTPUT_BYTES >= TARGET_FORWARD_BYTES:
                for step_q in [min(quality, q) for q in (90, 84, 78, 72)]:
                    candidate = _save_jpeg(image, step_q, subsampling=2, metadata=metadata)
                    encoded = candidate
                    if len(encoded) <= TARGET_FORWARD_BYTES:
                        break
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise ForwardImageError('complete image exceeds transport bounds')
        return [encoded]


def prepare_forward_content(content):
    """Snapshot inline cards before standard nodes; adaptively compress oversized PNGs for reliable forwarding."""
    from gsuid_core.segment import MessageSegment
    from gsuid_core.logger import logger
    from ..nikke_config.config import AliceUIDConfig
    from ..nikke_config.config import CACHE_PATH
    from .outbox import snapshot
    quality = AliceUIDConfig.get_config('AliceUID_ForwardJpegQuality').data
    reencode = AliceUIDConfig.get_config('AliceUID_ForwardReencode').data is True
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
        oversized_non_transparent = False
        if not reencode and len(raw) > AUTO_COMPRESS_RAW_BYTES:
            with Image.open(BytesIO(raw)) as probe:
                has_alpha = ('transparency' in probe.info or
                             ('A' in probe.getbands() and probe.getchannel('A').getextrema()[0] < 255))
                if probe.format != 'JPEG' and not has_alpha:
                    oversized_non_transparent = True
        if reencode or oversized_non_transparent:
            pages = encode_forward_pages(raw, quality=quality if reencode else min(int(quality or JPEG_QUALITY), 88))
        else:
            # The old roster path read a cached JPG straight into image(data).
            # Keep the exact bytes for PNG/JPEG/WEBP alike, including metadata.
            if not raw or len(raw) > min(MAX_INPUT_BYTES, MAX_OUTPUT_BYTES):
                raise ForwardImageError('original image size out of bounds')
            with Image.open(BytesIO(raw)) as original:
                if (original.format not in ('PNG', 'JPEG', 'WEBP')
                        or original.width * original.height > MAX_PIXELS
                        or getattr(original, 'n_frames', 1) != 1):
                    raise ForwardImageError('original image geometry out of bounds')
                original.verify()
            pages = [raw]
        with Image.open(BytesIO(raw)) as source, Image.open(BytesIO(pages[0])) as encoded:
            strategy = 'jpeg_optional' if reencode else ('jpeg_auto_large' if oversized_non_transparent else 'classic_original')
            logger.info(f'[AliceUID] 转发图片 strategy={strategy} source_format={source.format} '
                        f'output_format={encoded.format} width={encoded.width} height={encoded.height} '
                        f'input_bytes={len(raw)} output_bytes={len(pages[0])}')
        for page in pages:
            cached, hit = snapshot(page, CACHE_PATH / 'forward_outbox')
            logger.info(f'[AliceUID] 转发缓存 stage=cache_ready bytes={len(cached)} hit={hit}')
            result.append(MessageSegment.image(cached))
    texts = [str(item.data) for item in result if getattr(item, 'type', None) == 'text' and item.data]
    remaining = [item for item in result if getattr(item, 'type', None) != 'text']
    return ([MessageSegment.text('\n'.join(texts))] if texts else []) + remaining
