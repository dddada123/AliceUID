"""Observe critical transfers without routing or disabling the browser HTTP cache."""
import asyncio
import base64
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from .errors import SoloUnavailable, SoloTransient


@dataclass
class BrowserRecovery:
    # One instance per command, shared by its existing three-attempt budget.
    native_language: bool = False

    @property
    def language(self):
        return 'ko' if self.native_language else 'zh-CN'


async def wait_until(page, predicate, *, arg=None, timeout=90000):
    """Poll with direct evaluation; wait_for_function internally evals under CSP."""
    from playwright.async_api import Error, TimeoutError as BrowserTimeout
    deadline = time.monotonic() + timeout/1000
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BrowserTimeout('DILDORO页面控件等待超时。')
        try:
            result = await asyncio.wait_for(page.evaluate(predicate, arg), timeout=remaining)
            if result:
                return result
        except asyncio.TimeoutError:
            raise BrowserTimeout('DILDORO页面控件等待超时。') from None
        except Error as exc:
            # Navigation may replace the execution context between two polls.
            if 'Execution context was destroyed' not in str(exc) and 'Cannot find context' not in str(exc):
                raise
        await asyncio.sleep(min(.1, max(0, deadline-time.monotonic())))


class LoadMonitor:
    def __init__(self, page, heartbeat):
        self.page, self.heartbeat = page, heartbeat
        self.translations = set()
        self.critical = set()
        self.failure = asyncio.get_running_loop().create_future()
        self.cdp = None
        self.requests = {}
        self.listeners = []

    def relevant(self, url, resource=''):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'dildoro.com':
            return False
        path = parsed.path
        if path.startswith('/api/'):
            return path in {'/api/fetch', '/api/sr-rank/list', '/api/sr-rank/sets',
                            '/api/boss', '/api/boss/rec', '/api/sim', '/api/sim-heavy'}
        # Optional images/fonts/background polling cannot keep a stuck step alive.
        return resource in {'document', 'script', 'stylesheet'} or self.is_translation(url)

    @staticmethod
    def is_translation(url):
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and parsed.netloc == 'dildoro.com'
                and parsed.path == '/i18n/zh-cn.json')

    def touch(self):
        self.heartbeat[0] = time.monotonic()

    def fail(self, error):
        if not self.failure.done():
            self.failure.set_result(error)

    def requested(self, request):
        if self.relevant(request.url, request.resource_type):
            self.touch()
            self.critical.add(request)
        if self.is_translation(request.url):
            self.translations.add(request)

    def responded(self, response):
        request = response.request
        if self.relevant(response.url, request.resource_type):
            self.touch()
        if self.is_translation(response.url) and response.status >= 400:
            if response.status in {401, 403, 429}:
                self.fail(SoloUnavailable(f'DILDORO翻译资源访问受限（HTTP {response.status}），本次停止。'))
            else:
                self.fail(SoloTransient('网站中文翻译资源加载失败。',
                                        stage=self.heartbeat[1], reason='I18N_FAILED'))

    def finished(self, request):
        if request in self.critical:
            self.touch()
        self.critical.discard(request)
        self.translations.discard(request)

    def failed(self, request):
        self.critical.discard(request)
        if request in self.translations:
            self.translations.discard(request)
            self.fail(SoloTransient('网站中文翻译资源传输失败。',
                                    stage=self.heartbeat[1], reason='I18N_FAILED'))

    def sent(self, event):
        request_id = event.get('requestId')
        self.requests.pop(request_id, None)
        request = event.get('request', {})
        if self.relevant(request.get('url', ''), str(event.get('type', '')).lower()):
            self.requests[request_id] = True

    def received_bytes(self, event):
        # Headers alone do not prove that a 1.2 MB response is making progress.
        if event.get('requestId') in self.requests and event.get('dataLength', 0) > 0:
            self.touch()

    def completed(self, event):
        if self.requests.pop(event.get('requestId'), None):
            self.touch()

    async def start(self):
        for name, handler in [('request', self.requested), ('response', self.responded),
                              ('requestfinished', self.finished), ('requestfailed', self.failed)]:
            self.page.on(name, handler)
            self.listeners.append((name, handler))
        try:
            self.cdp = await self.page.context.new_cdp_session(self.page)
            self.cdp.on('Network.requestWillBeSent', self.sent)
            self.cdp.on('Network.dataReceived', self.received_bytes)
            self.cdp.on('Network.loadingFinished', self.completed)
            self.cdp.on('Network.loadingFailed', self.completed)
            await self.cdp.send('Network.enable')
        except Exception:
            # Non-Chromium hosts still get lifecycle monitoring and bounded waits.
            if self.cdp is not None:
                await self.cdp.detach()
            self.cdp = None

    async def run(self, operation):
        task = asyncio.create_task(operation)
        try:
            await asyncio.wait({task, self.failure}, return_when=asyncio.FIRST_COMPLETED)
            if self.failure.done():
                raise self.failure.result()
            return task.result()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def close(self):
        for name, handler in self.listeners:
            self.page.remove_listener(name, handler)
        if not self.failure.done():
            self.failure.cancel()
        if self.cdp is not None:
            try:
                await self.cdp.detach()
            except Exception:
                pass


