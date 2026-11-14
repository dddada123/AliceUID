"""Owned official lookup; isolated, credential-free DILDORO browser capture."""
from __future__ import annotations
import asyncio
import base64
import io
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit
from PIL import Image
from .selection import BY_CODE, ELEMENTS, label as element_label
from .site import choose, source_fingerprint, metadata, status_notes, resolve, automatic_code

SITE = 'https://dildoro.com/'
NOTICE = ('【实验性功能】正在从 https://dildoro.com/ 查询信息，请稍后，'
          '更为详细的计算请直接访问该网站。')
SERVERS = {81: ('JP', '日本'), 82: ('NA', '北美'), 83: ('KR', '韩国'),
           84: ('GLOBAL', '全球'), 85: ('SEA', '东南亚'), 91: ('TW-HK', '台湾·香港')}
SERVER_LABELS = {
    'JP': ('日本', 'Japan', '일본'),
    'NA': ('北美', 'North America', '북미'),
    'KR': ('韩国', '韓國', 'Korea', '한국'),
    'GLOBAL': ('全球服', '全球', 'Global', '글로벌'),
    'SEA': ('东南亚', '東南亞', 'SEA', '동남아'),
    'TW-HK': ('台港澳', '台湾·香港', '台灣·香港', '台湾・香港', 'Taiwan', '대만·홍콩'),
}
_CAPTURE = asyncio.Semaphore(1)
_TOTAL_TIMEOUT = 600
_PAGE_TIMEOUT_MS = 90_000
_NETWORK_TIMEOUT_MS = 20_000
from ..nikke_browser.runtime import diagnostic, page_reason

from .errors import SoloUnavailable, SoloTransient
from .resilience import run_with_idle_timeout, IDLE_SECONDS
from .loading import BrowserRecovery, LoadMonitor, prepare_visuals, capture_visual, wait_until


def _server_button(text):
    """Separate the site's trailing selection mark from its exact label."""
    text = text.strip()
    checked = text.endswith('✓')
    return (text[:-1].strip() if checked else text), checked


async def _select_server(card, server):
    buttons = card.locator('.lab-srv button')
    texts = await buttons.all_inner_texts()
    matches = [i for i, text in enumerate(texts)
               if _server_button(text)[0] in SERVER_LABELS[server]]

    def detail(values):
        # Only public button labels belong in this diagnostic, never page state.
        labels = [' '.join(value.split())[:80] for value in values[:20]]
        return '、'.join(labels) or '（无）'

    expected = SERVER_LABELS[server][0]
    if len(matches) != 1:
        raise SoloUnavailable(
            f'DILDORO服务器选项已变化：目标{expected}（{server}），'
            f'当前按钮：{detail(texts)}。未自动改选其他服。')
    await buttons.nth(matches[0]).click()
    selected = await buttons.all_inner_texts()
    checked = [label for text in selected
               for label, marked in [_server_button(text)] if marked]
    if len(checked) != 1 or checked[0] not in SERVER_LABELS[server]:
        raise SoloUnavailable(
            f'DILDORO服务器选择未确认：目标{expected}（{server}），'
            f'当前按钮：{detail(selected)}。本次停止计算。')


@dataclass(frozen=True)
class SoloAccount:
    url: str
    share_openid: str
    area: int
    icon_id: int | str | None = None

@dataclass(frozen=True)
class SoloImage:
    png: bytes
    weakness: str
    captured_at: float
    rank_season: str = ''
    notes: tuple[str, ...] = ()
    site: dict = field(default_factory=dict)
    presentation: dict = field(default_factory=dict)

async def owned_account(client, bind):
    expected = (str(bind.game_id), str(bind.intl_open_id), int(bind.area_id))
    actual = (str(client.region.game_id), str(client.credentials.openid), int(client.region.area_id))
    if expected != actual or actual[2] not in SERVERS:
        raise SoloUnavailable('本人绑定或服务器已变化，请重新查询。')
    role = await client.get_saved_role_info()
    if str(role.get('area_id', '')) != str(actual[2]):
        raise SoloUnavailable('blablalink当前角色服务器与AliceUID绑定不一致，请先在官网核对。')
    data = await client._request('POST', '/api/ugc/proxy/standalonesite/User/GetUserInfoNew', {})
    full = str(((data.get('data') or {}).get('info') or {}).get('intl_openid') or '')
    match = re.fullmatch(r'(29080|29157)-(\d{9,30})', full)
    if not match or match[1] != actual[0]:
        raise SoloUnavailable('未取得可核验的本人分享标识，请稍后重试。')
    # Authenticated self endpoint owns this share ID; it need not equal the login ID.
    encoded = base64.b64encode(full.encode()).decode('ascii')
    return SoloAccount('https://www.blablalink.com/user?' + urlencode({'openid': encoded}), match[2], actual[2], role.get('icon'))

