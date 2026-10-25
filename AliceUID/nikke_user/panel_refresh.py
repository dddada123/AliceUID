"""Persistent account snapshots; bounded raw-data prefetch, never render images."""
from __future__ import annotations
import asyncio
from types import SimpleNamespace

_tasks = {}
_task_revisions = {}
_manual_requests = {}
_queue_locks = {}
_profile_locks = {}
_profile_failures = {}
DETAIL_BATCH_SIZE = 20
MAX_OWNED_CHARACTERS = 500


def _check_profile_failure(key):
    import time
    if _profile_failures.get(key, 0) > time.monotonic():
        from ..nikke_character.service import CharacterDataError
        raise CharacterDataError('资料准备未完成，已短暂冷却；未立即重复请求。')


def _profile_failed(key, exc):
    import time
    _profile_failures[key] = time.monotonic() + (60 if getattr(exc, 'code', None) in (403, 429) else 5)


def _owner(bind):
    return str(bind.user_id), str(bind.bot_id)


def _revision(bind):
    from ..nikke_character.cache import panel_identity
    return panel_identity(bind)


def cached_profile(bind):
    from ..nikke_character.service import character_queries
    store = character_queries.store()
    saved = store.read(_revision(bind)) if store is not None else {}
    candidates = [(saved.get('profile_checked_at', saved.get('saved_at', 0)), saved.get('profile'))]
    if store is not None:
        from ..nikke_resource.cache import read_metadata
        light = read_metadata(store.path(_revision(bind), 'profile.json'))
        candidates.append((light.get('checked_at', 0), light.get('profile')))
    import math
    candidates = [(stamp, profile) for stamp, profile in candidates
                  if type(stamp) in (int, float) and math.isfinite(stamp)]
    for stamp, profile in sorted(candidates, key=lambda row: row[0], reverse=True):
        if not isinstance(profile, dict):
            continue
        if all(isinstance(profile.get(k), dict) for k in ('basic', 'outpost', 'saved', 'player')):
            if isinstance(profile.get('chars'), list):
                try:
                    character_queries.roster_codes(profile['chars'])
                    return dict(profile, _checked_at=stamp)
                except ValueError:
                    pass
    return None


async def wait_for_refresh(bind):
    key = (str(getattr(bind, 'user_id', '')), str(getattr(bind, 'bot_id', '')))
    task = _tasks.get(key)
    if (task is not None and task is not asyncio.current_task() and not task.done()
            and _task_revisions.get(key) == _revision(bind)):
        # Cancelling one query must not cancel the account's shared prefetch.
        try:
            result = await asyncio.shield(task)
            if result is False:
                from ..nikke_character.service import character_queries, CharacterDataError
                store = character_queries.store()
                if store is None or not store.read(_revision(bind)):
                    raise CharacterDataError('账号数据准备未完成，请稍后使用刷新面板命令重试。')
        except asyncio.CancelledError:
            if not task.cancelled():
                raise
            from ..nikke_character.service import CharacterDataError
            raise CharacterDataError('绑定或更新任务已变化，请重新查询。') from None


async def ensure_profile(client, bind, *, refresh=False):
    saved = cached_profile(bind)
    previous_stamp = saved.get('_checked_at') if saved else None
    if saved is not None and not refresh:
        return saved
    # A plain profile/roster display does not need every character's equipment.
    from ..nikke_profile.commands import _fetch
    from ..nikke_character.service import character_queries
    from ..nikke_roster.service import account_reads
    from .models import AliceBind
    from .service import binding_lock
    from .auth_state import expired, known_invalid
    expected = _revision(bind)
    async with _profile_locks.setdefault(expected, asyncio.Lock()):
        saved = cached_profile(bind)
        if saved is not None and (not refresh or saved.get('_checked_at') != previous_stamp):
            return saved
        _check_profile_failure(expected)
        try:
            async with account_reads.transaction(client, bind, wait=not refresh) as paced:
                data = await _fetch(paced)
        except Exception as exc:
            _profile_failed(expected, exc)
            raise
        async with binding_lock(bind.user_id, bind.bot_id):
            current = await AliceBind.get_bind(bind.user_id, bind.bot_id)
            if current is None or _revision(current) != expected or expired(current) or known_invalid(current):
                raise ValueError('绑定或登录状态已变化，未保存旧资料。')
            if str(data['basic'].get('area_id', bind.area_id)) != str(bind.area_id):
                raise ValueError('资料区服与绑定区服不一致。')
            character_queries.roster_codes(data['chars'])
            _save_profile(bind, data)
        return cached_profile(bind) or data


