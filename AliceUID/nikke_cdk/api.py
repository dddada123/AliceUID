"""Official CDK calls and credential-free source fetches, without write retries."""
from __future__ import annotations

import asyncio
import json
import re
import httpx
from email.utils import parsedate_to_datetime

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from .models import PRODUCT, SOURCE_URL, PARSER_VERSION, code_text, clean
from .parser import parse_gamewith

BASE = 'https://api.blablalink.com'
PATH = '/api/game/proxy/Game/'


class SourceError(ValueError):
    def __init__(self, retry_after=900):
        super().__init__('来源请求暂不可用')
        self.retry_after = retry_after


def check_source(response, now):
    if response.status_code == 200:
        return
    delay = 900
    if response.status_code == 429:
        value = response.headers.get('retry-after', '')
        try:
            delay = max(delay, int(value))
        except ValueError:
            try:
                delay = max(delay, parsedate_to_datetime(value).timestamp() - now)
            except (TypeError, ValueError, OverflowError):
                pass
    raise SourceError(delay)


def headers():
    return {'content-type': 'application/json', 'accept': 'application/json',
            'origin': 'https://www.blablalink.com', 'referer': 'https://www.blablalink.com/cdk',
            'x-channel-type': '2', 'x-language': 'zh-TW',
            'x-common-params': json.dumps(dict(game_id='16', area_id='global', source='pc_web',
                intl_game_id=PRODUCT, language='zh-TW', env='prod'), separators=(',', ':'))}


def network_message(value):
    return bool(re.search(
        r'time[ -]?out|timed\s*out|network|connection|gateway|网络|網路|超时|超時|逾時|连接|連線|タイムアウト|接続',
        str(value or ''), re.I))


def envelope(response, endpoint):
    if response.status_code == 401:
        raise NikkeLoginRequired(401, '登录已失效', endpoint)
    if response.status_code != 200:
        raise NikkeApiError(response.status_code, '官方请求未完成', endpoint)
    try:
        data = response.json()
        if not isinstance(data, dict) or type(data.get('code')) is not int:
            raise ValueError()
    except (ValueError, TypeError):
        raise NikkeApiError(-1, '官方响应格式异常，结果未确认', endpoint) from None
    code = data['code']
    if code in (300001, 401):
        raise NikkeLoginRequired(code, '登录已失效', endpoint)
    if code:
        # Do not expose raw upstream messages. Only use an exact allowlist as expiry evidence.
        msg = str(data.get('msg', '')).strip().casefold()
        expiry = msg in {'兑换码已过期', '兌換碼已過期', '兑换码已过期。',
                         'cdkey expired', 'cdkey has expired', 'redemption code has expired'}
        exc = NikkeApiError(code, '官方未完成兑换', endpoint)
        exc.network_uncertain = network_message(msg)
        exc.confirmed_expired = expiry and code == 1302009 and not exc.network_uncertain
        raise exc
    return data.get('data') or {}


async def private(client, name, body):
    endpoint = PATH + name
    if client.credentials.expired:
        raise NikkeLoginRequired(300001, '登录已过期', endpoint)
    if str(client.region.game_id) != PRODUCT:
        raise NikkeApiError(1302004, '当前游戏产品不受支持', endpoint)
    request_headers = {**client.headers(), **headers()}
    try:
        async with client._lock:
            response = await client._http.post(BASE + endpoint, headers=request_headers, json=body,
                                               follow_redirects=False)
        return envelope(response, endpoint)
    except NikkeLoginRequired as exc:
        if client.on_auth_failure:
            client.on_auth_failure(exc.code)
        raise
    except NikkeApiError:
        raise
    except Exception:
        raise NikkeApiError(-1, '网络中断，兑换结果未确认', endpoint) from None


async def recommendation(client):
    data = await private(client, 'GetCdkRedemption', {})
    rows = data.get('cdk_redemption_list')
    if not isinstance(rows, list) or len(rows) > 200:
        raise NikkeApiError(-1, '推荐列表异常', PATH)
    return rows


async def redeem(client, code):
    return await private(client, 'RecordCdkRedemption', {'cdkey': code_text(code)})


async def history(client):
    data = await private(client, 'GetCdkRedemptionHistory', {'page_num': 1, 'page_size': 20})
    rows = data.get('cdk_redemption_list')
    if not isinstance(rows, list):
        raise NikkeApiError(-1, '历史响应异常', PATH)
    return rows


async def fetch_public(source, now):
    # A fresh unauthenticated client per fetch: never reuse a player's cookie jar.
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), follow_redirects=False) as http:
        if source == 'official':
            async with http.stream('POST', BASE + '/api/game/direct/Game/GetCdkRedemption',
                    headers=headers(), json={'intl_game_id': PRODUCT}) as response:
                check_source(response, now)
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 512_000:
                        raise ValueError('官方目录过大')
                    chunks.append(chunk)
                await response.aclose()
                data = envelope(httpx.Response(response.status_code, content=b''.join(chunks)), 'public')
            rows = data.get('cdk_redemption_list')
            if not isinstance(rows, list) or len(rows) > 200 or data.get('is_last_page') is False:
                raise ValueError('官方目录结构或分页变化')
            items = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError('官方条目结构变化')
                product = str(row.get('intl_game_id') or PRODUCT)
                if product in ('29157', 'HMT'):
                    continue
                if product not in (PRODUCT, 'GLOBAL'):
                    raise ValueError('官方产品标识变化')
                items.append(dict(code=code_text(row.get('cdk')), state='candidate', reward=''))
            return dict(items=items, title='官方推荐', checked_at=now, parser_version=PARSER_VERSION)
        async with http.stream('GET', SOURCE_URL, headers={'user-agent': 'AliceUID/1.0.23 CDK catalog',
                                                        'accept': 'text/html'}) as response:
            check_source(response, now)
            if 'text/html' not in response.headers.get('content-type', ''):
                raise ValueError('第三方请求未完成')
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('第三方页面过大')
                chunks.append(chunk)
        content = b''.join(chunks).decode('utf-8', errors='strict')
        parsed = await asyncio.to_thread(parse_gamewith, content, now)
        return {**parsed, 'checked_at': now, 'parser_version': PARSER_VERSION}
