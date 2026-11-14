"""Bounded fuzzy recognition of recommended-settings notices, never battle parameters."""
from .loading import wait_until
import html
import re
import unicodedata
from datetime import date

TRANSLATION = str.maketrans('薦燒風壓電擊鐵熱', '荐烧风压电击铁热')
ALIASES = {
    '작열': ('燃烧','灼热','작열'), '수냉': ('水冷','수냉'),
    '풍압': ('风压','풍압'), '전격': ('电击','전격'), '철갑': ('铁甲','철갑')}
SHORT = {'火':'작열','水':'수냉','风':'풍압','电':'전격','铁':'철갑'}
ENGLISH = {'fire':'작열','water':'수냉','wind':'풍압','electric':'전격','electronic':'전격','iron':'철갑'}
ACTION = re.compile(r'套用|应用|應用|导入|導入|apply|import|적용|가져오기|추천 설정 넣기', re.I)


def normalize(text):
    if not isinstance(text, str) or len(text) > 2000:
        return ''
    for _ in range(2):text=html.unescape(text)
    text=re.sub(r'<[^>]*>', ' ', text)
    text=unicodedata.normalize('NFKC',text).translate(TRANSLATION).casefold()
    return ''.join(c for c in text if unicodedata.category(c)!='Cf')


def notice_dates(text):
    text=normalize(text)
    values=set()
    for match in re.finditer(r'(?<!\d)(20\d{2})\s*(?:[-./]|年)\s*(\d{1,2})\s*(?:[-./]|月)\s*(\d{1,2})(?!\d)\s*日?',text):
        try:values.add(date(*map(int,match.groups())))
        except ValueError:raise ValueError('推荐通知日期无效') from None
    return values


def parse_notice(text):
    normalized=normalize(text)
    compact=re.sub(r'\s+','',normalized)
    if not re.search(r'推荐|추천|recommend(?:ed|ation|ations)?',normalized,re.I):return None
    if not re.search(r'(?<![a-z])updated?(?![a-z])|更新',normalized,re.I):return None
    dates=notice_dates(normalized)
    if not dates:return None
    if len(dates)!=1:raise ValueError('推荐通知存在多个日期，无法唯一确认')
    codes={code for code,aliases in ALIASES.items() if any(alias in compact for alias in aliases)}
    codes.update(code for word,code in ENGLISH.items() if re.search(r'\b'+word+r'\b',normalized))
    for word,code in SHORT.items():
        standalone=re.search(r'(?<![\u3400-\u9fffA-Za-z])'+word+r'(?![\u3400-\u9fffA-Za-z])',normalized)
        context=re.search(word+r'(?=属性|弱点|单人|单突|solo|raid|突袭|突击|代码|[（(\[【]20\d{2})',compact)
        tagged=re.search(r'(?:属性|弱点|推荐(?:设置)?)[：:]?'+word+r'(?=[：:，,、。.!?（）()\d]|$)',compact)
        if standalone or context or tagged:codes.add(code)
    if len(codes)!=1:raise ValueError('推荐通知属性无法唯一确认')
    return {'weakness':next(iter(codes)),'updated':next(iter(dates)).isoformat()}


def validate_notice(text,recommendation):
    parsed=parse_notice(text)
    if parsed:
        if parsed['weakness']!=recommendation['weakness']:
            raise ValueError('推荐通知属性与实际配置不一致，本次停止套用')
        if not recommendation.get('updated') or parsed['updated']!=recommendation['updated']:
            raise ValueError('推荐通知日期与最新配置不一致，请重新查询')
    return parsed


async def find_trigger(page,recommendation,timeout):
    # Wait only for native recommendation controls or a similarly formatted notice.
    try:
        await wait_until(page, """() => {
        const visible=e=>!!e&&e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0
            &&getComputedStyle(e).visibility!=='hidden';
        return ['.rec-new .btn-primary','#boss-rec-solo','#bt-rec .bt-rec-go'].some(s=>visible(document.querySelector(s)))
            || !!document.querySelector('#bt-rec.is-using')
            || [...document.querySelectorAll('[role="alert"],[role="status"],.notice,.notification,.announcement')].some(e=>
                visible(e)&&/推荐|推薦|추천|recommend/i.test((e.textContent||'').normalize('NFKC'))&&/updated?|更新/i.test((e.textContent||'').normalize('NFKC'))
                &&/20[0-9]{2}/.test((e.textContent||'').normalize('NFKC'))&&[...e.querySelectorAll('button')].some(visible));
    }""", timeout=min(timeout,5000))
    except Exception as exc:
        from playwright.async_api import TimeoutError as BrowserTimeout
        if isinstance(exc,BrowserTimeout):return None
        raise
    native=page.locator('.rec-new')
    if await native.count()==1 and await native.is_visible():
        validate_notice(await native.inner_text(),recommendation)
        button=native.locator('.btn-primary')
        if await button.count()==1 and await button.is_visible():return button

    candidates=page.locator('[role="alert"],[role="status"],.notice,.notification,.announcement')
    buttons={}; invalid=[]
    for i in range(await candidates.count()):
        notice=candidates.nth(i)
        if not await notice.is_visible():continue
        actions=notice.get_by_role('button',name=ACTION)
        if await actions.count()!=1:continue
        try:parsed=validate_notice(await notice.inner_text(),recommendation)
        except ValueError as exc:
            invalid.append(str(exc));continue
        if not parsed:continue
        button=actions.first
        token=await button.evaluate("""(e,token)=>{const key='data-alice-rec-trigger';
            if(!e.hasAttribute(key))e.setAttribute(key,token);return e.getAttribute(key)}""",str(i))
        buttons[token]=button
    if len(buttons)>1:raise ValueError('存在多条匹配的推荐通知，无法唯一选择导入按钮')
    if buttons:return next(iter(buttons.values()))
    if invalid:raise ValueError(invalid[0])
    for selector in ['#boss-rec-solo','#bt-rec .bt-rec-go']:
        button=page.locator(selector)
        if await button.count()==1 and await button.is_visible():return button
    return None