def validate_png(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 16 * 1024 * 1024:
        raise SoloUnavailable('推荐截图大小异常，本次未发送。')
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'PNG' or not (400 <= im.width <= 2400 and 300 <= im.height <= 6000) or im.width * im.height > 16_000_000:
            raise SoloUnavailable('推荐截图尺寸异常，本次未发送。')
        im.verify()

# Storage schema checked against public app.js; only account selectors are read.
PROFILES = """() => Object.values(JSON.parse(localStorage.getItem('nikke.profiles.v1') || '{}')).map(p =>
    ({id:p.id, openid:String(p.openid), area:Number(p.area), count:Object.keys(p.fetched?.chars||{}).length,
      fetched_at:p.fetched?._meta?.fetched_at||p.fetched_at||"", notices:p.notices||[]}))"""

async def capture_page(page, account, *, mode='default', idle_seconds=IDLE_SECONDS, recovery=None):
    from playwright.async_api import Error, TimeoutError as BrowserTimeout
    stage = ['页面访问']
    heartbeat = [time.monotonic(), stage[0]]
    recovery = recovery if recovery is not None else BrowserRecovery()
    monitor = LoadMonitor(page, heartbeat)
    def progress(value):
        stage[0] = value
        heartbeat[:] = [time.monotonic(), value]
        diagnostic('DILDORO', value)
    try:
        await monitor.start()
        await page.expose_function('__aliceSoloHeartbeat', lambda: heartbeat.__setitem__(0,time.monotonic()))
        await page.add_init_script(r"""(() => {
            const Original=window.EventSource;if(typeof Original!=='function')return;
            window.EventSource=class extends Original {constructor(url,options){super(url,options);
                const target=new URL(url,location.href);
                if(target.origin===location.origin && /^\/api\/(fetch|sim|sim-heavy)\/events$/.test(target.pathname))
                    this.addEventListener('message',()=>window.__aliceSoloHeartbeat().catch(()=>{}));
            }};
        })();""")
        return await run_with_idle_timeout(monitor.run(_capture_page(page, account, progress, mode=mode,
                                                                     language=recovery.language)), heartbeat, timeout=idle_seconds)
    except SoloTransient as exc:
        # A pending translation alone is enough evidence to try the website's
        # native language next round. Never bypass an unrelated core failure.
        if exc.reason == 'IDLE_TIMEOUT' and monitor.translations and monitor.critical <= monitor.translations:
            exc.reason = 'I18N_STALLED'
        if exc.reason in {'I18N_FAILED', 'I18N_STALLED'}:
            recovery.native_language = True
        diagnostic('DILDORO',stage[0],exc.reason or 'NETWORK')
        from ..nikke_logs.store import record_failure
        record_failure('DILDORO',stage[0],exc)
        raise
    except SoloUnavailable as exc:
        diagnostic('DILDORO', stage[0], 'VALIDATION_FAILED')
        from ..nikke_logs.store import record_failure
        record_failure('DILDORO', stage[0], exc)
        raise
    except BrowserTimeout as exc:
        from ..nikke_logs.store import record_failure
        record_failure('DILDORO', stage[0], exc)
        diagnostic('DILDORO', stage[0], 'TIMEOUT')
        if monitor.translations and monitor.critical <= monitor.translations:
            recovery.native_language = True
            raise SoloTransient('网站中文翻译资源尚未就绪。',stage=stage[0],reason='I18N_STALLED') from None
        if stage[0] in {'页面初始化','本人计算账号选择'} and not monitor.critical:
            raise SoloUnavailable(f'DILDORO{stage[0]}未完成，可能是页面结构变化或目标账号选项缺失。') from None
        raise SoloTransient(f'DILDORO{stage[0]}超时。',stage=stage[0],reason='TIMEOUT') from None
    except Error as exc:
        from ..nikke_logs.store import record_failure
        record_failure('DILDORO', stage[0], exc)
        reason = page_reason(str(exc))
        diagnostic('DILDORO', stage[0], reason)
        error = SoloTransient if reason in {'ERR_NAME_NOT_RESOLVED','ERR_PROXY_CONNECTION_FAILED','ERR_TUNNEL_CONNECTION_FAILED','ERR_CONNECTION_RESET','ERR_CONNECTION_TIMED_OUT','ERR_CONNECTION_CLOSED','ERR_NETWORK_CHANGED'} else SoloUnavailable
        if error is SoloTransient:
            raise error(f'DILDORO{stage[0]}失败（{reason}）。',stage=stage[0],reason=reason) from None
        raise error(f'DILDORO{stage[0]}失败（{reason}）。') from None

    except Exception as exc:
        from ..nikke_logs.store import record_failure
        record_failure('DILDORO', stage[0], exc)
        raise
    finally:
        await monitor.close()


async def read_default(page):
    """Read settled native controls in a fresh context before any override."""
    await page.locator('#mode-solo').wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    if await page.locator('#mode-solo').get_attribute('aria-pressed') != 'true':
        await page.locator('#mode-solo').click()
    await wait_until(page, """() => document.querySelector('#mode-solo')?.getAttribute('aria-pressed')==='true'
        && document.querySelector('#code')?.options.length >= 5
        && !!document.querySelector('#code')?.value""", timeout=_PAGE_TIMEOUT_MS)
    code = await page.locator('#code').input_value()
    if code not in BY_CODE:
        raise SoloUnavailable('DILDORO网站默认属性尚未就绪或选项已变化。')
    return code

async def _capture_page(page, account, progress, *, mode='default', language='zh-CN'):
    progress('页面访问')
    response = await page.goto(SITE + 'account?lang=' + language, wait_until='domcontentloaded', timeout=_PAGE_TIMEOUT_MS)
    if response is not None and (response.status == 408 or response.status >= 500):
        raise SoloTransient('DILDORO账号页面暂时无响应。',stage='页面访问',reason='HTTP_SERVER')
    if response is None or response.status != 200 or not page.url.startswith(SITE):
        raise SoloUnavailable('DILDORO账号页面暂不可用，请稍后直接访问网站。')
    # Notices can open after the initial visibility check. Let Playwright dismiss
    # them before any action instead of timing out on an intercepted pointer.
    page.set_default_timeout(_PAGE_TIMEOUT_MS)
    async def close_history():
        await page.locator('#history-x').click()
    async def skip_coach():
        await page.locator('.coach-skip').click()
    await page.add_locator_handler(page.locator('#history-sheet[open]'), close_history)
    await page.add_locator_handler(page.locator('.coach-skip'), skip_coach)
    progress('页面初始化')
    # Wait for boot and event wiring, not merely server-rendered buttons.
    await page.locator('#sync-fold').wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    await page.locator('#sync-fold').evaluate('(e)=>{e.open=true}')
    # React mounts these controls before runtime/health initialization finishes.
    # Do not unhide them ourselves or mistake the initial hidden state for failure.
    await page.locator('#url-in').wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    await wait_until(page, "() => !!document.querySelector('#url-go') && !document.querySelector('#url-go').disabled", timeout=_PAGE_TIMEOUT_MS)
    progress('本人公开数据同步')
    await page.locator('#url-in').fill(account.url)
    # Each new context must submit an actual fetch job; a populated local profile is insufficient.
    async with page.expect_response(lambda r: '/api/fetch' == urlsplit(r.url).path
                                    and r.request.method == 'POST', timeout=_PAGE_TIMEOUT_MS) as sync_response:
        await page.locator('#url-go').click()
    sync_status = (await sync_response.value).status
    if sync_status == 408 or sync_status >= 500:
        raise SoloTransient('DILDORO本人数据同步服务暂时无响应。',stage='本人公开数据同步',reason='HTTP_SERVER')
    if not 200 <= sync_status < 300:
        raise SoloUnavailable('本人养成重新拉取失败，本次停止计算。')
    await wait_until(page, "() => !document.querySelector('#url-go')?.disabled", timeout=180000)
    profiles = await page.evaluate(PROFILES)
    matches = [p for p in profiles if p.get('openid') == account.share_openid and p.get('area') == account.area and p.get('count', 0) > 0]
    if len(matches) != 1:
        raise SoloUnavailable('账号同步未完成或目标区服未导入。请确认blablalink个人档案和妮姬列表公开，或直接访问DILDORO导入本人数据。')
    imported_at = matches[0].get('fetched_at')
    if imported_at:
        from datetime import datetime
        try:
            stamp = datetime.fromisoformat(imported_at.replace('Z', '+00:00'))
            if stamp.tzinfo is None or not -60 <= time.time() - stamp.timestamp() <= 600:
                raise ValueError('stale')
        except (AttributeError, TypeError, ValueError):
            raise SoloUnavailable('网站返回的本人养成采集时间过旧或无法核验，本次停止计算，请稍后重新同步。') from None
    progress('本人计算账号选择')
    # Grid mode intentionally hides the account selector. Select on the normal
    # deck first, then enter grid through the site's toggle to retain active state.
    response = await page.goto(SITE + 'deck?lang=' + language, wait_until='domcontentloaded', timeout=_PAGE_TIMEOUT_MS)
    if response is not None and (response.status == 408 or response.status >= 500):
        raise SoloTransient('DILDORO账号选择页面暂时无响应。',stage='本人计算账号选择',reason='HTTP_SERVER')
    if response is None or response.status != 200 or not page.url.startswith(SITE):
        raise SoloUnavailable('DILDORO编队配置页面暂不可用。')
    await page.locator('#profile-pick').wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    await wait_until(page, """id =>
        [...(document.querySelector('#profile-pick')?.options||[])].some(o=>o.value===id)
        && document.querySelector('#code')?.options.length>=5""", arg=matches[0]['id'], timeout=_PAGE_TIMEOUT_MS)
    await page.locator('#profile-pick').select_option(matches[0]['id'], timeout=_PAGE_TIMEOUT_MS)
    await wait_until(page, '(id)=>document.querySelector("#profile-pick")?.value===id', arg=matches[0]['id'], timeout=_PAGE_TIMEOUT_MS)
    native_code = await read_default(page)
    listing_response = await page.evaluate("""async () => {const r=await fetch('/api/sr-rank/list',{cache:'no-store'});return {status:r.status, data:await r.json()}}""")
    if listing_response['status'] == 408 or listing_response['status'] >= 500:
        raise SoloTransient('DILDORO排行信息暂时无响应。',stage='本人计算账号选择',reason='HTTP_SERVER')
    if listing_response['status'] != 200:
        raise SoloUnavailable('DILDORO赛季信息暂不可用。')
    initial_listing = listing_response['data']
    server, _ = SERVERS[account.area]
    try:
        weakness, expected_season = resolve(initial_listing, mode, server)
        default_code = automatic_code(initial_listing)
    except ValueError as exc:
        if mode == 'default':
            raise SoloUnavailable(str(exc)) from None
        try:
            weakness, expected_season = resolve(initial_listing, mode, server)
        except ValueError as error:
            raise SoloUnavailable(str(error)) from None
        default_code = None
    # Always trigger the site's native change event, including automatic mode.
    await page.locator('#code').select_option(weakness)
    await wait_until(page, '(code)=>document.querySelector("#code")?.value===code', arg=weakness, timeout=_PAGE_TIMEOUT_MS)
    progress('推荐设置套用')
    from .recommended import fetch_recommendation, browser_fetch, apply_recommendation, verify_applied, RecommendationUnavailable
    recommendation_status = 'none'
    available_recommendation = None
    try:
        available_recommendation = await fetch_recommendation(weakness, lambda path: browser_fetch(page, path))
        applied = await apply_recommendation(page, available_recommendation, timeout=_PAGE_TIMEOUT_MS)
        recommendation = available_recommendation if applied else None
        recommendation_status = 'applied' if applied else ('no-import-control' if available_recommendation else 'none')
    except RecommendationUnavailable:
        recommendation = None
        recommendation_status = 'unavailable'
    except ValueError as exc:
        raise SoloUnavailable(str(exc)) from None
    progress('配置模式切换')
    if not await page.locator('#fast-wrap').is_visible():
        await page.locator('#fast-toggle').click()
    await page.locator('#fast-wrap').wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    # Verification reads the hidden selector; it never forces a hidden control.
    await wait_until(page, '(id)=>document.querySelector("#profile-pick")?.value===id', arg=matches[0]['id'], timeout=_PAGE_TIMEOUT_MS)
    profiles = await page.evaluate(PROFILES)
    if not any(p.get('id') == matches[0]['id'] and p.get('openid') == account.share_openid and p.get('area') == account.area and p.get('count', 0) > 0 for p in profiles):
        raise SoloUnavailable('进入配置模式后本人账号校验失败，本次停止计算。')
    if await page.locator('#code').input_value() != weakness:
        raise SoloUnavailable('进入配置模式后网站属性发生变化，本次停止计算，请重新查询。')
    try:
        await verify_applied(page, recommendation)
    except ValueError as exc:
        raise SoloUnavailable(str(exc)) from None
    progress('排行推荐加载')
    # Fresh account: a single empty set; recommendation adds the second set.
    server, _ = SERVERS[account.area]
    async with page.expect_response(lambda r: '/api/sr-rank/list' in r.url, timeout=_PAGE_TIMEOUT_MS) as ranks:
        await page.locator('#fast-rank').click()
    listing = await (await ranks.value).json()
    try:
        confirmed_code, season = resolve(listing, mode, server)
        if confirmed_code != weakness or season['raid'] != expected_season['raid']:
            raise ValueError('网站赛季在计算期间发生变化，请重新查询。')
    except ValueError as exc:
        raise SoloUnavailable(str(exc)) from None
    card = page.locator('#lab-sheet .lab-card[data-kind="draft-rank"]')
    await card.wait_for(state='visible', timeout=_PAGE_TIMEOUT_MS)
    # Translate exact public labels; require one selection and disallow fallback.
    await _select_server(card, server)
    go = card.locator('[data-role="go"]')
    if not await go.is_enabled():
        raise SoloUnavailable('当前账号不满足推荐条件，请直接访问DILDORO查看详情。')
    # Verify fetched ranking sets as well: the website otherwise silently falls back.
    rank_errors = []
    actual_source = []
    actual_fetched = []
    async def guard_sets(route):
        try:
            upstream = await route.fetch(timeout=_NETWORK_TIMEOUT_MS)
            upstream_status = getattr(upstream,'status',200)
            if upstream_status != 200:
                rank_errors.append('HTTP_' + str(upstream_status))
                await route.fulfill(status=upstream_status,content_type='application/json',body='{"error":"ranking upstream unavailable"}')
                return
            payload = await upstream.json()
            if server not in payload.get('servers', []):
                await route.fulfill(status=409, content_type='application/json', body='{"error":"AliceUID: selected server unavailable"}')
            else:
                try:
                    source = source_fingerprint(payload, season, server)
                except ValueError:
                    rank_errors.append('SEASON_MISMATCH')
                    await route.fulfill(status=409, content_type='application/json', body='{"error":"AliceUID: ranking season mismatch"}')
                    return
                actual_source.append(source)
                actual_fetched.append(str(payload.get('fetched_at') or season.get('fetched_at') or ''))
                await route.fulfill(response=upstream)
        except Exception as exc:
            from playwright.async_api import TimeoutError as BrowserTimeout
            from ..nikke_logs.store import record_failure
            reason = 'TIMEOUT' if isinstance(exc, BrowserTimeout) else page_reason(str(exc))
            rank_errors.append(reason)
            record_failure('DILDORO', '排行数据请求', exc)
            # Finish the intercepted request so the website can stop its loading UI.
            await route.fulfill(status=502, content_type='application/json', body='{"error":"AliceUID: ranking fetch failed"}')
    await page.route('**/api/sr-rank/sets?*', guard_sets)
    progress('推荐计算')
    try:
        await verify_applied(page, recommendation)
    except ValueError as exc:
        raise SoloUnavailable(str(exc)) from None
    await go.click()
    await wait_until(page, """() => !document.querySelector('#lab-sheet')?.open ||
        !!document.querySelector('#lab-sheet .lab-out .warn')""", timeout=300000)
    if rank_errors:
        error = SoloTransient if rank_errors[0] == 'TIMEOUT' or rank_errors[0].startswith(('ERR_','HTTP_5')) or rank_errors[0] == 'HTTP_408' else SoloUnavailable
        if error is SoloTransient:
            raise error(f'DILDORO排行数据请求失败（{rank_errors[0]}）。',stage='排行推荐加载',reason=rank_errors[0])
        raise error(f'DILDORO排行数据请求失败（{rank_errors[0]}），请稍后重试。')
    if len(actual_source) != 1:
        raise SoloUnavailable('DILDORO实际阵容来源未唯一确认，本次未发送。')
    if await page.locator('#lab-sheet').get_attribute('open') is not None:
        raise SoloUnavailable('DILDORO未能完成推荐，可能没有完整适用队伍或计算服务繁忙，请直接访问网站查看。')
    sets = page.locator('#fast-grid > .fg-set')
    if await sets.count() == 2:
        result = sets.nth(1)
    else:
        # New frontend stores rank recommendations in a named slot rather than a second set.
        active = page.locator('#slot-sw .slot-chip.on .slot-pill')
        code = {'GLOBAL': 'GLB', 'TW-HK': 'TWHK'}.get(server, server)
        if await active.count() != 1 or not re.search(r'(?<![A-Z])' + re.escape(code) + r'(?![A-Z])', await active.inner_text()):
            raise SoloUnavailable('DILDORO排行推荐槽位或服务器未确认，本次未发送截图。')
        result = page.locator('#fast-wrap')
    if await result.locator('.fg-row').count() != 5 or await result.locator('.fg-slot.has').count() != 25:
        raise SoloUnavailable('推荐不足5队，未输出完整伤害预估，请直接访问网站查看。')
    totals = await result.locator('.fg-row-total').all_text_contents()
    if len(totals) != 5 or any(not re.search(r'\d', t) for t in totals) or await result.locator('.fg-row-total.err').count():
        raise SoloUnavailable('部分队伍伤害尚未计算完成，本次未发送。')
    try:
        await verify_applied(page, recommendation)
    except ValueError as exc:
        raise SoloUnavailable(str(exc)) from None
    progress('结果截图')
    visual_state = {}
    image = await capture_result(page, result, visual_state=visual_state)
    site = metadata(listing, default_code, weakness, mode, season, actual_source[0])
    site['fetched_at'] = actual_fetched[0]
    site['native_code'] = native_code
    site['profile_fetched_at'] = imported_at or ''
    site['recommended'] = recommendation
    site['recommended_available'] = available_recommendation
    site['recommendation_status'] = recommendation_status
    site['page_language'] = language
    site['visual_fallback'] = visual_state
    settings_note = (f'已套用网站推荐设置：{recommendation["label"]}（代码 {recommendation["code"]}）。' if recommendation
                     else ('未检测到推荐配置导入环节，已自动采用网站默认模拟配置。' if recommendation_status == 'no-import-control'
                           else '未读取到匹配的推荐配置，已自动采用网站默认模拟配置。'))
    degradation = (() if language != 'ko' else ('中文翻译加载异常，本次使用网站原生语言完成计算，截图可能包含韩文。',))
    if visual_state.get('missing_images'):
        degradation += ('部分角色图片未加载，已使用占位图；阵容与伤害数据已完成校验。',)
    if visual_state.get('font_fallback'):
        degradation += ('网站字体加载异常，已使用系统字体显示。',)
    return SoloImage(image, element_label(weakness), time.time(), str(season['raid']),
                     status_notes(site) + (settings_note,) + degradation + (() if imported_at else ('网站未报告可核验的养成采集时间；本次已重新提交链接拉取请求。',)) + ('排行阵容来自网站同弱点最近可用赛季；模拟条件采用网站当前设置。',
                      '网址导入受公开设置影响；回收室等缺失数据可能使用网站默认值。'), site)

async def capture_result(page, result, *, visual_state=None):
    """Isolate the real result at its intrinsic width, then scale all of it together.

    A 960px CSS width alone crosses the site's fixed ~600px stage into its
    sticky white roster. Hiding siblings AND retaining the original flex layout
    avoids both foreign pixels and stretched empty space.
    """
    if await result.count() != 1:
        raise SoloUnavailable('推荐截图目标不唯一，已停止截图。')
    assets = await prepare_visuals(page, result)
    if visual_state is not None:
        visual_state.update(assets)
    box = await result.bounding_box()
    if not box or not 300 <= box['width'] <= 1600:
        raise SoloUnavailable('推荐区域宽度异常，已停止截图。')
    await result.evaluate("""(e, width) => {
        let background = getComputedStyle(e).backgroundColor;
        for(let p=e; p && (!background || background==='rgba(0, 0, 0, 0)' || background==='transparent'); p=p.parentElement)
            background=getComputedStyle(p).backgroundColor;
        e.setAttribute('data-alice-solo-capture','true');
        for(let p=e.parentElement;p;p=p.parentElement){
            for(const [key,value] of Object.entries({overflow:'visible','max-height':'none',
                contain:'none','clip-path':'none',transform:'none',position:'static'}))
                p.style.setProperty(key,value,'important');
        }
        for(const [key,value] of Object.entries({width:width+'px','min-width':width+'px','max-width':width+'px',
            'box-sizing':'border-box',transform:'scale('+(960/width)+')','transform-origin':'top left',
            position:'relative',margin:'0',overflow:'visible',background:background||'#222428'}))
            e.style.setProperty(key,value,'important');
    }""", box['width'])
    await page.add_style_tag(content="""
        body * {visibility:hidden !important}
        [data-alice-solo-capture], [data-alice-solo-capture] * {visibility:visible !important}
        [data-alice-solo-capture] .fg-set-acts>button:not(.fg-set-calc){display:none!important}
    """)
    await result.evaluate('(e)=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    geometry = await result.evaluate("""e=>{
        const b=e.getBoundingClientRect();
        const inside=n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&
            r.left>=b.left-1&&r.top>=b.top-1&&r.right<=b.right+1&&r.bottom<=b.bottom+1};
        const cells=[...e.querySelectorAll('.fg-slot.has')],rows=[...e.querySelectorAll('.fg-row')],totals=[...e.querySelectorAll('.fg-row-total')];
        return {width:b.width,height:b.height,ok:cells.length===25&&rows.length===5&&totals.length===5&&
            [...cells,...rows,...totals,...e.querySelectorAll('.fg-set-head, .nk-dmg, .nk-art img, .fast-total-val')].every(inside)};
    }""")
    if not geometry['ok'] or abs(geometry['width']-960)>2 or not 200<=geometry['height']<=4000:
        raise SoloUnavailable('推荐区域内容超出截图边界，已停止发送，请稍后重试。')
    image = await capture_visual(page, result, font_fallback=assets['font_fallback'], timeout_ms=_PAGE_TIMEOUT_MS)
    validate_png(image)
    return image

async def capture(account, *, channel='auto', mode='default', recovery=None):
    from ..nikke_browser.runtime import manager, playwright as browser_playwright
    async with _CAPTURE:
        async with browser_playwright(error_type=SoloUnavailable, operation="个人突袭") as p:
            diagnostic('DILDORO', '浏览器启动')
            try:
                browser = await asyncio.wait_for(manager.launch(p, channel=channel, headless=True), 120)
            except asyncio.TimeoutError:
                raise SoloUnavailable('浏览器组件仍在准备，请稍后重试个人突袭推荐。') from None
            try:
                async def run():
                    context = await browser.new_context(viewport={'width':1600,'height':1200},device_scale_factor=1.5,
                                                        locale='zh-CN',timezone_id='Asia/Shanghai',service_workers='block')
                    try:
                        return await capture_page(await context.new_page(), account, mode=mode, recovery=recovery)
                    finally:
                        await context.close()
                try:
                    return await asyncio.wait_for(run(), timeout=_TOTAL_TIMEOUT)
                except asyncio.TimeoutError:
                    raise SoloUnavailable('DILDORO导入或计算超时，请稍后重试或直接访问网站。') from None
            finally:
                await browser.close()

async def probe_default(*, channel='auto'):
    """Anonymous read of the default; no profile import or recommendation execution."""
    from ..nikke_browser.runtime import manager, playwright as browser_playwright
    async with _CAPTURE:
        async with browser_playwright(error_type=SoloUnavailable, operation='个人突袭属性检查') as p:
            browser = await asyncio.wait_for(manager.launch(p, channel=channel, headless=True), 120)
            try:
                async def run():
                    context = await browser.new_context(locale='zh-CN', service_workers='block')
                    try:
                        page = await context.new_page()
                        page.set_default_timeout(_PAGE_TIMEOUT_MS)
                        async def close_history():
                            await page.locator('#history-x').click()
                        async def skip_coach():
                            await page.locator('.coach-skip').click()
                        await page.add_locator_handler(page.locator('#history-sheet[open]'), close_history)
                        await page.add_locator_handler(page.locator('.coach-skip'), skip_coach)
                        response = await page.goto(SITE + 'deck?lang=zh-CN', wait_until='domcontentloaded', timeout=_PAGE_TIMEOUT_MS)
                        if response is None or response.status != 200:
                            raise SoloUnavailable('DILDORO默认属性检查暂不可用。')
                        return await read_default(page)
                    finally:
                        await context.close()
                return await asyncio.wait_for(run(), 180)
            finally:
                await browser.close()
