"""绑定相关的业务封装：加密、读写、构造客户端。"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import asyncio
import hashlib
from functools import wraps
from typing import Callable, Optional

from ..nikke_api.auth import CookieCipher
from ..nikke_api.client import NikkeClient, REGIONS
from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
from .models import AliceBind

_cipher: Optional[CookieCipher] = None
_binding_locks: dict[tuple[str, str], asyncio.Lock] = {}


def binding_lock(user_id: str, bot_id: str) -> asyncio.Lock:
    return _binding_locks.setdefault((str(user_id), str(bot_id)), asyncio.Lock())


def get_cipher() -> CookieCipher:
    global _cipher
    if _cipher is None:
        _cipher = CookieCipher(MAIN_PATH / "secret.key")
    return _cipher


def master_qq_list() -> list[str]:
    try:
        return [str(x).strip() for x in AliceUIDConfig.get_config("AliceUID_MasterQQ").data if str(x).strip()]
    except Exception:
        return []


def is_master(user_id: str) -> bool:
    return str(user_id) in master_qq_list()


class BindingPersistenceError(RuntimeError):
    """A binding write did not produce the committed state requested by the caller."""


class _BindingRejected(ValueError):
    pass


def _binding_errors(func):
    @wraps(func)
    async def guarded(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (_BindingRejected, BindingPersistenceError):
            raise
        except Exception:
            # Never propagate SQL parameters / encrypted cookie in an error.
            raise BindingPersistenceError("绑定保存未确认") from None
    return guarded


@_binding_errors
async def save_login(
    user_id: str,
    bot_id: str,
    group_id: Optional[str],
    *,
    openid: str,
    area_id: int,
    game_id: str,
    cookie: str,
    nickname: str,
    uid: str,
    expire_at: int,
    still_current: Optional[Callable[[], bool]] = None,
    replace_revision: str = "",
    login_notification=None,
) -> int:
    async with binding_lock(user_id, bot_id):
        existing=await AliceBind.get_bind(user_id,bot_id)
        if existing and not replace_revision:
            raise _BindingRejected(f"已有绑定，已停止覆盖；换号请先 {command_prefix()}解绑")
        if replace_revision and (existing is None or
                hashlib.sha256(existing.cookie_enc.encode()).hexdigest()!=replace_revision or
                (str(existing.intl_open_id),int(existing.area_id),str(existing.game_id))!=(str(openid),int(area_id),str(game_id)) or
                (existing.uid and uid and str(existing.uid)!=str(uid))):
            raise _BindingRejected('原绑定已变化，或登录的不是同账号同区服；未替换原Cookie。')
        if still_current is not None and not still_current():
            raise _BindingRejected("登录链接已失效，请重新获取绑定链接")
        recovery = None
        if replace_revision:
            try:
                from ..nikke_community.runtime import capture_login_recovery
                recovery = capture_login_recovery(existing)
            except Exception:
                recovery = {'unavailable': True}
        encrypted = get_cipher().encrypt(cookie)
        master = is_master(user_id)
        if replace_revision:
            result=await AliceBind.replace_cookie(user_id,bot_id,
                expected_cookie=existing.cookie_enc,openid=openid,area_id=area_id,game_id=game_id,
                cookie_enc=encrypted,nickname=nickname,uid=uid or existing.uid,cookie_expire=expire_at)
            stored=await AliceBind.get_bind(user_id,bot_id)
            if result!=0 or stored is None or stored.cookie_enc!=encrypted or stored.cookie_expire!=expire_at:
                raise BindingPersistenceError('重新登录的Cookie保存未确认')
            # Old renders and old automatic jobs must not publish under the new
            # credential revision. Do not reset any community budget ledger.
            # Transfer only the verified same-account authorization before invalidating old jobs.
            try:
                from ..nikke_community.runtime import restore_login_recovery
                restore_login_recovery(recovery, stored)
            except Exception:
                pass  # A confirmed login must not be reclassified as a failed login.
            await _invalidate_replaced(existing)
            _start_login_prefetch(stored, group_id, notification=login_notification)
            return 0
        result = await AliceBind.save_bind(
            user_id=user_id,
            bot_id=bot_id,
            group_id=group_id,
            openid=openid,
            area_id=area_id,
            game_id=game_id,
            cookie_enc=encrypted,
            nickname=nickname,
            uid=uid,
            cookie_expire=expire_at,
            is_master=master,
        )
        if result != 0:
            raise BindingPersistenceError("绑定保存返回失败")
        # Core's write decorator commits before returning; a fresh read checks
        # durable state, not a detached object or an uncommitted session cache.
        stored = await AliceBind.get_bind(user_id, bot_id)
        expected = dict(intl_open_id=openid, area_id=area_id, game_id=game_id,
                        cookie_enc=encrypted, nickname=nickname, uid=uid,
                        cookie_expire=expire_at, is_master=master)
        if stored is None or any(getattr(stored, key, None) != value for key, value in expected.items()):
            raise BindingPersistenceError("绑定保存后校验失败")
        _start_login_prefetch(stored, group_id, notification=login_notification)
        try:
            from ..nikke_cdk.runtime import schedule_new_binding
            schedule_new_binding(stored, group_id)
        except Exception as exc:
            from gsuid_core.logger import logger
            logger.warning(f'[AliceUID] new binding CDK scheduling deferred error_type={type(exc).__name__}')
        return 0


def _start_login_prefetch(bind, group_id, *, notification=None):
    # A background cache failure must never turn a confirmed login into failure.
    try:
        from .panel_refresh import schedule_login_prefetch
        schedule_login_prefetch(bind, group_id, notification=notification)
    except Exception as exc:
        from gsuid_core.logger import logger
        logger.warning(f'[AliceUID] login prefetch scheduling failed error_type={type(exc).__name__}')


async def _invalidate_replaced(existing):
    from gsuid_core.logger import logger
    from .panel_refresh import cancel_prefetch
    cancel_prefetch(existing)
    def character():
        from ..nikke_character.service import character_queries
        from ..nikke_character.cache import panel_identity
        character_queries.invalidate(existing)
        store=character_queries.store()
        if store is not None:
            store.purge(panel_identity(existing))
    def roster():
        from ..nikke_roster.service import revoke_cached_binding
        revoke_cached_binding(existing,existing.user_id,existing.bot_id)
    def community():
        from ..nikke_community.runtime import revoke_binding
        revoke_binding(existing)
    def harvest():
        from ..nikke_harvest.runtime import revoke_binding
        revoke_binding(existing)
    def status():
        from ..nikke_status.service import resource_status
        from ..nikke_union.service import union_queries
        resource_status.invalidate(existing)
        union_queries.invalidate(existing)
    def solo():
        from ..nikke_solo.cache import invalidate_binding
        invalidate_binding(existing)
    def cards():
        from ..nikke_render.cache import revoke_cards
        revoke_cards(existing)
    for cleanup in (character, roster, community, harvest, status, solo, cards):
        try:
            cleanup()
        except Exception as exc:
            logger.warning(f'[AliceUID] 登录已更新，旧缓存清理需复核 stage={cleanup.__name__} error_type={type(exc).__name__}')


async def set_public(user_id: str, bot_id: str, public: bool) -> bool:
    async with binding_lock(user_id, bot_id):
        if await AliceBind.get_bind(user_id, bot_id) is None:
            return False
        result = await AliceBind.update_data(user_id, bot_id, is_public=public)
        stored = await AliceBind.get_bind(user_id, bot_id)
        # update_data returns 0 even when no row matched. Never infer success
        # from that code alone (e.g. a competing delete from another process).
        if result != 0 or stored is None or stored.is_public != public:
            raise BindingPersistenceError("公开设置保存后校验失败")
        return True


async def load_client(user_id: str, bot_id: str, *, community=False) -> tuple[Optional[NikkeClient], Optional[AliceBind]]:
    bind = await AliceBind.get_bind(user_id, bot_id)
    if not bind:
        return None, None
    from .auth_state import expired, known_invalid, mark_invalid
    if expired(bind) or (known_invalid(bind) and not community):
        return None, bind
    if not bind.cookie_enc:
        return None, bind
    try:
        cookie = get_cipher().decrypt(bind.cookie_enc)
    except Exception:
        return None, bind
    from ..nikke_api.auth import credentials_from_cookie

    cred = credentials_from_cookie(cookie, bind.cookie_expire)
    if cred is None:
        return None, bind
    region = REGIONS.get(int(bind.area_id or 0))
    if region is None or cred.game_id != region.game_id:
        return None, bind
    return NikkeClient(cred, region, on_auth_failure=None if community else lambda code: mark_invalid(bind,code)), bind


def bind_summary(bind: AliceBind) -> str:
    from ..nikke_api.auth import mask
    from .auth_state import known_invalid

    cred_state = '已失效，请重新登录' if known_invalid(bind) else '本地可用'
    region = REGIONS.get(int(bind.area_id or 0))
    return (
        f"昵称：{bind.nickname or '未知'}\n"
        f"UID：{bind.uid or '当前区服尚未取得'}\n"
        f"区服：{region.label if region else '不受支持，请重新登录'}\n"
        f"openid：{mask(bind.intl_open_id or '')}\n"
        f"凭据状态：{cred_state}"
    )


def account_status_summary(bind: AliceBind, ev=None) -> str:
    """Aggregate local account, panel cache, automation toggles and privacy status (0 network)."""
    from ..nikke_time import beijing_text
    lines = [bind_summary(bind)]

    # 1. Local panel & profile cache
    try:
        from ..nikke_character.cache import PanelCache, panel_identity
        store = PanelCache(MAIN_PATH / 'cache/panels')
        ident = panel_identity(bind)
        prof = store.read_profile(ident)
        snap = store.read(ident)
        p_time = beijing_text(prof['_checked_at']) if prof and prof.get('_checked_at') else '未缓存'
        if snap and snap.get('roster_checked_at'):
            r_count = len(snap.get('characters') or {})
            r_time = f'已缓存 {r_count} 名（{beijing_text(snap["roster_checked_at"])}）'
        else:
            r_time = '未缓存'
        lines.append(f'名片资料：{p_time}')
        lines.append(f'全量练度：{r_time}')
    except Exception:
        pass

    # 2. Community auto sign-in
    try:
        from ..nikke_community.runtime import recovery_store, configured_sign_time
        from ..nikke_community.notifications import identity as comm_identity
        from ..nikke_community.service import CommunityService
        account, owner = comm_identity(CommunityService, bind)
        st = recovery_store().state(account)
        if st.get('owner') == owner and st.get('enabled'):
            like_tag = '含点赞' if st.get('likes') else '不含点赞'
            fail_tag = f'｜连续失败{st["fail_count"]}/3' if st.get('fail_count') else ''
            lines.append(f'自动签到：开启（{like_tag}，每日 {configured_sign_time()}{fail_tag}）')
        elif st.get('owner') == owner and st.get('auto_disabled'):
            lines.append('自动签到：已因连续失败自动暂停')
        else:
            lines.append('自动签到：未开启')
    except Exception:
        pass

    # 3. Auto CDK
    try:
        from ..nikke_cdk.store import Store as CdkStore
        from ..nikke_cdk.models import identity as cdk_identity
        cdk_db = MAIN_PATH / 'cdk.sqlite3'
        user_on = False
        if cdk_db.is_file():
            cstore = CdkStore(cdk_db)
            acct_key = cdk_identity(bind)
            meta_val = cstore.meta(f'auto_user:{acct_key}')
            if meta_val is None:
                # Check automatic_users table if present
                with cstore.tx() as db:
                    row = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='automatic_users'").fetchone()
                    if row:
                        rec = db.execute('SELECT enabled FROM automatic_users WHERE account=?', (acct_key,)).fetchone()
                        user_on = bool(rec and rec['enabled'])
            else:
                user_on = bool(meta_val)
        sys_on = AliceUIDConfig.get_config('AliceUID_AutoCDKEnabled').data is True
        write_on = AliceUIDConfig.get_config('AliceUID_EnableWriteOps').data is True
        if user_on and sys_on and write_on:
            lines.append('自动兑换码：开启（系统已就绪）')
        elif user_on:
            lines.append('自动兑换码：个人已开启（等待后台开启兑换权限/总开关）')
        else:
            lines.append('自动兑换码：未开启')
    except Exception:
        pass

    # 4. Harvest reminder for current conversation
    if ev is not None:
        try:
            from ..nikke_harvest.planner import route_from_event
            from ..nikke_harvest.runtime import get_runtime
            route = route_from_event(ev)
            sub = get_runtime().store.sub(route['id'])
            if sub and sub.get('enabled'):
                quiet = sub.get('quiet') or '关闭'
                lines.append(f'收菜提醒：本会话已开启（免打扰：{quiet}）')
            else:
                lines.append('收菜提醒：本会话未开启')
        except Exception:
            pass

    # 5. Official privacy pending restore
    try:
        from ..nikke_privacy.service import PrivacyService, account_key as priv_key
        psvc = PrivacyService(MAIN_PATH / 'privacy_restore')
        if psvc.pending(priv_key(bind)) is not None:
            lines.append('官网隐私：个人突袭临时公开中（后台将自动恢复）')
    except Exception:
        pass

    return '\n'.join(lines)
