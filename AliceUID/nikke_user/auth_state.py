"""Local invalid-credential markers by owner/revision, without storing cookies."""
from ..nikke_commands import command_prefix
import hashlib
import json
import logging
import time
from pathlib import Path

RELOGIN = f'Cookie 已失效或登录凭据不可用，请发送 {command_prefix()}重新登录（或{command_prefix()}重新登陆）更新；原绑定已保留，无需先解绑。'
_invalid_memory = set()


def is_login_error(exc):
    return getattr(exc, 'code', None) in (401, 300001)


def _key(bind):
    revision = hashlib.sha256(str(getattr(bind, 'cookie_enc', '')).encode()).hexdigest()
    owner = [str(getattr(bind,'user_id','')),str(getattr(bind,'bot_id','')),revision]
    return hashlib.sha256(json.dumps(owner,separators=(',',':')).encode()).hexdigest(),revision


def _path(key):
    from ..nikke_config.config import MAIN_PATH
    return Path(MAIN_PATH)/'cache/auth_invalid'/(key+'.json')


def expired(bind):
    value = getattr(bind, 'cookie_expire', 0)
    return type(value) in (int,float) and value>0 and value<=time.time()


def known_invalid(bind):
    key,revision = _key(bind)
    try:
        path = _path(key)
        if str(path) in _invalid_memory:
            return True
        meta=json.loads(path.read_text('utf-8'))
        return isinstance(meta,dict) and meta.get('revision')==revision and meta.get('code') in (401,300001)
    except (OSError,ValueError,ImportError,AttributeError,RuntimeError):
        return False


def mark_invalid(bind, code):
    if code not in (401,300001):
        return
    key,revision = _key(bind)
    try:
        path = _path(key)
        _invalid_memory.add(str(path))
        from ..nikke_resource.cache import atomic_write
        atomic_write(path,json.dumps(dict(revision=revision,code=code,detected_at=time.time())).encode())
    except (OSError,ImportError,AttributeError,RuntimeError) as exc:
        logging.getLogger(__name__).warning('AliceUID auth marker persistence failed error_type=%s',type(exc).__name__)


def unavailable_message(bind):
    if bind is None:
        return f'还没有绑定账号，请发送 {command_prefix()}登录（或{command_prefix()}登陆）选择区服。'
    if expired(bind) or known_invalid(bind):
        return RELOGIN
    return f'绑定数据损坏或Cookie缺失/不可用，请发送 {command_prefix()}重新登录（或{command_prefix()}重新登陆）更新。'
