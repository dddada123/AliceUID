"""Official Blablalink calendar CDN asset resolution, local icon reuse, and 14-day cache."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
from pathlib import Path
import time

import httpx
from PIL import Image, ImageDraw

from ..nikke_api.resource import obfuscate_path
from ..nikke_resource.cache import atomic_write
from ..nikke_resource.media import media_path

ASSET_TTL_SECONDS = 14 * 86400
_HEADERS = {
    'Origin': 'https://www.blablalink.com',
    'Referer': 'https://www.blablalink.com/activity-calendar',
    'User-Agent': 'Mozilla/5.0',
}


def banner_url(banner: str, item_type: str | None = None) -> str:
    b = str(banner or '').strip()
    if not b:
        return ''
    if item_type == 'SeasonPass':
        return obfuscate_path(f'/icon/Logo/pass/{b}.webp')
    return obfuscate_path(f'/schedule/banner/{b}.webp')


def avatar_url(resource_id: int | str, skin_index: int | str = 0) -> str:
    try:
        rid = int(resource_id)
        sk = int(skin_index or 0)
    except (TypeError, ValueError):
        return ''
    if rid <= 0:
        return ''
    return obfuscate_path(f'/character/si/si_c{rid:03d}_{sk:02d}_s.webp')


def portrait_url(resource_id: int | str, skin_index: int | str = 0) -> str:
    try:
        rid = int(resource_id)
        sk = int(skin_index or 0)
    except (TypeError, ValueError):
        return ''
    if rid <= 0:
        return ''
    return obfuscate_path(f'/character/mi/mi_c{rid:03d}_{sk:02d}_s.webp')


def reward_icon_url(reward: dict) -> str:
    if not isinstance(reward, dict):
        return ''
    module = str(reward.get('module') or '').strip().strip('/')
    rid = str(reward.get('resource_id') or '').strip()
    sk = reward.get('skin_index', 0)
    if not rid:
        return ''
    if reward.get('reward_type') == 'CharacterCostume' or (module == 'costume' and rid.isdigit()):
        return avatar_url(rid, sk)
    if module:
        return obfuscate_path(f'/icon/{module}/{rid}.webp')
    return ''


def _to_data_uri(raw: bytes, *, max_width: int = 960, fmt: str = 'PNG') -> str:
    with Image.open(io.BytesIO(raw)) as im:
        has_alpha = 'A' in im.getbands() and im.convert('RGBA').getchannel('A').getextrema()[0] < 255
        img = im.convert('RGBA' if has_alpha else 'RGB')
        if img.width > max_width:
            img = img.resize((max_width, max(1, round(img.height * max_width / img.width))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if fmt == 'JPEG' and not has_alpha:
            img.save(buf, format='JPEG', quality=90, subsampling=0, optimize=True)
            mime = 'image/jpeg'
        else:
            img.save(buf, format='PNG', optimize=True)
            mime = 'image/png'
        return f'data:{mime};base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _local_character_icon(resource_id: int | str, skin_index: int | str = 0) -> bytes | None:
    try:
        rid = int(resource_id)
        sk = int(skin_index or 0)
    except (TypeError, ValueError):
        return None
    for base in (media_path('characters/icons'),):
        for ext in ('png', 'webp', 'jpg'):
            p = base / f'si_c{rid:03d}_{sk:02d}_s.{ext}'
            if p.is_file():
                try:
                    return p.read_bytes()
                except OSError:
                    pass
    return None


def _compose_season_pass_banner(portrait_bytes: bytes | None, logo_bytes: bytes | None) -> str:
    """Compose a 3:1 (900x300) SeasonPass banner when Blablalink uses pass logo + portrait."""
    w, h = 900, 300
    canvas = Image.new('RGBA', (w, h), (18, 28, 48, 255))
    draw = ImageDraw.Draw(canvas)
    for x in range(w):
        t = x / w
        r = int(18 + 26 * t)
        g = int(28 + 38 * t)
        b = int(48 + 72 * t)
        draw.line([(x, 0), (x, h)], fill=(r, g, b, 255))
    if portrait_bytes:
        try:
            with Image.open(io.BytesIO(portrait_bytes)) as pm:
                p_rgba = pm.convert('RGBA')
                scale = (h * 1.15) / max(1, p_rgba.height)
                pw, ph = max(1, int(p_rgba.width * scale)), max(1, int(p_rgba.height * scale))
                p_resized = p_rgba.resize((pw, ph), Image.Resampling.LANCZOS)
                canvas.alpha_composite(p_resized, (w - pw - 40, -10))
        except Exception:
            pass
    if logo_bytes:
        try:
            with Image.open(io.BytesIO(logo_bytes)) as lm:
                l_rgba = lm.convert('RGBA')
                max_lw = 380
                if l_rgba.width > max_lw:
                    lh = max(1, int(l_rgba.height * max_lw / l_rgba.width))
                    l_rgba = l_rgba.resize((max_lw, lh), Image.Resampling.LANCZOS)
                canvas.alpha_composite(l_rgba, (44, max(20, (h - l_rgba.height) // 2)))
        except Exception:
            pass
    buf = io.BytesIO()
    canvas.convert('RGB').save(buf, format='JPEG', quality=90, subsampling=0, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


async def _fetch_cached_bytes(
    url: str,
    cache_dir: Path,
    *,
    client: httpx.AsyncClient,
    clock=time.time,
) -> bytes | None:
    if not url:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode('utf-8')).hexdigest()
    path = cache_dir / f'{key}.bin'
    now = clock()
    if path.is_file():
        try:
            st = path.stat()
            if now - st.st_mtime < ASSET_TTL_SECONDS and st.st_size > 32:
                return path.read_bytes()
        except OSError:
            pass
    try:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.content
        if len(data) > 32 and len(data) <= 8 * 1024 * 1024:
            atomic_write(path, data)
            return data
    except Exception:
        pass
    return None


def cleanup_old_assets(cache_dir: Path, *, now: float | None = None):
    if not cache_dir.is_dir():
        return
    cur = now if now is not None else time.time()
    for p in cache_dir.glob('*.bin'):
        try:
            if cur - p.stat().st_mtime >= ASSET_TTL_SECONDS:
                p.unlink(missing_ok=True)
        except OSError:
            pass


async def prepare_calendar_assets(
    payload: dict,
    cache_dir: Path,
    *,
    now: float | None = None,
    http: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Fetch and cache all avatars, 3:1 banners, and reward icons needed by GetCalendarDetail."""
    cleanup_old_assets(cache_dir, now=now)
    cur_now = int(now if now is not None else time.time())
    data = payload.get('data') if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return {}

    urls: dict[str, tuple[str, int, str]] = {}  # key -> (url, max_width, fmt)
    local_bytes: dict[str, bytes] = {}
    season_pass_jobs: list[tuple[str, str, str]] = []  # (key, logo_url, portrait_url)

    def _reg_avatar(rid, sk=0):
        u = avatar_url(rid, sk)
        if not u:
            return
        loc = _local_character_icon(rid, sk)
        if loc is not None:
            local_bytes[u] = loc
        else:
            urls[u] = (u, 160, 'PNG')

    # 1. character_gacha
    for row in (data.get('character_gacha') or {}).get('items') or []:
        if int(row.get('end_time') or 0) < cur_now:
            continue
        b = banner_url(row.get('banner', ''), row.get('type'))
        if b:
            urls[b] = (b, 920, 'JPEG')
        for ch in row.get('characters') or []:
            _reg_avatar(ch.get('resource_id'), 0)

    # 2. skin_gacha
    skin_items = [r for r in ((data.get('skin_gacha') or {}).get('items') or []) if int(r.get('end_time') or 0) >= cur_now]
    for idx, row in enumerate(skin_items):
        _reg_avatar(row.get('resource_id'), row.get('costume_index', 0))
        if idx == 0:
            bkey = f"skin_banner:{row.get('banner')}:{row.get('resource_id')}:{row.get('costume_index', 0)}"
            if row.get('type') == 'SeasonPass':
                season_pass_jobs.append((
                    bkey,
                    banner_url(row.get('banner', ''), 'SeasonPass'),
                    portrait_url(row.get('resource_id'), row.get('costume_index', 0)),
                ))
            else:
                b = banner_url(row.get('banner', ''), row.get('type'))
                if b:
                    urls[b] = (b, 920, 'JPEG')

    # 3. version_event & simulation_room rewards
    for sec in ('version_event', 'simulation_room'):
        for row in (data.get(sec) or {}).get('items') or []:
            if int(row.get('end_time') or 0) < cur_now:
                continue
            for rw in (row.get('rewards') or [])[:5]:
                u = reward_icon_url(rw)
                if u:
                    urls[u] = (u, 128, 'PNG')

    out: dict[str, str] = {}
    for k, raw in local_bytes.items():
        try:
            out[k] = _to_data_uri(raw, max_width=160, fmt='PNG')
        except Exception:
            pass

    sem = asyncio.Semaphore(6)

    async def _fetch_all(client: httpx.AsyncClient):
        async def _one(k: str, url: str, mw: int, fmt: str):
            async with sem:
                raw = await _fetch_cached_bytes(url, cache_dir, client=client)
                if raw:
                    try:
                        out[k] = _to_data_uri(raw, max_width=mw, fmt=fmt)
                    except Exception:
                        pass

        async def _pass(bkey: str, lurl: str, purl: str):
            async with sem:
                logo_b, port_b = await asyncio.gather(
                    _fetch_cached_bytes(lurl, cache_dir, client=client),
                    _fetch_cached_bytes(purl, cache_dir, client=client),
                )
                if logo_b or port_b:
                    out[bkey] = _compose_season_pass_banner(port_b, logo_b)

        tasks = [_one(k, u, mw, fmt) for k, (u, mw, fmt) in urls.items()]
        tasks.extend(_pass(bk, lu, pu) for bk, lu, pu in season_pass_jobs)
        if tasks:
            await asyncio.gather(*tasks)

    if http is not None:
        await _fetch_all(http)
    else:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
            await _fetch_all(client)
    return out
