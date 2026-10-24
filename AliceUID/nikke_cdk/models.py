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
PARSER_VERSION = 3
EXPIRY_GRACE = 5 * 60
RECENT_SUCCESS = 48 * 3600


def code_text(value):
    if not isinstance(value, str):
        raise ValueError('兑换码格式不正确')
    code = value.strip()
    if not 1 <= len(code) <= 32 or not re.fullmatch(r'[A-Za-z0-9_-]+', code):
        raise ValueError('请输入单个1～32位兑换码（字母、数字、下划线或连接符），不要附带空格或换行')
    return code


def code_key(value):
    return code_text(value).casefold()


def code_lookup(mapping, code):
    key = code_key(code)
    return next((value for name, value in mapping.items() if code_key(name) == key), None)


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


def retirement_at(item):
    return item['expires_at'] + EXPIRY_GRACE if item.get('expires_at') else None


def eligible(item, now, *, grace=0):
    return (item.get('state') == 'candidate'
            and (not item.get('expires_at') or now < item['expires_at'] + grace)
            and (not item.get('valid_from') or now >= item['valid_from']))


def merged(snapshots, now, blocked, members=(), details=None, inventory=()):
    result = {}
    warnings = []
    if details is None:
        details = {r['code']: r for r in snapshots.get('gamewith', {}).get('items', [])}
    details = {code_key(k): v for k, v in details.items()}
    # Pure callers may not use Store.details(); never let GW replace a known official window.
    for row in snapshots.get('official', {}).get('items', []):
        key = code_key(row['code'])
        detail = dict(details.get(key, {}))
        if detail.get('expiry_source') != 'official' and row.get('expires_at'):
            detail.update(expires_at=row['expires_at'], expiry_source='official')
        if row.get('valid_from') and not detail.get('official_valid_from'):
            detail.update(valid_from=row['valid_from'], official_valid_from=row['valid_from'])
        details[key] = detail
    blocked_keys = {code_key(k) for k in blocked}
    members = list(members)
    member_names = {code_key(row['code']): row['code'] for row in reversed(members)}
    known = {row['code_key']: row for row in inventory}

    def available(code):
        key = code_key(code)
        detail = details.get(key, {})
        end = retirement_at(detail)
        return (key not in blocked_keys and (end is None or now < end)
                and (not detail.get('valid_from') or now >= detail['valid_from']))

    for source in ('official', 'gamewith'):
        snapshot = snapshots.get(source)
        if not snapshot:
            warnings.append(('官方' if source == 'official' else 'GameWith') + '暂无可用缓存')
            continue
        age = max(0, now - snapshot['checked_at'])
        if age > 86400 or snapshot.get('parser_version') not in (2, PARSER_VERSION):
            warnings.append(('官方' if source == 'official' else 'GameWith') + '缓存已超时或需要重新解析')
            continue
        if snapshot.get('parser_version') != PARSER_VERSION:
            warnings.append(('官方' if source == 'official' else 'GameWith') + '缓存待补充新版信息；暂保留已知可用码')
        for row in snapshot['items']:
            detail = details.get(code_key(row['code']), {})
            window = row
            if detail.get('expiry_source') == 'official':
                window = {**row, 'expires_at': detail['expires_at'], 'valid_from': detail.get('valid_from')}
            if not eligible(window, now, grace=EXPIRY_GRACE) or not available(row['code']):
                continue
            code = code_key(row['code'])
            if code not in result:
                display = known.get(code, {}).get('code') or member_names.get(code) or row['code']
                result[code] = dict(code=display, sources=[], reward='', expires_at=None)
            item = result[code]
            if source not in item['sources']:
                item['sources'].append(source)
            if source == 'gamewith':
                item['reward'] = clean(row.get('reward', ''))
                item['expires_at'] = row.get('expires_at')
    # Leaving the recommendation page is not an expiry verdict. A persisted official
    # window keeps existing inventory available until its actual retirement boundary.
    for code, known_row in known.items():
        detail = details.get(code, {})
        if detail.get('expiry_source') != 'official' or not detail.get('expires_at') or not available(known_row['code']):
            continue
        item = result.setdefault(code, dict(code=known_row['code'], sources=[], reward='', expires_at=None))
        if 'official' not in item['sources']:
            item['sources'].insert(0, 'official')
    for row in members:
        code = code_key(row['code'])
        if not available(code):
            continue
        if code not in result:
            result[code] = dict(code=known.get(code, {}).get('code') or row['code'], sources=[], reward='', expires_at=None)
        item = result[code]
        if 'member' not in item['sources']:
            item['sources'].append('member')
        item['verified_at'] = max(item.get('verified_at', 0), row['last_verified'])
    for code, item in result.items():
        detail = details.get(code, {})
        if clean(detail.get('reward')):
            item['reward'] = clean(detail['reward'])
        if detail.get('expires_at'):
            item['expires_at'] = detail['expires_at']
            item['expiry_source'] = detail.get('expiry_source', 'gamewith')
            item['retire_at'] = retirement_at(detail)
        if detail.get('valid_from'):
            item['valid_from'] = detail['valid_from']
    # Source refreshes enrich existing stock without renaming or reordering it.
    ordered = sorted(result, key=lambda k: known.get(k, {}).get('position', float('inf')))
    return [result[key] for key in ordered], warnings