async def prepare_visuals(page, result, *, timeout_ms=4000):
    """Bound optional assets; only computed and validated results reach this step."""
    return await result.evaluate("""async (root, timeout) => {
        const wait = promise => Promise.race([
            Promise.resolve(promise).then(()=>true,()=>false),
            new Promise(resolve=>setTimeout(()=>resolve(false),timeout))]);
        const images=[...root.querySelectorAll('img')];
        images.forEach(image=>image.loading='eager');
        const [fontsReady] = await Promise.all([
            wait(document.fonts.ready),
            Promise.all(images.map(image=>wait(image.decode())))
        ]);
        const missing=images.filter(image=>!image.complete||image.naturalWidth===0);
        // Stop loading only failed result images. Preserve their intrinsic box.
        for(const image of missing) {
            const rect=image.getBoundingClientRect();
            const box=document.createElement('span');
            box.className=image.className;
            box.setAttribute('data-alice-placeholder','true');
            box.textContent='?';
            box.style.cssText=`display:inline-flex;align-items:center;justify-content:center;`+
                `width:${Math.max(16,rect.width)}px;height:${Math.max(16,rect.height)}px;`+
                `background:#394454;color:#fff;flex-shrink:0;font:20px sans-serif;`;
            image.removeAttribute('srcset'); image.removeAttribute('src');
            image.replaceWith(box);
        }
        // Use installed fonts for rendering; a timed-out network font may still
        // keep the document-level ready promise pending after it is removed.
        let fontFallback=!fontsReady;
        for(const face of [...document.fonts]) {
            if(face.status==='loading'||face.status==='error') {
                document.fonts.delete(face); fontFallback=true;
            }
        }
        if(fontFallback) {
            const style=document.createElement('style');
            style.textContent='[data-alice-font-fallback], [data-alice-font-fallback] * {'+
                'font-family:"Microsoft YaHei","Malgun Gothic","Noto Sans CJK SC",sans-serif!important}';
            document.head.append(style); root.setAttribute('data-alice-font-fallback','true');
        }
        return {missing_images:missing.length,font_fallback:fontFallback};
    }""", timeout_ms)


async def capture_visual(page, result, *, font_fallback=False, timeout_ms=90000):
    if not font_fallback:
        return await result.screenshot(type='png', animations='disabled', timeout=timeout_ms)
    # Playwright's normal element screenshot waits on the whole document's
    # fonts.ready, including unused stalled fonts. Capture the validated region
    # through Chromium only after applying system fonts and stabilizing layout.
    await result.scroll_into_view_if_needed(timeout=timeout_ms)
    await result.evaluate("""e => {
        const style=document.createElement('style');
        style.textContent='[data-alice-font-fallback], [data-alice-font-fallback] * {'+
            'animation:none!important;transition:none!important}';
        document.head.append(style);
        return new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }""")
    box = await result.bounding_box()
    if not box or box['width'] <= 0 or box['height'] <= 0:
        raise SoloUnavailable('推荐截图区域不可见，已停止截图。')
    scroll = await page.evaluate('({x:scrollX,y:scrollY})')
    session = await page.context.new_cdp_session(page)
    try:
        shot = await asyncio.wait_for(session.send('Page.captureScreenshot', {
            'format': 'png', 'fromSurface': True, 'captureBeyondViewport': True,
            'clip': {'x':box['x']+scroll['x'], 'y':box['y']+scroll['y'],
                     'width':box['width'], 'height':box['height'], 'scale':1}
        }), timeout=timeout_ms/1000)
        return base64.b64decode(shot['data'], validate=True)
    finally:
        await session.detach()
