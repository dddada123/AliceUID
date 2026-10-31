"""Native to_ai integration for four read-only queries; no extra AI dependency."""
from __future__ import annotations
from contextvars import ContextVar
from functools import wraps
import json
import sys

_pending = ContextVar('aliceuid_ai_summaries', default=None)


def description(text):
    """Opt-in registration: AI-disabled installations never import Core AI here."""
    from ..nikke_config.config import AliceUIDConfig
    return text if AliceUIDConfig.get_config('AliceUID_AIQueryEnabled').data else ''


def active():
    return _pending.get() is not None


def core_allowed(sv, ev):
    """Match Core handler's plugin/SV lists, area and permission semantics.

    Core's to_ai bridge currently checks enabled/pm only. Keep the remaining
    command-path constraints here, covered against the pinned native predicate.
    """
    plugin = sv.plugins
    if type(ev.user_pm) is not int or ev.user_pm < 0:
        return False
    for scope in (plugin, sv):
        if not scope.enabled or ev.user_pm > scope.pm:
            return False
        if ev.group_id in scope.black_list or ev.user_id in scope.black_list:
            return False
        if scope.white_list and scope.white_list != ['']:
            if ev.user_id not in scope.white_list and ev.group_id not in scope.white_list:
                return False
    area = plugin.area
    if not (area in ('SV', 'ALL') or ev.user_type == 'group' and area == 'GROUP'
            or ev.user_type == 'direct' and area == 'DIRECT'):
        return False
    return (sv.area == 'ALL' or area == 'ALL' or ev.user_type == 'group' and sv.area == 'GROUP'
            or ev.user_type == 'direct' and sv.area == 'DIRECT')


async def allowed(sv, ev):
    from ..nikke_config.config import AliceUIDConfig
    from ..nikke_permissions.runtime import get_policy
    from gsuid_core.utils.plugins_config.gs_config import sp_config
    if not AliceUIDConfig.get_config('AliceUID_AIQueryEnabled').data or not core_allowed(sv, ev):
        return False
    blacklist = sp_config.get_config('BlackList').data
    if ev.user_id in blacklist or ev.group_id in blacklist:
        return False
    policy = get_policy()
    return policy.user_allowed(ev.user_id) and await policy.query_allowed(ev.group_id)


def _has_image(message):
    if isinstance(message, bytes):
        return True
    if isinstance(message, list):
        return any(_has_image(item) for item in message)
    from gsuid_core.models import Message
    return isinstance(message, Message) and message.type == 'image'


class _QueryBot:
    def __init__(self, bot, sv, ev, bridge):
        self._bot, self._sv, self._ev, self._bridge = bot, sv, ev, bridge

    def __getattr__(self, name):
        return getattr(self._bot, name)

    async def send(self, message, *args, **kwargs):
        if not await allowed(self._sv, self._ev):
            _pending.get().clear()
            return False
        result = await self._bot.send(message, *args, **kwargs)
        # Only publish data after the handler's final ownership checks produced
        # an image. Rendering errors or revoked bindings never leak staged data.
        if _has_image(message):
            for summary in _pending.get():
                self._bridge.ai_return(summary)
        _pending.get().clear()
        return result


def query(sv, *, no_args=False):
    """Applied BEFORE to_ai captures the function; ordinary dispatch is unchanged."""
    def decorate(func):
        @wraps(func)
        async def guarded(bot, ev):
            # Core already loaded this module to construct its MockBot. Looking
            # it up avoids importing the AI engine during ordinary commands.
            bridge = sys.modules.get('gsuid_core.ai_core.trigger_bridge')
            if bridge is None or not isinstance(bot, bridge.MockBot):
                return await func(bot, ev)
            if not await allowed(sv, ev):
                return await bot.send('当前未获准通过AI调用此妮姬查询，请联系Bot主检查功能开关和权限。')
            if no_args and ev.text.strip():
                return await bot.send('此查询无需参数，仅查询当前发起者绑定的账号。')
            token = _pending.set([])
            try:
                return await func(_QueryBot(bot, sv, ev, bridge), ev)
            finally:
                _pending.reset(token)
        return guarded
    return decorate


def summary(kind, context):
    """Only explicitly selected display fields may enter AI output, never raw APIs."""
    if not active():
        return
    if kind == 'profile':
        data = {key: context[key] for key in ('area_label', 'level', 'stats', 'progress', 'outpost')}
    elif kind == 'character':
        data = {key: context[key] for key in ('name', 'level', 'combat', 'grade', 'core', 'bond')}
        data['skills'] = [{key: row[key] for key in ('name', 'level')} for row in context['skills']]
        data['gear'] = [{key: row[key] for key in ('label', 'tier', 'lv')} for row in context['gear']]
    elif kind == 'aliases':
        data = {key: context[key] for key in ('name', 'aliases', 'automatic_aliases')}
    else:
        raise ValueError('unsupported AI summary kind')
    _pending.get().append('AliceUID查询结果（现有缓存可能被复用，缺失值不作推测）：' +
                          json.dumps(data, ensure_ascii=False, separators=(',', ':')))
