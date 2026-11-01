"""Account-serialized roster/detail queries with binding-versioned caches."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import hashlib
import time
from typing import Callable

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from ..nikke_api.parser import StaticData
from .builder import build_character_context, integer, resolve_character


class CharacterCooldown(ValueError):
    pass


class CharacterNotOwned(ValueError):
    pass


class CharacterDataError(ValueError):
    pass


class CharacterQueryService:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic, cooldown: float = 5,
                 persistent=False, data_cache=None):
        self.clock = clock
        self.cooldown = cooldown
        self._locks: dict[tuple, asyncio.Lock] = {}
        self._last_fetch: dict[tuple, float] = {}
        self._rosters: dict[tuple, tuple[float, list[dict]]] = {}
        self._details: dict[tuple, tuple[float, dict, list[dict]]] = {}
        self.persistent=persistent or data_cache is not None
        self.data_cache=data_cache
        self._epochs={}
        self._ownership_checks = {}
        self._commanders = {}
        self._invalidations = {}
        self._views = {}
        self._view_idle = {}

    def store(self):
        if not self.persistent: return None
        if self.data_cache is None:
            from .cache import get_panel_cache
            self.data_cache=get_panel_cache()
        return self.data_cache

    @staticmethod
    def _account(bind) -> tuple:
        return (str(bind.game_id), str(bind.intl_open_id), int(bind.area_id))

    def _revision(self, bind) -> tuple:
        return self._account(bind) + (str(getattr(bind,'user_id','')), str(getattr(bind,'bot_id','')),
                                      hashlib.sha256(bind.cookie_enc.encode()).hexdigest())

    def invalidate(self, bind, *, clear_store=True) -> None:
        account=self._account(bind)
        self._invalidations[account] = self._invalidations.get(account, 0) + 1
        self._epochs[account]=self._epochs.get(account,0)+1
        store=self.store()
        if store is not None and clear_store:
            from .cache import panel_identity
            store.invalidate(panel_identity(bind))
        key = self._revision(bind)
        self._rosters.pop(key, None)
        self._ownership_checks.pop(key, None)
        for entry in [entry for entry in self._details if entry[:-1] == key]:
            self._details.pop(entry, None)

    @asynccontextmanager
    async def foreground_view(self, bind):
        account = self._account(bind)
        event = self._view_idle.setdefault(account, asyncio.Event())
        self._views[account] = self._views.get(account, 0) + 1
        event.clear()
        try:
            yield
        finally:
            self._views[account] -= 1
            if not self._views[account]:
                event.set()

    @asynccontextmanager
    async def background_publish(self, bind):
        account = self._account(bind)
        lock = self._locks.setdefault(account, asyncio.Lock())
        while True:
            if self._views.get(account, 0):
                await self._view_idle[account].wait()
            await lock.acquire()
            if not self._views.get(account, 0):
                break
            lock.release()
        try:
            yield
        finally:
            lock.release()

    @staticmethod
    def _detail_rows(payload: dict) -> list[dict]:
        # The endpoint's exact wrapper is validated against the reviewed source.
        rows = payload.get('character_details')
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise CharacterDataError('角色详情响应格式发生变化，请稍后重试并联系管理员。')
        return rows

    @staticmethod
    def roster_codes(roster):
        if not isinstance(roster, list) or not all(isinstance(row, dict) for row in roster):
            raise CharacterDataError('角色列表响应格式发生变化，请稍后重试。')
        codes = [integer(row.get('name_code')) for row in roster]
        if any(code is None or code <= 0 for code in codes) or len(codes) != len(set(codes)):
            raise CharacterDataError('角色列表存在无效或重复记录，请稍后重试。')
        return codes

    @classmethod
    def detail_entries(cls, payload, requested):
        if not isinstance(payload, dict):
            raise CharacterDataError('角色详情响应格式发生变化，请稍后重试。')
        rows = cls._detail_rows(payload)
        codes = [integer(row.get('name_code')) for row in rows]
        if len(codes) != len(set(codes)) or set(codes) != set(requested):
            raise CharacterDataError('接口未返回全部唯一匹配的角色详情，未替换原缓存。')
        effects = payload.get('state_effects')
        if effects is None:
            effects = []
        if not isinstance(effects, list) or not all(isinstance(row, dict) for row in effects):
            raise CharacterDataError('装备词条响应格式发生变化，请稍后重试。')
        return {str(code): dict(detail=row, effects=effects, checked_at=time.time()) for code, row in zip(codes, rows)}

    def publish_snapshot(self, bind, snapshot):
        """Caller holds the account and current-binding locks; publish atomically."""
        from .cache import panel_identity
        self.roster_codes(snapshot['roster'])
        store = self.store()
        if store is not None:
            store.write(panel_identity(bind), dict(snapshot, _area_id=int(bind.area_id)))
        account, revision = self._account(bind), self._revision(bind)
        self._epochs[account] = self._epochs.get(account, 0) + 1
        self._rosters[revision] = (self.clock(), snapshot['roster'])
        for key in [key for key in self._details if key[:-1] == revision]:
            self._details.pop(key, None)
        for code, saved in snapshot['details'].items():
            self._details[revision+(int(code),)] = (self.clock(), saved['detail'], saved['effects'])

    async def query(self, client, bind, name: str, static: StaticData, *, refresh: bool = False, ttl: int = 600,
                    equipment_items=None, skill_icons=None, current_check=None, publish_lock=None, ownership_notice=None) -> dict:
        from .aliases import current_aliases
        code = resolve_character(name, static, aliases=current_aliases())
        account, revision = self._account(bind), self._revision(bind)
        async with self._locks.setdefault(account, asyncio.Lock()), AsyncExitStack() as network_stack:
            epoch=self._epochs.get(account,0)
            from .cache import panel_identity
            store=self.store()
            identity=panel_identity(bind)
            snapshot=store.read(identity) if store is not None else {}
            if store is not None and (snapshot or store.latest_roster(identity, snapshot)[0]):
                self._rosters[revision]=(self.clock(),store.latest_roster(identity, snapshot)[1])
                for saved_code,saved in snapshot.get('details', {}).items():
                    if str(saved_code).isascii() and str(saved_code).isdigit() and isinstance(saved,dict):
                        if isinstance(saved.get('detail'),dict) and isinstance(saved.get('effects'),list):
                            self._details[revision+(int(saved_code),)]=(self.clock(),saved['detail'],saved['effects'])
            fetched = False
            detail_fetched = False
            network_client = client
            async def reserve():
                nonlocal fetched, network_client
                if fetched:
                    return
                now = self.clock()
                if account in self._last_fetch and now - self._last_fetch[account] < self.cooldown:
                    raise CharacterCooldown('练度刷新较频繁，请至少等待5秒后再查询。')
                self._last_fetch[account] = now
                if store is not None:
                    from ..nikke_roster.service import account_reads
                    network_client = await network_stack.enter_async_context(
                        account_reads.transaction(client, bind, wait=True))
                fetched = True
            def fresh(entry):
                return entry is not None and (store is not None or 0 <= self.clock() - entry[0] < max(0, ttl))
            try:
                roster_entry = self._rosters.get(revision)
                roster = roster_entry[1] if fresh(roster_entry) else None
                recovered = False
                roster_fetched = False
                community_roster = None
                community_checked_at = None
                fast_detail = None
                fast_target = False
                partial_roster = False

                async def fetch_roster():
                    nonlocal community_roster, community_checked_at
                    await reserve()
                    rows = await network_client.get_characters()
                    community_checked_at = time.time()
                    self.roster_codes(rows)
                    community_roster = rows
                    return rows

                cache_missing = roster is not None and not any(integer(row.get('name_code')) == code for row in roster)
                if (refresh and not cache_missing) or roster is None:
                    roster = await fetch_roster()
                    roster_fetched = True
                    if refresh and snapshot and any(integer(row.get('name_code')) == code for row in roster):
                        current = next(row for row in roster if integer(row.get('name_code')) == code)
                        base_roster = roster_entry[1] if fresh(roster_entry) else snapshot['roster']
                        roster = [row for row in base_roster if integer(row.get('name_code')) != code] + [current]
                        partial_roster = True
                self.roster_codes(roster)
                owned = next((row for row in roster if integer(row.get('name_code')) == code), None)
                if owned is None:
                    checked = self._ownership_checks.get(revision)
                    recently_checked = (not refresh and checked is not None and 0 <= self.clock()-checked[0] < self.cooldown
                                        and checked[1] == roster)
                    if not recently_checked:
                        if ownership_notice is not None:
                            await ownership_notice(static.name(code))
                        await reserve()
                        payload = await network_client.get_character_details([code])
                        if not isinstance(payload, dict):
                            raise CharacterDataError('角色详情响应格式发生变化，请稍后重试。')
                        rows = self._detail_rows(payload)
                        matches = [row for row in rows if integer(row.get('name_code')) == code]
                        if len(matches) > 1 or (not matches and rows):
                            raise CharacterDataError('接口未返回唯一匹配的角色详情，请稍后重试。')
                        if matches:
                            effects = payload.get('state_effects', [])
                            if effects is None:
                                effects = []
                            if not isinstance(effects, list) or not all(isinstance(row, dict) for row in effects):
                                raise CharacterDataError('装备词条响应格式发生变化，请稍后重试。')
                            detail = matches[0]
                            owned = {field:detail[field] for field in
                                     ('name_code','lv','combat','grade','core','costume_id','costume_tid') if field in detail}
                            owned['name_code'] = code
                            roster = [row for row in roster if integer(row.get('name_code')) != code] + [owned]
                            fast_detail = detail, effects
                            fast_target = recovered = True
                            # A single role proves its ownership, not a full-list refresh.
                            roster_fetched = False
                        else:
                            if not roster_fetched:
                                roster = await fetch_roster()
                                roster_fetched = True
                            owned = next((row for row in roster if integer(row.get('name_code')) == code), None)
                            if owned is not None:
                                raise CharacterDataError('社区显示已持有，但角色详情暂未返回，请稍后刷新该角色面板。')
                if roster_fetched:
                    # Commit ownership even if detail fetch fails or the role is absent.
                    # Release the binding lock before making another network request.
                    async with AsyncExitStack() as commit_stack:
                        if publish_lock is not None:
                            await commit_stack.enter_async_context(publish_lock)
                        if current_check is not None and not await current_check():
                            raise CharacterDataError('绑定或权限已变化，已停止保存和展示旧账号数据。')
                        if self._epochs.get(account, 0) != epoch:
                            raise CharacterDataError('面板已刷新，请重新查询；未保存旧结果。')
                        if store is not None:
                            saved = store.read(identity)
                            codes = {str(c) for c in self.roster_codes(roster)}
                            details = {k:v for k,v in saved.get('details', {}).items() if k in codes}
                            if recovered or owned is None:
                                details.pop(str(code), None)
                            list_stamp = store.latest_roster(identity, saved)[0] if partial_roster else community_checked_at
                            updated = dict(saved, roster=roster, details=details, roster_checked_at=list_stamp)
                            if partial_roster:
                                updated['row_checked_at'] = dict(saved.get('row_checked_at', {}), **{str(code):community_checked_at})
                            updated['complete'] = bool(saved.get('complete') and set(details) == codes)
                            if isinstance(updated.get('profile'), dict):
                                updated['profile'] = dict(updated['profile'], chars=roster)
                            store.write(identity, dict(updated, _area_id=int(bind.area_id)))
                        if roster_entry is not None and roster_entry[1] != roster:
                            self._epochs[account] = self._epochs.get(account, 0) + 1
                            epoch = self._epochs[account]
                        self._rosters[revision] = (self.clock(), roster)
                        self._ownership_checks[revision] = (self.clock(), community_roster)
                        owned_codes = set(self.roster_codes(roster))
                        for detail_key in list(self._details):
                            if detail_key[:-1] == revision and (detail_key[-1] not in owned_codes
                                                               or (recovered and detail_key[-1] == code)):
                                self._details.pop(detail_key, None)
                if owned is None:
                    from ..nikke_commands import command_prefix
                    prefix = command_prefix()
                    raise CharacterNotOwned(
                        f'当前社区数据中，绑定账号未持有「{static.name(code)}」。'
                        f'若刚获得该角色，社区数据可能尚未同步，请稍后使用 {prefix}刷新{static.name(code)}面板，'
                        f'或使用 {prefix}刷新面板 同步社区数据。')
                key = revision + (code,)
                detail_entry = self._details.get(key)
                if fast_detail is not None:
                    detail, effects = fast_detail
                    detail_fetched = True
                elif refresh or not fresh(detail_entry):
                    await reserve()
                    payload = await network_client.get_character_details([code])
                    if not isinstance(payload, dict):
                        raise CharacterDataError('角色详情响应格式发生变化，请稍后重试并联系管理员。')
                    # Never rely on response order and never use another role's
                    # first result when this requested name_code is absent.
                    matches = [row for row in self._detail_rows(payload) if integer(row.get('name_code')) == code]
                    if len(matches) != 1:
                        raise CharacterDataError('接口未返回唯一匹配的角色详情，请稍后重试。')
                    effects = payload.get('state_effects')
                    if effects is None:
                        effects = []
                    if not isinstance(effects, list) or not all(isinstance(row, dict) for row in effects):
                        raise CharacterDataError('装备词条响应格式发生变化，请稍后重试。')
                    detail, effects = matches[0], effects
                    detail_fetched = True
                    self._details[key] = (self.clock(), detail, effects)
                else:
                    _, detail, effects = detail_entry
                if publish_lock is not None:
                    await network_stack.enter_async_context(publish_lock)
                if current_check is not None and not await current_check():
                    raise CharacterDataError('绑定或权限已变化，已停止保存和展示旧账号数据。')
                if self._epochs.get(account,0)!=epoch:
                    self._rosters.pop(revision,None)
                    self._details.pop(key,None)
                    raise CharacterDataError('面板已刷新，请重新查询；未保存旧结果。')
                if store is not None and (fetched or not snapshot):
                    # Store raw JSON data, not prepared images, cookies or tokens.
                    saved=store.read(identity)
                    saved_details=saved.get('details',{})
                    old_checked = saved_details.get(str(code), {}).get('checked_at', saved.get('saved_at'))
                    saved_details[str(code)]={'detail':detail,'effects':effects,
                                              'checked_at':time.time() if detail_fetched else old_checked}
                    updated = dict(saved, roster=roster, details=saved_details)
                    row_checks = dict(saved.get('row_checked_at', {}))
                    if fast_target or refresh:
                        row_checks[str(code)] = time.time()
                    updated['row_checked_at'] = row_checks
                    if fast_target:
                        updated['full_refresh_pending'] = True
                    updated['complete'] = bool(not fast_target and saved.get('complete') and set(saved_details) == {str(c) for c in self.roster_codes(roster)})
                    if isinstance(updated.get('profile'), dict):
                        updated['profile'] = dict(updated['profile'], chars=roster)
                    store.write(identity, dict(updated, _area_id=int(bind.area_id)))
                    if refresh:
                        self._epochs[account] = self._epochs.get(account, 0) + 1
                        epoch = self._epochs[account]
                self._rosters[revision] = (self.clock(), roster)
                self._details[key] = (self.clock(), detail, effects)
                context = build_character_context(owned, detail, effects, static,
                                               area_label=client.region.label,
                                               nickname=bind.nickname or '',
                                               equipment_items=equipment_items, skill_icons=skill_icons)
                from ..nikke_resource.cache import read_metadata
                from ..nikke_login.regions import saved_role_matches
                profile_entries = [(snapshot.get('profile_checked_at',snapshot.get('saved_at',0)), snapshot.get('profile') or {})]
                if store is not None:
                    light = read_metadata(store.path(identity, 'profile.json'))
                    profile_entries.append((light.get('checked_at',0),light.get('profile') or {}))
                    avatar = read_metadata(store.path(identity, 'commander.json'))
                    profile_entries.append((avatar.get('checked_at',0), {'saved': avatar.get('saved')}))
                profiles = [p for _,p in sorted(profile_entries,key=lambda r: r[0] if type(r[0]) in (int,float) else 0,reverse=True)
                            if isinstance(p,dict)]
                outpost_profile = next((p for p in profiles if isinstance(p.get('outpost'),dict)
                                        and isinstance(p.get('basic'),dict)
                                        and str(p['basic'].get('area_id',bind.area_id))==str(bind.area_id)), {})
                context['recycle_room_researches'] = (outpost_profile.get('outpost') or {}).get('recycle_room_researches')
                saved_role = next((p.get('saved') for p in profiles
                                   if isinstance(p, dict) and isinstance(p.get('saved'), dict)
                                   and p['saved'].get('icon') is not None
                                   and saved_role_matches(p['saved'], client.region)), None)
                if saved_role is None:
                    remembered = self._commanders.get(revision)
                    if remembered and 0 <= self.clock()-remembered[0] < 300 and not refresh:
                        saved_role = remembered[1]
                    elif hasattr(client, 'get_saved_role_info'):
                        try:
                            if store is not None and not fetched:
                                from ..nikke_roster.service import account_reads
                                network_client = await network_stack.enter_async_context(
                                    account_reads.transaction(client, bind, wait=True))
                            role = await network_client.get_saved_role_info()
                            if current_check is not None and not await current_check():
                                raise CharacterDataError('绑定或权限已变化，已停止保存和展示旧账号数据。')
                            saved_role = role if saved_role_matches(role, client.region) else {}
                            self._commanders[revision] = (self.clock(), saved_role)
                            if store is not None and saved_role.get('icon') is not None:
                                import json
                                from ..nikke_resource.cache import atomic_write
                                atomic_write(store.path(identity, 'commander.json'), json.dumps(
                                    {'checked_at': time.time(), 'saved': saved_role}, ensure_ascii=False).encode())
                        except NikkeLoginRequired:
                            raise
                        except NikkeApiError:
                            saved_role = {}
                            self._commanders[revision] = (self.clock(), saved_role)
                saved_role = saved_role or {}
                context['commander_icon_id'] = saved_role.get('icon')
                context.update(commander_name=bind.nickname or '昵称未知',
                               commander_uid=getattr(bind,'uid','') or '未知',
                               commander_region=client.region.label)
                context['_panel_epoch']=epoch
                context['_needs_full_refresh'] = fast_target or bool(snapshot.get('full_refresh_pending'))
                if store is not None:
                    context['_cache_identity']=identity
                    context['_snapshot_saved_at']=store.read(identity).get('saved_at')
                    context['_detail_checked_at']=store.read(identity).get('details',{}).get(str(code),{}).get('checked_at')
                return context
            except NikkeLoginRequired:
                self.invalidate(bind, clear_store=False)
                raise
            except NikkeApiError as exc:
                if exc.code in (401, 403, 300001):
                    self.invalidate(bind, clear_store=False)
                raise

    def context_current(self,context,bind):
        return '_panel_epoch' not in context or context['_panel_epoch']==self._epochs.get(self._account(bind),0)


character_queries = CharacterQueryService(persistent=True)
