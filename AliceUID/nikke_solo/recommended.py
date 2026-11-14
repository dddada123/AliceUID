"""Resolve public recommended SOLO settings, then apply through the site's own UI."""
import re
from datetime import date
from urllib.parse import urlencode, urlsplit, parse_qs
from .selection import BY_CODE
from .site import fingerprint

CODE = re.compile(r'[A-Za-z0-9_-]{4,16}')


def recommendation_label(item):
    labels = item.get('labels')
    labels = labels if isinstance(labels, dict) else {}
    value = labels.get('zh-cn') or labels.get('zh') or item.get('label') or item['code']
    return str(value)[:240]


def updated_date(item):
    labels = item.get('labels')
    texts = [item.get('label', ''), *(labels.values() if isinstance(labels, dict) else [])]
    dates = set()
    for text in texts:
        if isinstance(text, str):
            for match in re.finditer(r'(?<!\d)(20\d{2})[-./](\d{1,2})[-./](\d{1,2})(?!\d)', text):
                try: dates.add(date(*map(int, match.groups())))
                except ValueError: raise ValueError('网站推荐设置日期无效') from None
    if len(dates) > 1:
        raise ValueError('网站推荐设置日期不一致')
    return next(iter(dates), None)


async def fetch_recommendation(weakness, fetch):
    listing = await fetch('/api/boss/rec')
    items = listing.get('solo')
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError('网站单人突袭推荐设置列表异常')
    seen, matches = set(), []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('code'), str) or not CODE.fullmatch(item['code']):
            raise ValueError('网站推荐设置代码异常')
        code = item['code']
        if code in seen:
            raise ValueError('网站推荐设置代码重复，无法唯一确认')
        seen.add(code)
        payload = await fetch('/api/boss?' + urlencode({'c': code}))
        if (payload.get('mode') != 'solo' or 'rows' in payload or payload.get('kind') == 'season_bosses'
                or not isinstance(payload.get('battle'), dict) or not payload['battle']
                or payload.get('code') not in BY_CODE or type(payload.get('duration')) is not int
                or not 1 <= payload['duration'] <= 3600):
            raise ValueError('网站推荐设置并非有效单人突袭配置')
        if payload['code'] == weakness:
            matches.append((item, payload))
    if not matches:
        return None
    if len(matches) > 1:
        dated = [(updated_date(item), item, payload) for item, payload in matches]
        if any(stamp is None for stamp, _, _ in dated):
            raise ValueError('该属性有多份推荐设置，无法确认最新一份')
        latest = max(row[0] for row in dated)
        matches = [(item, payload) for stamp, item, payload in dated if stamp == latest]
        if len(matches) != 1:
            raise ValueError('该属性最新推荐设置不唯一')
    item, payload = matches[0]
    label = recommendation_label(item)
    return dict(code=item['code'], weakness=weakness, duration=payload['duration'], label=label,
                payload_fingerprint=fingerprint(payload),
                fingerprint=fingerprint([item['code'], label, payload]))


async def browser_fetch(page, path):
    response = await page.evaluate("""async path => {
        const r=await fetch(path,{cache:'no-store'});return {status:r.status,data:await r.json()};
    }""", path)
    if response['status'] != 200 or not isinstance(response['data'], dict) or response['data'].get('error'):
        raise ValueError('网站推荐设置暂不可用')
    return response['data']


async def verify_applied(page, recommendation):
    if recommendation is None:
        return
    valid = await page.evaluate("""expected => {
        const settings=JSON.parse(localStorage.getItem('nikke.settings.v2')||'{}');
        const selected=document.querySelector('#code')?.value;
        const saved=settings.soloRec;
        return selected===expected.weakness && settings.code===expected.weakness
            && Number(settings.duration)===expected.duration && saved?.code===expected.code
            && typeof saved.sig==='string' && saved.sig.length>0
            && !!document.querySelector('#bt-rec.is-using');
    }""", recommendation)
    if not valid:
        raise ValueError('网站推荐设置未成功套用或计算设置已发生变化，本次停止计算')


async def apply_recommendation(page, recommendation, *, timeout=90_000):
    if recommendation is None:
        return
    # Only these native controls open the recommended-settings preview. No label guessing.
    triggers = ['.rec-new .btn-primary', '#boss-rec-solo', '#bt-rec .bt-rec-go']
    await page.wait_for_function("""() => ['.rec-new .btn-primary','#boss-rec-solo','#bt-rec .bt-rec-go']
        .some(selector=>{const e=document.querySelector(selector);return e && e.getBoundingClientRect().width>0
            && e.getBoundingClientRect().height>0 && getComputedStyle(e).visibility!=='hidden'})
        || !!document.querySelector('#bt-rec.is-using')""", timeout=timeout)
    trigger = None
    for selector in triggers:
        candidate = page.locator(selector)
        if await candidate.count() == 1 and await candidate.is_visible():
            trigger = candidate
            break
    if trigger is None:
        # It can already be applied, but a dismissed notice alone is insufficient.
        await verify_applied(page, recommendation)
        return

    def matches(response):
        url = urlsplit(response.url)
        return url.path == '/api/boss' and parse_qs(url.query).get('c') == [recommendation['code']]

    async with page.expect_response(matches, timeout=timeout) as received:
        await trigger.click()
        await page.wait_for_function("""() => document.querySelector('#bosslink-sheet')?.open
            || document.querySelector('#brecpick-sheet')?.open""", timeout=timeout)
        picker = page.locator('#brecpick-sheet[open]')
        if await picker.count():
            rows = picker.locator('.preset-line')
            texts = await rows.locator('.prof-meta').all_text_contents()
            indices = [i for i, text in enumerate(texts) if text.strip() == recommendation['code']]
            if len(indices) != 1:
                raise ValueError('网站推荐设置选项已变化，无法唯一选择最新设置')
            await rows.nth(indices[0]).locator('button').click()
        await page.locator('#bosslink-sheet[open]').wait_for(state='visible', timeout=timeout)
    response = await received.value
    if response.status != 200 or fingerprint(await response.json()) != recommendation['payload_fingerprint']:
        raise ValueError('网站推荐设置在套用期间已更新，请重新查询')
    shown = await page.locator('#bosslink-code .rec-code').text_content()
    if shown != recommendation['code']:
        raise ValueError('网站推荐设置预览代码不一致，本次停止计算')
    # Applying a configuration does not require opting into rank contribution.
    consent = page.locator('#bosslink-rank-on')
    if await consent.count():
        await consent.uncheck()
    await page.locator('#bosslink-ok').click()
    await page.wait_for_function("() => !document.querySelector('#bosslink-sheet')?.open", timeout=timeout)
    await verify_applied(page, recommendation)
