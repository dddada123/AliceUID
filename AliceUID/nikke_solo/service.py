"""Owned official lookup; isolated, credential-free DILDORO browser capture."""
from __future__ import annotations
import asyncio
import base64
import io
import re
import time
from dataclasses import dataclass
from urllib.parse import urlencode
from PIL import Image

SITE = 'https://dildoro.com/'
NOTICE = ('【实验性功能】正在从 https://dildoro.com/ 查询信息，请稍后，'
          '更为详细的计算请直接访问该网站。')
SERVERS = {81: ('JP', '日本'), 82: ('NA', '北美'), 83: ('KR', '韩国'),
           84: ('GLOBAL', '全球'), 85: ('SEA', '东南亚'), 91: ('TW-HK', '台湾·香港')}
_CAPTURE = asyncio.Semaphore(1)
_TOTAL_TIMEOUT = 600

class SoloUnavailable(Exception):
    pass

@dataclass(frozen=True)
class SoloAccount:
    url: str
    share_openid: str
    area: int

@dataclass(frozen=True)
class SoloImage:
    png: bytes
    weakness: str
    captured_at: float
    rank_season: str = ''
    notes: tuple[str, ...] = ()

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
    return SoloAccount('https://www.blablalink.com/shiftyspad/nikke-list?' + urlencode({'openid': encoded}), match[2], actual[2])

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
      notices:p.notices||[]}))"""

async def capture_page(page, account):
    response = await page.goto(SITE + 'account?lang=zh-CN', wait_until='domcontentloaded', timeout=45000)
    if response is None or response.status != 200 or not page.url.startswith(SITE):
        raise SoloUnavailable('DILDORO账号页面暂不可用，请稍后直接访问网站。')
    # Wait for boot and event wiring, not merely server-rendered buttons.
    await page.wait_for_function("() => typeof state !== 'undefined' && typeof HEALTH !== 'undefined' && typeof $('#url-go')?.onclick === 'function'", timeout=45000)
    coach = page.locator('.coach-skip')
    if await coach.is_visible():
        await coach.click()
    history_close = page.locator('#history-sheet[open] #history-x')
    if await history_close.is_visible():
        await history_close.click()
    await page.locator('#sync-fold').evaluate('(e)=>{e.open=true}')
    if not await page.locator('#url-in').is_visible():
        raise SoloUnavailable('DILDORO网址同步暂不可用，请直接访问网站导入本人数据。')
    await page.locator('#url-in').fill(account.url)
    await page.locator('#url-go').click()
    await page.wait_for_function("() => !document.querySelector('#url-go')?.disabled", timeout=180000)
    profiles = await page.evaluate(PROFILES)
    matches = [p for p in profiles if p.get('openid') == account.share_openid and p.get('area') == account.area and p.get('count', 0) > 0]
    if len(matches) != 1:
        raise SoloUnavailable('账号同步未完成或目标区服未导入。请确认blablalink个人档案和妮姬列表公开，或直接访问DILDORO导入本人数据。')
    # Navigate using the site's own tab, retaining this request's private storage.
    await page.locator('[data-tab="deck"]').click()
    await page.locator('#profile-pick').select_option(matches[0]['id'])
    await page.wait_for_function('(id)=>document.querySelector("#profile-pick")?.value===id', arg=matches[0]['id'])
    mode = page.locator('#mode-solo')
    if await mode.get_attribute('aria-pressed') != 'true':
        await mode.click()
    await page.wait_for_function("() => document.querySelector('#mode-solo')?.getAttribute('aria-pressed')==='true'")
    weakness = await page.locator('#code').input_value()
    label = await page.locator('#code option:checked').inner_text()
    if not weakness:
        raise SoloUnavailable('DILDORO未提供单人突袭BOSS弱点，请直接访问网站核对当期设置。')
    if not await page.locator('#fast-wrap').is_visible():
        await page.locator('#fast-toggle').click()
    await page.locator('#fast-wrap').wait_for(state='visible')
    # Fresh account: a single empty set; recommendation adds the second set.
    server, _ = SERVERS[account.area]
    async with page.expect_response(lambda r: '/api/sr-rank/list' in r.url, timeout=30000) as ranks:
        await page.locator('#fast-rank').click()
    listing = await (await ranks.value).json()
    seasons = listing.get('seasons', [])
    season = next((s for s in seasons if s.get('weakness_code') == weakness), None)
    if not season or server not in season.get('servers', []):
        raise SoloUnavailable('DILDORO暂无该弱点及本人服务器的排行推荐，请稍后再试。')
    card = page.locator('#lab-sheet .lab-card[data-kind="draft-rank"]')
    await card.wait_for(state='visible')
    # Runtime labSrvPicker translates these labels. Read exact buttons and disallow fallback.
    labels = {'JP': ('日本','Japan','일본'), 'NA': ('北美','North America','북미'),
              'KR': ('韩国','韓國','Korea','한국'), 'GLOBAL': ('全球','Global','글로벌'),
              'SEA': ('东南亚','東南亞','SEA','동남아'), 'TW-HK': ('台湾·香港','台灣·香港','台湾・香港','Taiwan','대만·홍콩')}
    buttons = card.locator('.lab-srv button')
    found = []
    for i in range(await buttons.count()):
        text = (await buttons.nth(i).inner_text()).replace(' ✓','').strip()
        if text in labels[server]:
            found.append(buttons.nth(i))
    if len(found) != 1:
        raise SoloUnavailable('DILDORO服务器选项已变化，未自动改选其他服。')
    await found[0].click()
    # Read only site state to verify the server chosen by UI, before expensive work.
    selected = await page.evaluate('() => labSrv')
    if selected != server:
        raise SoloUnavailable('DILDORO服务器选择未确认，本次停止计算。')
    go = card.locator('[data-role="go"]')
    if not await go.is_enabled():
        raise SoloUnavailable('当前账号不满足推荐条件，请直接访问DILDORO查看详情。')
    # Verify fetched ranking sets as well: the website otherwise silently falls back.
    async def guard_sets(route):
        upstream = await route.fetch()
        payload = await upstream.json()
        if server not in payload.get('servers', []):
            await route.fulfill(status=409, content_type='application/json', body='{"error":"AliceUID: selected server unavailable"}')
        else:
            await route.fulfill(response=upstream)
    await page.route('**/api/sr-rank/sets?*', guard_sets)
    await go.click()
    await page.wait_for_function("""() => !labRunning &&
        (!document.querySelector('#lab-sheet')?.open || !!document.querySelector('#lab-sheet .lab-out .warn'))""", timeout=300000)
    if await page.locator('#lab-sheet').get_attribute('open') is not None:
        raise SoloUnavailable('DILDORO未能完成推荐，可能没有完整适用队伍或计算服务繁忙，请直接访问网站查看。')
    sets = page.locator('#fast-grid > .fg-set')
    if await sets.count() != 2:
        raise SoloUnavailable('DILDORO推荐区域结构已变化，本次未发送截图。')
    result = sets.nth(1)
    if await result.locator('.fg-row').count() != 5 or await result.locator('.fg-slot.has').count() != 25:
        raise SoloUnavailable('推荐不足5队，未输出完整伤害预估，请直接访问网站查看。')
    totals = await result.locator('.fg-row-total').all_text_contents()
    if len(totals) != 5 or any(not re.search(r'\d', t) for t in totals) or await result.locator('.fg-row-total.err').count():
        raise SoloUnavailable('部分队伍伤害尚未计算完成，本次未发送。')
    image = await capture_result(page, result)
    return SoloImage(image, label, time.time(), str(season.get('raid','')),
                     ('排行阵容来自网站同弱点最近可用赛季；模拟条件采用网站当前默认设置。',
                      '网址导入受公开设置影响；回收室等缺失数据可能使用网站默认值。'))

async def capture_result(page, result):
    """Isolate the real result at its intrinsic width, then scale all of it together.

    A 960px CSS width alone crosses the site's fixed ~600px stage into its
    sticky white roster. Hiding siblings AND retaining the original flex layout
    avoids both foreign pixels and stretched empty space.
    """
    if await result.count() != 1:
        raise SoloUnavailable('推荐截图目标不唯一，已停止截图。')
    await result.locator('img').evaluate_all('(xs)=>xs.forEach(i=>i.loading="eager")')
    await page.evaluate('document.fonts.ready')
    await result.evaluate("""async e => {
        const images=[...e.querySelectorAll('img')];
        await Promise.all(images.map(i=>i.decode()));
    }""")
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
    image = await result.screenshot(type='png', animations='disabled',timeout=30000)
    validate_png(image)
    return image

async def capture(account, *, channel='auto'):
    from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
    try:
        async with _CAPTURE:
            async def run():
                async with async_playwright() as p:
                    browser = None
                    choices = [None, 'msedge'] if channel == 'auto' else [None if channel=='chromium' else 'msedge']
                    for choice in choices:
                        try:
                            browser = await p.chromium.launch(headless=True, channel=choice)
                            break
                        except Exception:
                            if choice == choices[-1]:
                                raise SoloUnavailable('截图浏览器不可用，请管理员检查Playwright浏览器安装。') from None
                    try:
                        context = await browser.new_context(viewport={'width':1600,'height':1200},device_scale_factor=1.5,
                                                            locale='zh-CN',timezone_id='Asia/Shanghai',service_workers='block')
                        try:
                            return await capture_page(await context.new_page(), account)
                        finally:
                            await context.close()
                    finally:
                        await browser.close()
            return await asyncio.wait_for(run(), timeout=_TOTAL_TIMEOUT)
    except (asyncio.TimeoutError, BrowserTimeout):
        raise SoloUnavailable('DILDORO导入或计算超时，请稍后重试或直接访问网站。') from None
