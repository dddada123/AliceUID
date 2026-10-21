"""Account-serialized roster/detail queries with binding-versioned caches."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
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
        self._epochs[account]=self._epochs.get(account,0)+1
        store=self.store()
        if store is not None and clear_store:
            from .cache import panel_identity
            store.invalidate(panel_identity(bind))
        key = self._revision(bind)
        self._rosters.pop(key, None)
        for entry in [entry for entry in self._details if entry[:-1] == key]:
            self._details.pop(entry, None)

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
        return {str(code): dict(detail=row, effects=effects) for code, row in zip(codes, rows)}

    def publish_snapshot(self, bind, snapshot):
        """Caller holds the account and current-binding locks; publish atomically."""
        from .cache import panel_identity
        self.roster_codes(snapshot['roster'])
        store = self.store()
        if store is not None:
            store.write(panel_identity(bind), snapshot)
        account, revision = self._account(bind), self._revision(bind)
        self._epochs[account] = self._epochs.get(account, 0) + 1
        self._rosters[revision] = (self.clock(), snapshot['roster'])
        for key in [key for key in self._details if key[:-1] == revision]:
            self._details.pop(key, None)
        for code, saved in snapshot['details'].items():
            self._details[revision+(int(code),)] = (self.clock(), saved['detail'], saved['effects'])

    async def query(self, client, bind, name: str, static: StaticData, *, refresh: bool = False, ttl: int = 600,
                    equipment_items=None, skill_icons=None, current_check=None, publish_lock=None) -> dict:
        from .aliases import current_aliases
        code = resolve_character(name, static, aliases=current_aliases())
        account, revision = self._account(bind), self._revision(bind)
        async with self._locks.setdefault(account, asyncio.Lock()), AsyncExitStack() as network_stack:
            epoch=self._epochs.get(account,0)
            from .cache import panel_identity
            store=self.store()
            identity=panel_identity(bind)
            snapshot=store.read(identity) if store is not None else {}
            if snapshot:
                self._rosters[revision]=(self.clock(),snapshot['roster'])
                for saved_code,saved in snapshot['details'].items():
                    if str(saved_code).isascii() and str(saved_code).isdigit() and isinstance(saved,dict):
                        if isinstance(saved.get('detail'),dict) and isinstance(saved.get('effects'),list):
                            self._details[revision+(int(saved_code),)]=(self.clock(),saved['detail'],saved['effects'])
            fetched = False
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
                if refresh or not fresh(roster_entry):
                    await reserve()
                    roster = await network_client.get_characters()
                    if not isinstance(roster, list) or not all(isinstance(row, dict) and integer(row.get('name_code')) not in (None, 0) for row in roster):
                        raise CharacterDataError('角色列表响应格式发生变化，请稍后重试并联系管理员。')
                    if refresh and snapshot:
                        current = next((row for row in roster if integer(row.get('name_code')) == code), None)
                        if current is not None:
                            roster = [row for row in snapshot['roster'] if integer(row.get('name_code')) != code] + [current]
                    self._rosters[revision] = (self.clock(), roster)
                else:
                    roster = roster_entry[1]
                owned_rows = [row for row in roster if integer(row.get('name_code')) == code]
                if len(owned_rows) > 1:
                    raise CharacterDataError('角色列表存在重复记录，无法确认唯一角色，请稍后重试。')
                owned = owned_rows[0] if owned_rows else None
                if owned is None:
                    raise CharacterNotOwned(f'当前绑定账号未持有「{static.name(code)}」，不会请求该角色详情。')
                key = revision + (code,)
                detail_entry = self._details.get(key)
                if refresh or not fresh(detail_entry):
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
                    saved_details[str(code)]={'detail':detail,'effects':effects}
                    updated = dict(saved, roster=roster, details=saved_details)
                    if isinstance(updated.get('profile'), dict):
                        updated['profile'] = dict(updated['profile'], chars=roster)
                    store.write(identity, updated)
                    if refresh:
                        self._epochs[account] = self._epochs.get(account, 0) + 1
                        epoch = self._epochs[account]
                context = build_character_context(owned, detail, effects, static,
                                               area_label=client.region.label,
                                               nickname=bind.nickname or '',
                                               equipment_items=equipment_items, skill_icons=skill_icons)
                context.update(commander_name=bind.nickname or '昵称未知',
                               commander_uid=getattr(bind,'uid','') or '未知',
                               commander_region=client.region.label)
                context['_panel_epoch']=epoch
                if store is not None:
                    context['_cache_identity']=identity
                    context['_snapshot_saved_at']=store.read(identity).get('saved_at')
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
