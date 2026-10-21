"""Per-send receipt timeout for Core without mutating its global wait deadline."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from types import FunctionType, MethodType

_OVERRIDE = ContextVar('aliceuid_forward_receipt', default=None)
KEY = 'AliceUID_ForwardReceiptSeconds'
DEFAULT = 30


def configured_timeout():
    from ..nikke_config.config import AliceUIDConfig
    try:
        value = AliceUIDConfig.get_config(KEY).data
        if type(value) is int and 5 <= value <= 300:
            return value
    except (KeyError, AttributeError, TypeError, ValueError):
        pass
    return DEFAULT


def core_timeout(transport):
    method = getattr(transport, 'target_send', None)
    function = getattr(method, '__func__', method)
    value = getattr(function, '__globals__', {}).get('RECALL_WAIT_TIMEOUT', 10.0)
    return float(value) if type(value) in (int, float) and 0 < value < 3600 else 10.0


@contextmanager
def receipt_scope(transport, seconds):
    token = _OVERRIDE.set((transport, seconds))
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


def install_timeout_override(transport):
    """Wrap the reviewed Python Core method once; other sends use it unchanged.

    Core's target_send reads RECALL_WAIT_TIMEOUT after queuing its frames. A
    shallow per-call globals copy supplies that number to the same function
    code, preserving echo IDs, pending futures, cancellation and queue logic.
    Never change Core globals or bypass Bot.send and its permission wrappers.
    """
    method = getattr(transport, 'target_send', None)
    function = getattr(method, '__func__', None)
    if getattr(function, '_aliceuid_receipt_override', False):
        return True
    if (not isinstance(function, FunctionType)
            or getattr(method, '__self__', None) is not transport
            or 'RECALL_WAIT_TIMEOUT' not in function.__code__.co_names):
        return False

    @wraps(function)
    async def target_send(self, *args, **kwargs):
        override = _OVERRIDE.get()
        if override is None or override[0] is not self or not kwargs.get('wait_recall', False):
            return await function(self, *args, **kwargs)
        scope = dict(function.__globals__, RECALL_WAIT_TIMEOUT=override[1])
        isolated = FunctionType(function.__code__, scope, function.__name__,
                                function.__defaults__, function.__closure__)
        isolated.__kwdefaults__ = function.__kwdefaults__
        return await isolated(self, *args, **kwargs)

    target_send._aliceuid_receipt_override = True
    try:
        transport.target_send = MethodType(target_send, transport)
    except (AttributeError, TypeError):
        return False
    return True
