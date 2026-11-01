"""Pure, bounded cookie import. Never log raw text or include it in errors."""
import time

MAX_COOKIE_BYTES = 256 * 1024
KEYS = frozenset(('game_openid','game_token','game_channelid','game_gameid',
                  'game_login_game','game_adult_status','game_uid','game_user_name'))


class CookieInputError(ValueError):
    pass


def _api_domain(domain, include_subdomains):
    domain = domain.lower().lstrip('.')
    return domain == 'api.blablalink.com' or (domain == 'blablalink.com' and include_subdomains)


def parse_import_cookie(text, *, now=None):
    if not isinstance(text, str):
        raise CookieInputError('Cookie内容格式不正确。')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeError:
        raise CookieInputError('Cookie内容编码不正确，请使用UTF-8文本。') from None
    if size > MAX_COOKIE_BYTES:
        raise CookieInputError('Cookie内容过长或格式不正确，请只导出当前站点。')
    text = text.lstrip('\ufeff').strip()
    now = time.time() if now is None else now
    values, expiries, expired = {}, [], False

    def add(key, value, expiry=0):
        nonlocal expired
        if key not in KEYS:
            return
        if any(ord(c) < 32 or ord(c) == 127 for c in value) or ';' in value:
            raise CookieInputError('Cookie字段含不支持的控制字符。')
        if expiry and expiry <= now:
            expired = True
            return
        if key in values and values[key] != value:
            raise CookieInputError('Blablalink登录字段存在冲突，请只导出当前账号的站点Cookie。')
        values[key] = value
        if expiry:
            expiries.append(expiry)

    if '\t' in text or text.startswith(('# Netscape', '# HTTP Cookie', '#HttpOnly_')):
        for line in text.splitlines():
            line = line.strip()
            if not line or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                continue
            if line.startswith('#HttpOnly_'):
                line = line[len('#HttpOnly_'):]
            fields = line.split('\t')
            domain = fields[0].lower().lstrip('.')
            # Skip unrelated sites BEFORE parsing their names/values/expiry.
            if domain not in ('blablalink.com','api.blablalink.com'):
                continue
            if len(fields) != 7 or fields[1].upper() not in ('TRUE','FALSE') or fields[3].upper() not in ('TRUE','FALSE'):
                raise CookieInputError('Blablalink Cookie应为TAB分隔的七列格式。')
            if not _api_domain(fields[0], fields[1].upper() == 'TRUE') or fields[2] != '/':
                continue
            if fields[5] not in KEYS:
                continue
            try:
                expiry = int(fields[4])
                if expiry < 0 or expiry > 253402300799:
                    raise ValueError()
            except ValueError:
                raise CookieInputError('Cookie到期时间格式不正确。') from None
            add(fields[5],fields[6],expiry)
    else:
        if text.lower().startswith('cookie:'):
            text = text.split(':',1)[1].strip()
        if '\n' in text or '\r' in text:
            raise CookieInputError('请求头Cookie请使用单行name=value格式，或粘贴原始cookies.txt。')
        for part in text.split(';'):
            if '=' in part:
                key,value = part.strip().split('=',1)
                add(key.strip(),value.strip())
    if not values.get('game_openid') or not values.get('game_token'):
        if expired:
            raise CookieInputError('Blablalink登录Cookie已到期，请重新登录官网后导出。')
        return {}, 0
    return values, min(expiries,default=0)
