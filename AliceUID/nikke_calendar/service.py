"""Anonymous screenshots of the official current activity calendar only."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

CALENDAR_URL = 'https://www.blablalink.com/activity-calendar'
CALENDAR_SELECTOR = '[class*="bg-calendar-line"]'
MAX_SCREENSHOT_BYTES = 12 * 1024 * 1024
MAX_SCREENSHOT_PIXELS = 16_000_000
MAX_SCREENSHOT_HEIGHT = 12_000
_CAPTURE_LOCK = asyncio.Lock()
log = logging.getLogger(__name__)


class CalendarUnavailable(Exception):
    """Public calendar unavailable or refresh in persisted cooldown."""


@dataclass(frozen=True)
class CalendarImage:
    png: bytes
    captured_at: float
    stale: bool = False
    from_cache: bool = False

    def caption(self) -> str:
        stamp = datetime.fromtimestamp(self.captured_at, ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S UTC+8')
        state = '官网暂不可用，以下为旧缓存，活动可能已变化。' if self.stale else '官网当前默认活动日历（裁剪日历内容）。'
        return (f'{state}\n拍摄时间：{stamp}\n来源：{CALENDAR_URL}\n'
                '官网默认页面，不按绑定区服筛选；多标签仅展示当前选中项。\n'
                '不支持历史月份；Raid仅为活动日程，不含阵容或分数。')


def _atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_png(data: bytes):
    if not isinstance(data, bytes) or not data or len(data) > MAX_SCREENSHOT_BYTES:
        raise ValueError('calendar screenshot byte limit')
    with Image.open(io.BytesIO(data)) as image:
        if (image.format != 'PNG' or image.width < 300 or image.height < 200
                or image.width > 2000 or image.height > MAX_SCREENSHOT_HEIGHT
                or image.width * image.height > MAX_SCREENSHOT_PIXELS):
            raise ValueError('calendar screenshot dimensions or format')
        image.verify()


async def capture_page(page) -> bytes:
    """Verify current real DOM before cropping it; never synthesize event rows."""
    response = await page.goto(CALENDAR_URL, wait_until='domcontentloaded', timeout=45_000)
    if response is None or response.status != 200 or page.url.rstrip('/') != CALENDAR_URL:
        raise CalendarUnavailable('官网日历返回错误状态或跳转。')
    root = page.locator(CALENDAR_SELECTOR)
    await root.wait_for(state='visible', timeout=30_000)
    if await root.count() != 1:
        raise CalendarUnavailable('官网日历结构已变化。')
    await page.wait_for_function(r"""selector => {
        const e = document.querySelector(selector);
        if (!e) return false;
        const text = e.innerText || '';
        const dates = text.match(/\d{2,4}\/\d{1,2}\/\d{1,2}\s+\d{1,2}:\d{2}/g) || [];
        const sections = e.querySelectorAll('[class*="calendar-title.png"]').length;
        const loading = [...e.querySelectorAll('[class*="skeleton"], [class*="loading"], [aria-busy="true"]')]
            .some(n => n.getBoundingClientRect().width && n.getBoundingClientRect().height);
        return dates.length >= 2 && sections >= 3 && !loading && text.length >= 100;
    }""", arg=CALENDAR_SELECTOR, timeout=30_000)
    if await page.locator('input[type="password"]:visible, #loginPwdForm_account:visible').count():
        raise CalendarUnavailable('官网日历出现登录窗口。')
    # Preserve the page's content and layout, expanding only its scrolling ancestors.
    # Hide sibling UI (cookie banner/navigation/sidebar) so it cannot cover the crop.
    # A stylesheet also covers UI inserted later by the consent manager.
    await page.add_style_tag(content=(
        'body * { visibility: hidden !important; } '
        f'{CALENDAR_SELECTOR}, {CALENDAR_SELECTOR} * {{ visibility: visible !important; }}'
    ))
    await root.evaluate("""e => {
        for (let p=e; p; p=p.parentElement) {
            if (p.parentElement) for (const sibling of p.parentElement.children)
                if (sibling !== p) sibling.style.visibility='hidden';
            p.style.overflow='visible'; p.style.maxHeight='none'; p.style.height='auto';
            if (['sticky','fixed'].includes(getComputedStyle(p).position)) p.style.position='static';
            p.scrollTop=0;
        }
        e.style.width='960px';
        for (const image of e.querySelectorAll('img')) { image.loading='eager'; image.scrollIntoView(); }
    }""")
    await page.wait_for_function("""selector => {
        const imgs = [...document.querySelector(selector).querySelectorAll('img')];
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }""", arg=CALENDAR_SELECTOR, timeout=30_000)
    await page.evaluate('() => document.fonts.ready')
    await root.evaluate("""e => new Promise(resolve => {
        window.scrollTo(0,0); requestAnimationFrame(()=>requestAnimationFrame(resolve));
    })""")
    box = await root.bounding_box()
    if (not box or box['height'] > MAX_SCREENSHOT_HEIGHT or box['width'] > 2000
            or box['height'] * box['width'] > MAX_SCREENSHOT_PIXELS):
        raise CalendarUnavailable('官网日历内容超出截图尺寸限制。')
    data = await root.screenshot(type='png', animations='disabled', timeout=30_000)
    _validate_png(data)
    return data


async def capture_calendar(*, channel: str = 'auto') -> bytes:
    """Use a fresh anonymous, nonpersistent browser; never reuse login storage."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = None
        choices = (None, 'msedge') if channel == 'auto' else ((None,) if channel == 'chromium' else ('msedge',))
        for candidate in choices:
            try:
                browser = await playwright.chromium.launch(headless=True, channel=candidate)
                break
            except Exception:
                if candidate == choices[-1]:
                    raise CalendarUnavailable('截图浏览器不可用。') from None
        context = None
        try:
            context = await browser.new_context(
                viewport={'width': 1440, 'height': 1000}, device_scale_factor=1,
                locale='zh-TW', timezone_id='Asia/Shanghai',
            )
            page = await context.new_page()
            return await capture_page(page)
        finally:
            if context is not None:
                await context.close()
            await browser.close()


