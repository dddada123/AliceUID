"""Global actor guard for every Trigger belonging to the registered plugin."""
from functools import wraps

DENIED = "你无权使用AliceUID，请联系Bot主。"
_group_observer = None

def set_group_observer(observer):
    global _group_observer
    _group_observer = observer


class _LiveAccessBot:
    """Forward normal Bot operations, recheck actor access on every reply."""
    def __init__(self, bot, policy, actor):
        self._bot, self._policy, self._actor = bot, policy, actor

    def __getattr__(self, name):
        return getattr(self._bot, name)

    async def send(self, *args, **kwargs):
        if not self._policy.user_allowed(self._actor):
            return False
        return await self._bot.send(*args, **kwargs)


def require_user_access(policy):
    def decorate(func):
        @wraps(func)
        async def guarded(bot, ev):
            # Framework-authenticated sender; never ev.at / target QQ.
            if not policy.user_allowed(getattr(ev, "user_id", None)):
                await bot.send(DENIED, at_sender=True)
                return None
            # Authenticated group presence is local metadata, never a member-list claim.
            if _group_observer is not None:
                try:
                    _group_observer(ev)
                except Exception:
                    pass  # Optional local observation must never block the command.
            return await func(_LiveAccessBot(bot, policy, getattr(ev, "user_id", None)), ev)
        return guarded
    return decorate


def guard_plugin_triggers(plugin, policy):
    """Call after ALL SV registrations. Returns count newly guarded; idempotent.

    Uses actual SL.detail_lst[Plugins] -> SV.TL[type][key] -> Trigger.func.
    The access check runs INSIDE Core modify_func, preserving its finally cleanup
    even when denied or bot.send fails. Repeat after registering future triggers.
    """
    from gsuid_core.sv import SL, modify_func
    if isinstance(plugin, str):
        plugin = SL.plugins[plugin]
    wrapper_code = modify_func(lambda *_: None).__code__
    count = 0
    for sv in SL.detail_lst.get(plugin, []):
        for triggers in sv.TL.values():
            for trigger in triggers.values():
                original = trigger.func
                if getattr(original, "_nikke_access_guard", None) is policy:
                    continue
                # SV registration already applies modify_func. Recompose exactly
                # that wrapper rather than moving the access check outside finally.
                raw = original.__wrapped__ if getattr(original, "__code__", None) is wrapper_code and hasattr(original, "__wrapped__") else original
                guarded = modify_func(require_user_access(policy)(raw))
                guarded._nikke_access_guard = policy
                trigger.func = guarded
                count += 1
    return count
