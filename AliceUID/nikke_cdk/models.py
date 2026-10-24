"""Small JSON-compatible records; never store credentials in catalog data."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo('Asia/Shanghai')
TOKYO = ZoneInfo('Asia/Tokyo')
PRODUCT = '29080'
SOURCE_URL = 'https://gamewith.jp/nikke/article/show/371014'
PARSER_VERSION = 1


def code_text(value):
    if not isinstance(value, str):
        raise ValueError('兑换码格式不正确')
    code = value.strip()
    if not 1 <= len(code) <= 32 or not re.fullmatch(r'[A-Za-z0-9_-]+', code):
        raise ValueError('请输入单个1～32位兑换码（字母、数字、下划线或连接符），不要附带空格或换行')
    return code


def clean(value, limit=1200):
    if not isinstance(value, str):
        return ''
    return ''.join(c for c in value if c in '\n\t' or unicodedata.category(c)[0] != 'C').strip()[:limit]


def day_at(now):
    return datetime.fromtimestamp(now, SHANGHAI).date().isoformat()


def time_text(now):
    return datetime.fromtimestamp(now, SHANGHAI).strftime('%m/%d %H:%M')


def identity(bind):
    import hashlib
    import json
    parts = [str(bind.game_id), str(bind.intl_open_id), int(bind.area_id), str(bind.uid)]
    return hashlib.sha256(json.dumps(parts, separators=(',', ':')).encode()).hexdigest()


def revision(bind):
    import hashlib
    return hashlib.sha256((identity(bind) + str(bind.cookie_enc)).encode()).hexdigest()


def eligible(item, now):
    return (item.get('state') == 'candidate'
            and (not item.get('expires_at') or now < item['expires_at'])
            and (not item.get('valid_from') or now >= item['valid_from']))


def merged(snapshots, now, blocked):
    result = {}
    warnings = []
    for source in ('official', 'gamewith'):
        snapshot = snapshots.get(source)
        if not snapshot:
            warnings.append(('官方' if source == 'official' else 'GameWith') + '暂无可用缓存')
            continue
        age = max(0, now - snapshot['checked_at'])
        if age > 86400 or snapshot.get('parser_version') != PARSER_VERSION:
            warnings.append(('官方' if source == 'official' else 'GameWith') + '缓存已超时或需要重新解析')
            continue
        for row in snapshot['items']:
            if not eligible(row, now) or row['code'] in blocked:
                continue
            code = row['code']
            if code not in result:
                result[code] = dict(code=code, sources=[], reward='', expires_at=None)
            item = result[code]
            item['sources'].append(source)
            if source == 'gamewith':
                item['reward'] = clean(row.get('reward', ''))
                item['expires_at'] = row.get('expires_at')
    # A source-only casing variation is not proof of a second distinct code.
    cases = {}
    for code in result:
        cases.setdefault(code.casefold(), []).append(code)
    ambiguous = {c for values in cases.values() if len(values) > 1 for c in values}
    if ambiguous:
        warnings.append('存在大小写冲突的兑换码，已暂缓自动列入')
    return [v for k, v in result.items() if k not in ambiguous], warnings