def _save_profile(bind, data, *, checked_at=None):
    import json, time
    from ..nikke_resource.cache import atomic_write
    from ..nikke_character.service import character_queries
    store = character_queries.store()
    if store is not None:
        encoded = json.dumps(dict(profile={k:v for k,v in data.items() if not k.startswith('_')},
                                  checked_at=checked_at or time.time()), ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 16*1024*1024:
            raise ValueError('资料缓存超过安全大小。')
        atomic_write(store.path(_revision(bind), 'profile.json'), encoded)


async def refresh_panel(client, bind, *, actor=None, bot=None, only_missing=False,
                        wait=False, policy=None, event=None):
    from ..nikke_profile import commands as profile
    from ..nikke_character.service import character_queries, CharacterDataError
    from ..nikke_roster.service import account_reads, get_roster_service
    from .models import AliceBind
    from .service import binding_lock
    from .auth_state import expired, known_invalid
    actor = str(actor if actor is not None else bind.user_id)
    bot = str(bot if bot is not None else bind.bot_id)
    expected = _revision(bind)
    account = character_queries._account(bind)

    async def check_current():
        current = await AliceBind.get_bind(actor, bot)
        if current is None or _revision(current) != expected:
            raise CharacterDataError('绑定已变化，已停止缓存旧账号资料。')
        if expired(current) or known_invalid(current):
            raise CharacterDataError('登录凭据已失效，请重新登录。')
        if policy is not None and event is not None:
            from ..nikke_roster.commands import allowed
            if not await allowed(policy, event):
                raise CharacterDataError('权限已变化，已停止更新资料。')

    # All character queries and snapshot replacements share this account lock.
    async with character_queries._locks.setdefault(account, asyncio.Lock()):
        await check_current()
        if only_missing:
            store = character_queries.store()
            snapshot = store.read(expected) if store is not None else {}
            codes = character_queries.roster_codes(snapshot.get('roster', []))
            details = snapshot.get('details', {})
            saved = cached_profile(bind)
            if (snapshot.get('complete') and saved is not None and
                    set(details) == {str(code) for code in codes} and
                    all(isinstance(row, dict) and isinstance(row.get('detail'), dict)
                        and isinstance(row.get('effects'), list) for row in details.values())):
                return saved
        epoch = character_queries._epochs.get(account, 0)
        async with _profile_locks.setdefault(expected, asyncio.Lock()):
            _check_profile_failure(expected)
            try:
                async with account_reads.transaction(client, bind, wait=wait) as paced:
                    data = await profile._fetch(paced)
            except Exception as exc:
                _profile_failed(expected, exc)
                raise
            import time
            profile_checked_at = time.time()
            if str(data['basic'].get('area_id', bind.area_id)) != str(bind.area_id):
                raise CharacterDataError('资料区服与绑定区服不一致，已停止缓存。')
            character_queries.roster_codes(data['chars'])
            # Cold-login readers can use the valid light profile before full details finish.
            if cached_profile(bind) is None:
                async with binding_lock(actor, bot):
                    await check_current()
                    _save_profile(bind, data, checked_at=profile_checked_at)
        if str(data['basic'].get('area_id', bind.area_id)) != str(bind.area_id):
            raise CharacterDataError('资料区服与绑定区服不一致，已停止缓存。')
        codes = character_queries.roster_codes(data['chars'])
        if len(codes) > MAX_OWNED_CHARACTERS:
            raise CharacterDataError('角色数量超过本次更新预算，已停止请求。')
        details = {}
        batches = [codes[i:i+DETAIL_BATCH_SIZE] for i in range(0, len(codes), DETAIL_BATCH_SIZE)]
        for start in range(0, len(batches), 5):
            await check_current()
            async with account_reads.transaction(client, bind, wait=True) as paced:
                for batch in batches[start:start+5]:
                    await check_current()
                    payload = await paced.get_character_details(batch)
                    details.update(character_queries.detail_entries(payload, batch))
        async with binding_lock(actor, bot):
            await check_current()
            if character_queries._epochs.get(account, 0) != epoch:
                raise CharacterDataError('绑定或缓存已变化，已丢弃旧更新结果。')
            snapshot = dict(roster=data['chars'], details=details, profile=data,
                            profile_checked_at=profile_checked_at, complete=True)
            character_queries.publish_snapshot(bind, snapshot)
            get_roster_service().invalidate_binding(bind, actor, bot, clear_image=False)
            profile._cache.pop(profile._cache_key(bind), None)
        return cached_profile(bind) or data


async def refresh_worker(bot, ev, policy, *, expected=None, automatic=False):
    from gsuid_core.logger import logger
    from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
    from ..nikke_character.service import CharacterDataError
    from ..nikke_roster.commands import allowed
    from ..nikke_roster.service import RosterCooldown
    from .service import load_client
    from .auth_state import RELOGIN, is_login_error, unavailable_message
    client = None
    committed = False
    key = str(ev.user_id), str(ev.bot_id)

    def notification_target():
        return _manual_requests.get(key, (bot, ev, policy))

    try:
        if not await allowed(policy, ev):
            return False
        client, bind = await load_client(ev.user_id, ev.bot_id)
        if client is None:
            bot, ev, policy = notification_target()
            if bot is not None:
                await bot.send(unavailable_message(bind), at_sender=True)
            return False
        if expected is not None and _revision(bind) != expected:
            return False
        async with asyncio.timeout(300):
            data = await refresh_panel(client, bind, actor=ev.user_id, bot=ev.bot_id,
                                       wait=automatic, policy=policy, event=ev)
        committed = True
        notify_bot, notify_ev, notify_policy = notification_target()
        if notify_bot is not None:
            from ..nikke_profile.commands import send_profile_image
            # Render exactly one information card from the data just committed.
            # This does not re-fetch or render all character cards.
            try:
                sent = await send_profile_image(notify_bot, notify_ev, client, bind, data, policy=notify_policy)
                if not sent:
                    await notify_bot.send('绑定、权限或资料已变化，已停止发送旧信息图，请重新查询。', at_sender=True)
            except Exception as exc:
                logger.warning(f'[AliceUID] refresh completion image failed error_type={type(exc).__name__}')
                await notify_bot.send('资料、全部角色练度与皮肤缓存已刷新，但信息图生成或发送失败；请使用信息命令重试。', at_sender=True)
        return True
    except (RosterCooldown, CharacterDataError) as exc:
        bot, ev, policy = notification_target()
        if bot is not None:
            await bot.send(str(exc), at_sender=True)
    except NikkeLoginRequired:
        bot, ev, policy = notification_target()
        if bot is not None:
            await bot.send(RELOGIN, at_sender=True)
    except NikkeApiError as exc:
        bot, ev, policy = notification_target()
        if bot is not None:
            await bot.send(RELOGIN if is_login_error(exc) else f'更新失败（{exc.code}），已停止请求；未替换原缓存。', at_sender=True)
    except Exception as exc:
        bot, ev, policy = notification_target()
        logger.error(f'[AliceUID] account prefetch failed error_type={type(exc).__name__}')
        if bot is not None:
            await bot.send('资料已缓存，但完成通知失败，请使用信息命令查询。' if committed else
                           '资料缓存更新失败，未替换原缓存，请稍后重试。', at_sender=True)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
    return False


def _track(key, revision, coroutine):
    task = asyncio.create_task(coroutine)
    _tasks[key] = task
    _task_revisions[key] = revision
    def done(completed):
        if _tasks.get(key) is completed:
            _tasks.pop(key, None)
            _task_revisions.pop(key, None)
            _manual_requests.pop(key, None)
        if not completed.cancelled():
            completed.exception()
    task.add_done_callback(done)
    return task


def cancel_prefetch(bind):
    key = _owner(bind)
    task = _tasks.get(key)
    if task is not None and _task_revisions.get(key) == _revision(bind):
        if task is not asyncio.current_task() and not task.done():
            task.cancel()


def schedule_login_prefetch(bind, group_id=None):
    from ..nikke_permissions.runtime import get_policy
    key, revision = _owner(bind), _revision(bind)
    current = _tasks.get(key)
    if current is not None and not current.done():
        if _task_revisions.get(key) == revision:
            return current
        current.cancel()
    _manual_requests.pop(key, None)
    event = SimpleNamespace(user_id=key[0], bot_id=key[1], group_id=group_id)
    return _track(key, revision, refresh_worker(None, event, get_policy(), expected=revision, automatic=True))


async def queue_refresh(bot, ev, policy):
    from ..nikke_roster.commands import allowed
    from .models import AliceBind
    if not await allowed(policy, ev):
        await bot.send('当前用户或群未开放妮姬查询，请联系管理员。', at_sender=True)
        return
    key = str(ev.user_id), str(ev.bot_id)
    async with _queue_locks.setdefault(key, asyncio.Lock()):
        bind = await AliceBind.get_bind(*key)
        if bind is None:
            from .auth_state import unavailable_message
            await bot.send(unavailable_message(None), at_sender=True)
            return
        revision = _revision(bind) if bind is not None else ''
        current = _tasks.get(key)
        if current is not None and not current.done():
            if _task_revisions.get(key) == revision:
                _manual_requests.setdefault(key, (bot, ev, policy))
                await bot.send('本人资料与角色数据正在缓存，请稍候；已合并重复请求。', at_sender=True)
                return
            current.cancel()
        _manual_requests[key] = (bot, ev, policy)
        await bot.send('正在刷新本人资料、全部角色练度与皮肤缓存；完成后发送最新信息图。', at_sender=True)
        _track(key, revision, refresh_worker(bot, ev, policy, expected=revision))
