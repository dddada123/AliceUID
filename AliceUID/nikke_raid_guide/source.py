"""Anonymous public list and real webpage capture; no account client or storage."""
from __future__ import annotations

import asyncio
import io
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
from PIL import Image

AUTHOR = '29080-6355534029721844438'
AUTHOR_NAME = '在舒恩裡面卍解【Syuen】'
AUTHOR_URL = 'https://www.blablalink.com/user?openid=MjkwODAtNjM1NTUzNDAyOTcyMTg0NDQzOA=='
POST_URL = 'https://www.blablalink.com/post/detail?post_uuid='
LIST_URL = 'https://api.blablalink.com/api/ugc/direct/standalonesite/Dynamics/GetUserPostList'
TTL = 3 * 86400
MAX_BYTES = 8 * 1024 * 1024


class GuideUnavailable(Exception):
    pass


class GuidePending(GuideUnavailable):
    pass


def image_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname != 'sg-cdn.blablalink.com'
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.path.startswith('/standalonesite/ugc/public/image/')):
        raise GuideUnavailable('攻略图片来源异常。')
    return value


class ExampleParser(HTMLParser):
    """Only the first image after a standalone heading, before another text block."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ''
        self.waiting = False
        self.result = None

    def handle_starttag(self, tag, attrs):
        if tag == 'img' and self.waiting and self.result is None:
            self.result = image_url(dict(attrs).get('src', ''))
            self.waiting = False

    def handle_data(self, data):
        self.text += data

    def handle_endtag(self, tag):
        if tag in ('div', 'p', 'h1', 'h2', 'h3', 'h4'):
            text = re.sub(r'\s+', '', self.text)
            if text:
                self.waiting = text in ('組隊示例', '组队示例')
            self.text = ''


def example_image(content):
    parser = ExampleParser()
    parser.feed(content)
    if not parser.result:
        raise GuideUnavailable('本期帖子尚未提供「組隊示例」图片，请稍后再试。')
    return parser.result


def matches(post, season, now):
    try:
        if post.get('intl_openid') != AUTHOR or post.get('user', {}).get('intl_openid') != AUTHOR:
            return False
        title = post['title']
        if not re.search(r'(?:联|聯)盟(?:战|戰|突袭|突襲)|[公工](?:会|會)(?:战|戰)', title):
            return False
        published = int(post['created_on'])
        if not 0 < published <= now or not re.fullmatch(r'\d{1,30}', str(post['post_uuid'])):
            return False
        tz = timezone(timedelta(hours=8))
        pubdate = datetime.fromtimestamp(published, tz)
        date = re.search(r'(?<!\d)(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?', title)
        if not date:
            return False
        # Resolve the title's year against publication time, not the current month.
        dates = []
        for year in (pubdate.year-1, pubdate.year, pubdate.year+1):
            try:
                dates.append(datetime(year, int(date[1]), int(date[2] or 1), tzinfo=tz))
            except ValueError:
                pass
        if not dates:
            return False
        title_date = min(dates, key=lambda d: abs(d.timestamp()-published)).timestamp()
        if abs(title_date-published) > 45*86400 or title_date > now+86400:
            return False
        # Allow delayed Hard guides and timezone differences within this raid window.
        return (season['start_ts']-86400 <= published <= min(now, season['end_ts']+86400)
                and (not date[2] or season['start_ts']-86400 <= title_date <= season['end_ts']+86400)
                and (date[2] or int(date[1]) in {
                    datetime.fromtimestamp(season['start_ts'],tz).month,
                    datetime.fromtimestamp(season['end_ts'],tz).month}))
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        return False



async def find_post(season, now):
    headers = {'Origin': 'https://www.blablalink.com', 'Referer': AUTHOR_URL,
               'x-language': 'zh-tw', 'x-channel-type': '2'}
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, headers=headers) as client:
        cursor, seen, candidates = '', set(), []
        for _ in range(12):
            body = dict(plate_id=0, order_by=1, limit='10', intl_openid=AUTHOR, page_type=0)
            if cursor:
                body['next_page_cursor'] = cursor
            response = await client.post(LIST_URL, json=body)
            response.raise_for_status()
            if len(response.content) > 4 * 1024 * 1024:
                raise GuideUnavailable('作者帖子列表超出读取限制。')
            payload = response.json()
            if payload.get('code') != 0:
                raise GuideUnavailable('作者主页暂不可用，请稍后再试。')
            data = payload.get('data', {})
            rows, info = data.get('list'), data.get('page_info', {})
            if not isinstance(rows, list) or not isinstance(info, dict):
                raise GuideUnavailable('作者主页结构已变化。')
            candidates.extend(p for p in rows if matches(p, season, now))
            cursor = info.get('next_page_cursor')
            if not rows or info.get('is_finish') or not cursor or cursor in seen:
                break
            seen.add(cursor)
            await asyncio.sleep(0.25)
    for post in sorted(candidates, key=lambda p: int(p['created_on']), reverse=True):
        try:
            example_image(post.get('content', ''))
            return post
        except GuideUnavailable:
            continue
    raise GuidePending('暂未找到本期会战攻略，攻略作者可能还在编写或整理中，请稍后再查询。')


def validate_image(data, *, screenshot=False):
    if not data or len(data) > MAX_BYTES:
        raise GuideUnavailable('攻略图片超出发送限制，未发送不完整图片。')
    with Image.open(io.BytesIO(data)) as im:
        if (im.format not in ('JPEG', 'PNG', 'WEBP') or im.width < 100 or im.height < 100
                or im.width * im.height > 64_000_000 or im.height > 65000
                or getattr(im, 'n_frames', 1) != 1):
            raise GuideUnavailable('攻略图片尺寸或格式异常。')
        if screenshot and im.format != 'JPEG':
            raise GuideUnavailable('帖子长截图格式异常。')
        im.verify()


async def download_image(url):
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        async with client.stream('GET', image_url(url), headers={'Referer': AUTHOR_URL}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise GuideUnavailable('阵容原图超出发送限制。')
                chunks.append(chunk)
    data = b''.join(chunks)
    validate_image(data)
    return data


async def capture_page(page, post, quality=95):
    url = POST_URL + str(post['post_uuid'])
    response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
    if response is None or response.status != 200 or page.url != url:
        raise GuideUnavailable('帖子页面不可用。')
    root = page.locator('.post-letter-paper')
    await root.wait_for(state='visible', timeout=30000)
    if await root.count() != 1:
        raise GuideUnavailable('帖子正文结构已变化。')
    await page.wait_for_function('(title) => document.querySelector(".post-letter-paper")?.innerText.includes(title)',
                                 arg=post['title'], timeout=30000)
    expected = example_image(post['content'])
    # Select the article editor only; comments have their own ql-editor nodes.
    actual = await root.locator('.ql-editor img').evaluate_all('(imgs)=>imgs.map(i=>i.src)')
    if expected not in actual or await page.locator('input[type="password"]:visible').count():
        raise GuideUnavailable('帖子内容未完整加载或出现登录窗口。')
    await page.add_style_tag(content='body *{visibility:hidden!important}.post-letter-paper,.post-letter-paper *{visibility:visible!important}')
    await root.evaluate('''e => {
        for(let p=e;p;p=p.parentElement){p.style.overflow='visible';p.style.height='auto';
            p.style.maxHeight='none';if(['sticky','fixed'].includes(getComputedStyle(p).position))p.style.position='static';}
        for(const i of e.querySelectorAll('img')){i.loading='eager';i.scrollIntoView();}
    }''')
    await page.wait_for_function('''() => {
        const imgs=[...document.querySelector('.post-letter-paper').querySelectorAll('img')];
        return imgs.length>0 && imgs.every(i=>i.complete && i.naturalWidth>0);
    }''', timeout=45000)
    await page.evaluate('() => document.fonts.ready')
    box = await root.bounding_box()
    if not box or box['width'] * box['height'] > 64_000_000 or box['height'] > 65000:
        raise GuideUnavailable('帖子超出完整长截图尺寸限制。')
    quality = quality if type(quality) is int and 0 <= quality <= 100 else 95
    data = await root.screenshot(type='jpeg', quality=quality, animations='disabled', timeout=45000)
    validate_image(data, screenshot=True)
    return data


async def capture_post(post, *, channel='auto', quality=95):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        choices = (None, 'msedge') if channel == 'auto' else ((None,) if channel == 'chromium' else ('msedge',))
        browser = None
        for choice in choices:
            try:
                browser = await playwright.chromium.launch(headless=True, channel=choice)
                break
            except Exception:
                if choice == choices[-1]:
                    raise GuideUnavailable('攻略截图浏览器不可用。') from None
        context = None
        try:
            context = await browser.new_context(viewport={'width':1440,'height':1000},
                device_scale_factor=1, locale='zh-TW', timezone_id='Asia/Shanghai')
            return await capture_page(await context.new_page(), post, quality)
        finally:
            if context is not None:
                await context.close()
            await browser.close()
