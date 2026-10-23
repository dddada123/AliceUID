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
    return hashlib.sha256((bind.cookie_enc or '').encode()).hexdigest()


async def _load_binding(actor_id, bot_id):
    from ..nikke_permissions.runtime import get_policy
    if not get_policy().user_allowed(actor_id):
        return None
    from ..nikke_user.service import load_client
    from .commands import Binding
    client, bind = await load_client(actor_id, bot_id, community=True)
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
            for row in await AliceBind.get_all_binds()]


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
        from .notifications import GroupNotifier
        from ..nikke_user.auth_state import expired, known_invalid
        _runtime.runner.notifier = GroupNotifier(_runtime.service, _report_bindings, _send_summary, _summary_allowed,
                                                 invalid=lambda row: expired(row) or known_invalid(row))
    _runtime.commands.local_control = local_community_control
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
        _runtime.runner.notifier.store.observe(ev, _runtime.service.clock())
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


async def _report_bindings():
    from ..nikke_user.models import AliceBind
    return await AliceBind.get_all_binds()

async def _summary_allowed(route):
    from ..nikke_permissions.runtime import get_policy
    from gsuid_core.gss import gss
    from ..nikke_config.config import AliceUIDConfig
    from .notify_policy import notify_allowed
    if not notify_allowed(AliceUIDConfig,route['group_id'],route['bot_id'],route['self_id']):
        return False
    # Only the exact observed connection, never the first connected bot.
    from gsuid_core.sv import SL
    plugin = SL.plugins.get('AliceUID')
    sv = getattr(_runtime,'sv',None)
    def native_allowed(item):
        if item is None or not getattr(item,'enabled',True) or getattr(item,'area','ALL') == 'DIRECT':
            return False
        black = {str(x) for x in getattr(item,'black_list',[])}
        white = {str(x) for x in getattr(item,'white_list',[])}
        return route['group_id'] not in black and (not white or route['group_id'] in white)
    if not native_allowed(plugin) or not native_allowed(sv):
        return False
    transport = gss.active_bot.get(route['ws_id'])
    return transport is not None and getattr(transport,'bot',None) is not None and await get_policy().query_allowed(route['group_id'])

async def _send_summary(route, text):
    from gsuid_core.gss import gss
    transport = gss.active_bot.get(route['ws_id'])
    if transport is None or not await _summary_allowed(route):
        return None
    return await transport.target_send(text, 'group', route['group_id'], route['bot_id'],route['self_id'],
                                       group_id=route['group_id'],at_sender=False,wait_recall=True)


def recovery_store():
    if _runtime is not None:
        return _runtime.service.store
    from ..nikke_config.config import MAIN_PATH
    from .store import CommunityStore
    return CommunityStore(MAIN_PATH/'community.sqlite3')


def capture_login_recovery(bind):
    try:
        from .notifications import identity
        from .service import CommunityService
        account,owner=identity(CommunityService,bind)
        return recovery_store().recovery_snapshot(account,owner)
    except Exception:
        return {'unavailable':True}


def restore_login_recovery(snapshot, bind):
    from .notifications import identity
    from .service import CommunityService
    from .cycle import cycle_day
    import time
    try:
        store=recovery_store()
        _,owner=identity(CommunityService,bind)
        if snapshot and snapshot.get('unavailable'):
            raise ValueError('recovery snapshot unavailable')
        restored=store.transfer_login(snapshot,owner,cycle_day(time.time()))
        if snapshot and snapshot['restore'] and not restored:
            text='登录已成功，自动签到授权发生变化，恢复未确认；请查看自动社区状态。'
        elif restored:
            text=f'已恢复此前开启的自动签到，每日北京时间{configured_sign_time()}执行；全局暂停或权限限制仍生效。'
        else:
            text='自动签到保持关闭；未自动开启此前未授权或手动关闭的任务。'
        store.login_notice(owner,text)
        return text
    except Exception:
        import logging
        logging.getLogger(__name__).warning('AliceUID login succeeded; community recovery unconfirmed')
        return '登录已成功，自动签到恢复未确认，请查看自动社区状态。'


async def login_recovery_notice(actor_id,bot_id):
    try:
        from ..nikke_user.models import AliceBind
        from .notifications import identity
        from .service import CommunityService
        bind=await AliceBind.get_bind(actor_id,bot_id)
        if bind is None:return ''
        _,owner=identity(CommunityService,bind)
        return recovery_store().login_notice(owner) or '自动签到恢复未确认，请查看自动社区状态。'
    except Exception:
        return '自动签到恢复未确认，请查看自动社区状态。'


async def local_community_control(actor_id, bot_id, option):
    """Closing/status must remain available even when a cookie cannot build a client."""
    from ..nikke_permissions.runtime import get_policy
    from ..nikke_user.models import AliceBind
    from ..nikke_user.service import binding_lock
    from .notifications import identity
    from .service import CommunityService
    if not get_policy().user_allowed(actor_id):
        return '当前用户无权使用AliceUID。'
    async with binding_lock(actor_id,bot_id):
        bind=await AliceBind.get_bind(actor_id,bot_id)
        if bind is None:return f'请先发送{command_prefix()}登录绑定本人账号。'
        account,owner=identity(CommunityService,bind)
        store=recovery_store();state=store.state(account)
        if state.get('owner')!=owner:return '当前绑定尚未开启自动社区。'
        if option in ('关闭','关'):
            store.consent(account,owner,False)
            return '自动社区已关闭（签到、浏览及点赞均关闭）；重新登录也不会自动恢复本次手动关闭。'
        paused='无' if not state['paused'] else state['paused']
        return (f'自动社区：{"开启" if state["enabled"] else "关闭"}\n'
                f'点赞：{"开启" if state["likes"] else "关闭"}\n'
                f'连续失败：{state["fail_count"]}/3个签到周期\n'
                f'系统停用：{"连续三天失败" if state["auto_disabled"] else "无"}\n'
                f'暂停：{paused}\n每日自动时间：北京时间{configured_sign_time()}\n'
                f'命令：{command_prefix()}自动社区 开启/关闭/状态。')
