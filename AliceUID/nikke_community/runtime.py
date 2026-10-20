"""GsCore binding adapter for community automation.

Account/owner credential identities are hashed; group observations use chat IDs.
Cookie encryption/decryption remains in
nikke_user. Rebinding and unlinking revoke old consent before touching binding.
"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import hashlib

_runtime = None


def binding_revision(bind) -> str:
    return hashlib.sha256(bind.cookie_enc.encode()).hexdigest()


async def _load_binding(actor_id, bot_id):
    from ..nikke_permissions.runtime import get_policy
    if not get_policy().user_allowed(actor_id):
        return None
    from ..nikke_user.service import load_client
    from .commands import Binding
    client, bind = await load_client(actor_id, bot_id)
    if not get_policy().user_allowed(actor_id):
        if client is not None:
            await client.close()
        return None
    if client is None or bind is None:
        return None
    return Binding(str(actor_id), str(bot_id), binding_revision(bind), client)


async def _list_bindings():
    from ..nikke_user.models import AliceBind
    return [(str(row.user_id), str(row.bot_id), binding_revision(row))
            for row in await AliceBind.get_all_binds() if row.cookie_enc]


async def _binding_current(actor_id, bot_id, revision):
    from ..nikke_user.models import AliceBind
    bind = await AliceBind.get_bind(actor_id,bot_id)
    return bind is not None and binding_revision(bind) == revision


def setup_community(*, policy=None):
    global _runtime
    if policy is None:
        from ..nikke_permissions.runtime import get_policy
        policy = get_policy()
    if _runtime is None:
        from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
        from .integration import setup
        from .pacing import configured_range, REQUEST_KEY, SWITCH_KEY
        request_range = configured_range(AliceUIDConfig, REQUEST_KEY)
        def bounded(key, default, low, high):
            try:
                value = int(AliceUIDConfig.get_config(key).data)
            except (TypeError, ValueError):
                value = default
            return max(low, min(high, value))
        _runtime = setup(
            state_path=MAIN_PATH / 'community.sqlite3',
            load_binding=_load_binding,
            list_bindings=_list_bindings,
            paused=lambda: bool(AliceUIDConfig.get_config('AliceUID_CommunityPaused').data),
            interval_seconds=request_range[0], max_interval_seconds=request_range[1],
            account_interval=configured_range(AliceUIDConfig, SWITCH_KEY),
            daily_requests=bounded('AliceUID_CommunityDailyRequests', 30, 1, 30),
            sign_time=lambda: configured_sign_time(),
            group_report=report_group,
            binding_hint=binding_hint,
        )
    _runtime.service.user_allowed = policy.user_allowed
    _runtime.service.binding_current = _binding_current
    return _runtime


def revoke_binding(bind):
    # Do not instantiate a scheduler while saving or deleting an account.
    if _runtime is not None and bind is not None:
        _runtime.revoke_binding(str(bind.user_id), str(bind.bot_id), binding_revision(bind))


def configured_sign_time():
    from .schedule import DEFAULT, KEY, normalized_time
    try:
        from ..nikke_config.config import AliceUIDConfig
        return normalized_time(AliceUIDConfig.get_config(KEY).data)
    except (ImportError, AttributeError, KeyError, TypeError, RuntimeError):
        return DEFAULT


def apply_sign_schedule(value):
    """No implicit runtime construction while configuration is loading."""
    if _runtime is not None:
        _runtime.job = _runtime.runner.reschedule(value)


def observe_group(ev):
    if _runtime is None or not getattr(ev, 'group_id', None):
        return
    try:
        _runtime.service.store.observe_group(str(ev.user_id), str(ev.bot_id), str(ev.group_id),
                                             _runtime.service.clock())
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('AliceUID group observation unavailable error_type=%s',type(exc).__name__)


async def report_group(bot, ev, page):
    from ..nikke_permissions.runtime import get_policy
    from ..nikke_user.models import AliceBind
    from .report import group_report_text
    from ..nikke_user.auth_state import expired, known_invalid
    policy = get_policy()
    if type(getattr(ev, 'user_pm', None)) is not int or ev.user_pm != 0:
        return '仅Bot主可以查询本群签到记录。'
    if not getattr(ev, 'group_id', None):
        return f'请在群内使用 {command_prefix()}签到查询。'
    if not policy.user_allowed(ev.user_id) or not await policy.query_allowed(ev.group_id):
        return '当前未开放本群签到查询。'
    runtime = setup_community(policy=policy)
    rows = await AliceBind.get_all_binds()
    return group_report_text(runtime.service, rows, bot_id=str(ev.bot_id), group_id=str(ev.group_id),
                             page=page, sign_time=configured_sign_time(), user_allowed=policy.user_allowed,
                             credential_invalid=lambda bind: expired(bind) or known_invalid(bind))


async def binding_hint(actor_id,bot_id):
    from ..nikke_user.models import AliceBind
    from ..nikke_user.auth_state import unavailable_message
    return unavailable_message(await AliceBind.get_bind(actor_id,bot_id))
