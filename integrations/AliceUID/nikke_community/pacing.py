"""Validated second ranges shared by WebUI and the community runner."""
from __future__ import annotations

import re

REQUEST_KEY = 'AliceUID_CommunityRequestRange'
SWITCH_KEY = 'AliceUID_CommunityAccountRange'
REQUEST_DEFAULT = '5-15'
SWITCH_DEFAULT = '10-120'
RANGE_KEYS = {REQUEST_KEY: REQUEST_DEFAULT, SWITCH_KEY: SWITCH_DEFAULT}


def parse_range(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('时间范围须为最小秒数-最大秒数')
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]{1,3})?)\s*-\s*([0-9]+(?:\.[0-9]{1,3})?)', value.strip())
    if match is None:
        raise ValueError('时间范围须为最小秒数-最大秒数')
    lower, upper = map(float, match.groups())
    if not 1 <= lower <= upper <= 3600:
        raise ValueError('须满足1≤最小值≤最大值≤3600秒')
    return lower, upper


def configured_range(config, key):
    try:
        return parse_range(config.get_config(key).data)
    except (KeyError, AttributeError, TypeError, ValueError):
        return parse_range(RANGE_KEYS[key])
