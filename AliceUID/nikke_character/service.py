"""Account-serialized roster/detail queries with binding-versioned caches."""
from __future__ import annotations

import asyncio
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
        return self._account(bind) + (hashlib.sha256(bind.cookie_enc.encode()).hexdigest(),)

    def invalidate(self, bind) -> None:
        account=self._account(bind)
        self._epochs[account]=self._epochs.get(account,0)+1
        store=self.store()
        if store is not None:
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

    async def query(self, client, bind, name: str, static: StaticData, *, refresh: bool = False, ttl: int = 600,
                    equipment_items=None, skill_icons=None) -> dict:
        from .aliases import current_aliases
        code = resolve_character(name, static, aliases=current_aliases())
        account, revision = self._account(bind), self._revision(bind)
        async with self._locks.setdefault(account, asyncio.Lock()):
            epoch=self._epochs.get(account,0)
            from .cache import panel_identity
            store=self.store()
            identity=panel_identity(bind)
            snapshot=store.read(identity) if store is not None and not refresh else {}
            if snapshot:
                self._rosters[revision]=(self.clock(),snapshot['roster'])
                for saved_code,saved in snapshot['details'].items():
                    if str(saved_code).isascii() and str(saved_code).isdigit() and isinstance(saved,dict):
                        if isinstance(saved.get('detail'),dict) and isinstance(saved.get('effects'),list):
                            self._details[revision+(int(saved_code),)]=(self.clock(),saved['detail'],saved['effects'])
            fetched = False
            def reserve():
                nonlocal fetched
                if fetched:
                    return
                now = self.clock()
                if account in self._last_fetch and now - self._last_fetch[account] < self.cooldown:
                    raise CharacterCooldown('练度刷新较频繁，请至少等待5秒后再查询。')
                self._last_fetch[account] = now
                fetched = True
            def fresh(entry):
                return entry is not None and (store is not None or 0 <= self.clock() - entry[0] < max(0, ttl))
            try:
                roster_entry = self._rosters.get(revision)
                if refresh or not fresh(roster_entry):
                    reserve()
                    roster = await client.get_characters()
                    if not isinstance(roster, list) or not all(isinstance(row, dict) and integer(row.get('name_code')) not in (None, 0) for row in roster):
                        raise CharacterDataError('角色列表响应格式发生变化，请稍后重试并联系管理员。')
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
                    reserve()
                    payload = await client.get_character_details([code])
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
                if self._epochs.get(account,0)!=epoch:
                    self._rosters.pop(revision,None)
                    self._details.pop(key,None)
                    raise CharacterDataError('面板已刷新，请重新查询；未保存旧结果。')
                if store is not None and (fetched or not snapshot):
                    # Store raw JSON data, not prepared images, cookies or tokens.
                    saved=store.read(identity)
                    saved_details=saved.get('details',{})
                    saved_details[str(code)]={'detail':detail,'effects':effects}
                    store.write(identity,{'roster':roster,'details':saved_details})
                context = build_character_context(owned, detail, effects, static,
                                               area_label=client.region.label,
                                               nickname=bind.nickname or '',
                                               equipment_items=equipment_items, skill_icons=skill_icons)
                context.update(commander_name=bind.nickname or '昵称未知',
                               commander_uid=getattr(bind,'uid','') or '未知',
                               commander_region=client.region.label)
                context['_panel_epoch']=epoch
                if store is not None: context['_cache_identity']=identity
                return context
            except NikkeLoginRequired:
                self.invalidate(bind)
                raise
            except NikkeApiError as exc:
                if exc.code in (401, 403, 300001):
                    self.invalidate(bind)
                raise

    def context_current(self,context,bind):
        return '_panel_epoch' not in context or context['_panel_epoch']==self._epochs.get(self._account(bind),0)


character_queries = CharacterQueryService(persistent=True)
