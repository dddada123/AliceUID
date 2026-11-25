"""Shared recent numbered-selection router for nk查询1~20 (120s TTL)."""
from __future__ import annotations

from collections import OrderedDict
import time
from typing import Awaitable, Callable

SELECTION_TTL_SECONDS = 120
_MAX_SESSIONS = 256
_sessions: OrderedDict[tuple[str, str, str], tuple[float, float, Callable[..., Awaitable]]] = OrderedDict()


def _session_key(ev) -> tuple[str, str, str]:
    bot_id = str(getattr(ev, 'bot_id', '') or '')
    group_id = str(getattr(ev, 'group_id', '') or 'dm')
    user_id = str(getattr(ev, 'user_id', '') or '')
    return (bot_id, group_id, user_id)


def register_selection(ev, handler, *, ttl: float = SELECTION_TTL_SECONDS, clock=time.monotonic) -> None:
    key = _session_key(ev)
    now = clock()
    _sessions[key] = (now, now + ttl, handler)
    _sessions.move_to_end(key)
    while len(_sessions) > _MAX_SESSIONS:
        _sessions.popitem(last=False)


async def dispatch_selection(bot, ev, index: int, *, clock=time.monotonic) -> bool:
    key = _session_key(ev)
    entry = _sessions.get(key)
    if not entry:
        return False
    _, expires_at, handler = entry
    if clock() > expires_at:
        _sessions.pop(key, None)
        return False
    await handler(bot, ev, index)
    return True
