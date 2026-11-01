"""Login-only external HTTPS policy; use the ASGI scheme set by trusted Core proxies."""
from urllib.parse import urlsplit


class LoginAddressError(ValueError):
    pass


def require_https():
    from ..nikke_config.config import AliceUIDConfig
    return AliceUIDConfig.get_config('AliceUID_LoginRequireHTTPS').data is True


def external_base(configured, host='127.0.0.1', port='8765', *, secure=False):
    value = str(configured or '').strip()
    if not value:
        if secure:
            raise LoginAddressError('已开启登录HTTPS要求，请在GsCore后台配置带有效证书的https登录反代地址；HTTP部署可关闭此开关。')
        host = '127.0.0.1' if host in ('0.0.0.0','::','localhost') else host
        value = f'http://{host}:{port}'
    elif '://' not in value:
        value = 'https://' + value  # Preserve the existing no-scheme default.
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http','https') and parsed.hostname and parsed.port != 0
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and not any(c.isspace() or ord(c) < 32 for c in value))
    except ValueError:
        valid = False
    if not valid:
        raise LoginAddressError('登录反代地址格式不正确，请配置http或https站点地址。')
    if secure and parsed.scheme != 'https':
        raise LoginAddressError('已开启登录HTTPS要求，请配置https登录反代地址，或关闭开关以兼容HTTP部署。')
    return value.rstrip('/')