class CalendarService:
    def __init__(self, root: Path, *, capture=None, channel='auto', clock=time.time,
                 ttl=1800, cooldown=300):
        self.root = Path(root)
        self.capture = capture
        self.channel = channel if channel in {'auto', 'chromium', 'msedge'} else 'auto'
        self.clock = clock
        self.ttl = max(300, int(ttl))
        self.cooldown = max(300, int(cooldown))
        self.image_path = self.root / 'current.png'
        self.meta_path = self.root / 'current.json'

    def _metadata(self) -> dict:
        try:
            meta = json.loads(self.meta_path.read_text(encoding='utf-8'))
            if not isinstance(meta, dict):
                return {}
            for key in ('captured_at', 'retry_after', 'last_attempt'):
                number = float(meta.get(key, 0))
                if not math.isfinite(number) or number < 0:
                    raise ValueError('invalid calendar cache time')
                meta[key] = number
            return meta
        except (OSError, ValueError, TypeError, OverflowError):
            return {}

    def _cached(self, meta: dict, now: float) -> CalendarImage | None:
        try:
            if meta.get('url') != CALENDAR_URL or not 0 < meta.get('captured_at', 0) <= now + 60:
                return None
            data = self.image_path.read_bytes()
            _validate_png(data)
            if hashlib.sha256(data).hexdigest() != meta.get('sha256'):
                return None
            return CalendarImage(data, meta['captured_at'], from_cache=True)
        except (OSError, ValueError, Image.DecompressionBombError):
            return None

    async def get(self) -> CalendarImage:
        # Shared across all service instances/groups; a queued caller rechecks disk state.
        async with _CAPTURE_LOCK:
            now = self.clock()
            meta = self._metadata()
            cached = self._cached(meta, now)
            if cached and 0 <= now - cached.captured_at < self.ttl:
                return cached
            if now < meta.get('retry_after', 0):
                if cached:
                    return CalendarImage(cached.png, cached.captured_at, stale=True, from_cache=True)
                raise CalendarUnavailable('官网日历暂不可用，正在冷却，请至少五分钟后再试。')
            # Persist before opening a browser: restart/repeated requests cannot bypass cooldown.
            meta.update(last_attempt=now, retry_after=now + self.cooldown)
            _atomic_write(self.meta_path, json.dumps(meta, ensure_ascii=False).encode())
            try:
                capture = self.capture
                data = await asyncio.wait_for(
                    capture() if capture else capture_calendar(channel=self.channel), timeout=150,
                )
                _validate_png(data)
                captured_at = self.clock()
                _atomic_write(self.image_path, data)
                _atomic_write(self.meta_path, json.dumps({
                    'version': 1, 'url': CALENDAR_URL, 'captured_at': captured_at,
                    'last_attempt': now, 'retry_after': now + self.cooldown,
                    'sha256': hashlib.sha256(data).hexdigest(),
                }, ensure_ascii=False).encode())
                return CalendarImage(data, captured_at)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning('AliceUID official calendar capture failed: %s', type(exc).__name__)
                meta['retry_after'] = max(meta['retry_after'], self.clock() + self.cooldown)
                try:
                    _atomic_write(self.meta_path, json.dumps(meta, ensure_ascii=False).encode())
                except OSError:
                    pass
                if cached:
                    return CalendarImage(cached.png, cached.captured_at, stale=True, from_cache=True)
                raise CalendarUnavailable('官网日历暂不可用，未发送错误页。请至少五分钟后再试。') from None


_service: CalendarService | None = None


def get_calendar() -> CalendarService:
    global _service
    if _service is None:
        from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
        try:
            channel = AliceUIDConfig.get_config('AliceUID_BrowserChannel').data or 'auto'
        except Exception:
            channel = 'auto'
        _service = CalendarService(MAIN_PATH / 'cache' / 'calendar', channel=channel)
    return _service
