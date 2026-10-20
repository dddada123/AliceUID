"""Validated minute-precision Beijing schedule; independent of the reset clock."""
import re
KEY = 'AliceUID_CommunitySignTime'
DEFAULT = '08:33'

def valid_time(value):
    return isinstance(value, str) and re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value) is not None

def normalized_time(value):
    return value if valid_time(value) else DEFAULT

def clock_parts(value):
    return tuple(map(int, normalized_time(value).split(':')))
