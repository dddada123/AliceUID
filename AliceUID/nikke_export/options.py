"""One native-prefix command grammar for format, level and public share link."""
from dataclasses import dataclass
import base64
import re
from urllib.parse import urlsplit, parse_qs
from .model import ExportError

PATTERN = r'^(?P<level>[0-9]{1,8})?\s*(?:练度)?全量导出(?P<tail>.*)$'

@dataclass(frozen=True)
class ExportOptions:
    level: int | None = None
    format: str = 'xlsx'
    share: str | None = None

def parse(text):
    match = re.fullmatch(PATTERN, str(text or '').strip())
    if not match:
        raise ExportError('用法：nk[等级]练度全量导出[json] [Blablalink练度链接]。')
    level = int(match['level']) if match['level'] else None
    if level is not None and not 1 <= level <= 10000:
        raise ExportError('模拟等级必须为1至10000的整数，且角色成长表必须包含该等级。')
    tail = match['tail'].strip()
    fmt = 'xlsx'
    if tail[:4].lower() == 'json':
        fmt, tail = 'json', tail[4:].strip()
    if not tail:
        return ExportOptions(level, fmt)
    # Plain URL, [URL], <URL>, and Markdown [label](URL).
    md = re.fullmatch(r'\[[^\]\r\n]*\]\((https://[^\s]+)\)', tail)
    if md:
        tail = md[1]
    elif tail.startswith('[') and tail.endswith(']') or tail.startswith('<') and tail.endswith('>'):
        tail = tail[1:-1]
    try:
        url = urlsplit(tail)
        if (url.scheme != 'https' or url.hostname not in ('www.blablalink.com', 'blablalink.com')
                or url.port not in (None, 443) or url.username or url.password or url.fragment
                or url.path.rstrip('/') != '/shiftyspad/nikke-list' or len(tail) > 2048):
            raise ValueError()
        query = parse_qs(url.query, keep_blank_values=True)
        if set(query) != {'openid'} or len(query['openid']) != 1:
            raise ValueError()
        decoded = base64.b64decode(query['openid'][0], validate=True).decode('ascii')
        if not re.fullmatch(r'(29080|29157)-[0-9]{9,30}', decoded):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise ExportError('练度链接无效，请复制 Blablalink 妮姬列表页面的完整链接。') from None
    return ExportOptions(level, fmt, decoded)
