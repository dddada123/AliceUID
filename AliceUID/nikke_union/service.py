"""Verified guild queries, with official season routing and historical fallback."""
from __future__ import annotations

import asyncio
import hashlib
import time

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from .builder import UnionDataError, build_union_context, identifier, normalize_attacks, normalize_members

PREFIX = '/api/game/proxy/Game/'


class UnionCooldown(ValueError):
    pass


class UnionService:
    def __init__(self, *, clock=time.monotonic, wall_clock=time.time, sleeper=asyncio.sleep, ttl=None, cooldown=5,
                 season_loader=None, history=None, persistent=False):
        self.clock, self.wall_clock, self.sleeper = clock, wall_clock, sleeper
        self.ttl, self.cooldown = ttl, cooldown
        self._locks, self._cache, self._last_remote = {}, {}, {}
        self._guild_locks, self._guild_cache = {}, {}
        self.season_loader, self.history, self.persistent = season_loader, history, persistent

    def history_store(self):
        if self.history is None and self.persistent:
            from ..nikke_config.config import MAIN_PATH
            from .history import UnionHistory
            self.history = UnionHistory(MAIN_PATH / 'cache' / 'union_history')
        return self.history

    def cache_ttl(self):
        if self.ttl is not None:
            return max(0,int(self.ttl))
        try:
            from ..nikke_config.config import AliceUIDConfig
            return max(0,min(3600,int(AliceUIDConfig.get_config('AliceUID_UnionCacheSeconds').data)))
        except (ImportError,AttributeError,KeyError,TypeError,ValueError):
            return 180

    @staticmethod
    def account(bind):
        return str(bind.game_id), str(bind.intl_open_id), int(bind.area_id)

    def cache_key(self, bind):
        # Fingerprint encrypted binding material only; never persist or log it.
        return self.account(bind) + (hashlib.sha256(bind.cookie_enc.encode()).hexdigest(),)

    def invalidate(self, bind):
        self._cache.pop(self.cache_key(bind), None)

    @staticmethod
    def _payload(response):
        if not isinstance(response, dict) or not isinstance(response.get('data'), dict):
            raise UnionDataError('联盟响应结构变化，无法统计；不会按0刀处理。')
        return response['data']

    async def _fetch(self, client, bind, account, season, *, refresh=False):
        async def remote(endpoint, body):
            last = self._last_remote.get(account)
            if last is not None:
                delay = self.cooldown - (self.clock() - last)
                if delay > 0:
                    await self.sleeper(delay)
            self._last_remote[account] = self.clock()
            return self._payload(await client._request('POST', PREFIX + endpoint, body))

        warnings = []
        guild_id, guild_name, members = None, '当前联盟', None
        try:
            guild = await remote('GetMyGuildInfo', {})
            # Exact reviewed guild wrapper is resolved by guild_info() below.
            info = guild_info(guild)
            if info is not None:
                guild_id = identifier(info.get('guild_id'), '联盟标识')
                name = info.get('guild_name')
                if isinstance(name, str) and name.strip():
                    guild_name = name
        except NikkeLoginRequired:
            raise
        except NikkeApiError as exc:
            if exc.code in (401, 403, 429, 300001):
                raise
            warnings.append('联盟信息暂不可用；仅统计已出刀成员，0刀未知。')
        async def load_snapshot():
            members = None
            notes = list(warnings)
            if guild_id is not None:
                try:
                    payload = await remote('GetGuildMembers', {'guild_id': guild_id, 'nikke_area_id': str(client.region.area_id)})
                    members = normalize_members(payload)
                except NikkeLoginRequired:
                    raise
                except NikkeApiError as exc:
                    if exc.code in (401, 403, 429, 300001):
                        raise
                    notes.append('成员名单暂不可用；仅统计已出刀成员，0刀未知。')
            else:
                notes.append('未取得可确认的联盟信息；仅统计已出刀成员，0刀未知。')
            body = {'intl_open_id': client.credentials.openid, 'nikke_area_id': client.region.area_id}
            if guild_id is not None:
                body['guild_id'] = guild_id
            from .season import season_context
            group = (str(bind.game_id), int(bind.area_id), guild_id)
            store = self.history_store()
            previous = store.read(group, season['id']) if store and guild_id else None
            if previous is None and guild_id:
                shared=self._guild_cache.get((*group,season['id'],season['active'],season['live_endpoint']))
                previous=shared[1] if shared else None
            historical = not season['live_endpoint']
            endpoint, level_endpoint = 'GetUnionRaidData', 'GetUnionRaidLevelInfo'
            if historical:
                if guild_id is None:
                    raise UnionDataError('无法确认本人联盟，不能读取历史会战。')
                body = {'area_id': int(bind.area_id), 'guild_id': guild_id, 'season_id': str(season['id'])}
                endpoint, level_endpoint = 'GetUnionRaidDataOfGuildSeason', 'GetUnionRaidLevelDataOfGuildSeason'
            local = False
            try:
                if (not refresh and historical and previous and previous.get('finalized')
                        and previous.get('attacks') and previous.get('level_payload',{}).get('level_info')):
                    # Calendar/own guild/current roster were checked above.
                    # Only a successfully fetched, settled season is frozen.
                    attacks,level=previous['attacks'],previous['level_payload']
                    local=True
                else:
                    attacks = normalize_attacks(await remote(endpoint, body))
                    level = await remote(level_endpoint, body)
            except NikkeLoginRequired:
                raise
            except NikkeApiError as exc:
                # A rejected login/rate limit never unlocks cached private data.
                if (exc.code in (401, 403, 429, 300001) or season['active'] or not previous
                        or str(bind.intl_open_id) not in (members or {})):
                    raise
                attacks, level = previous['attacks'], previous['level_payload']
                local = True
            if not season['active'] and previous and str(bind.intl_open_id) in (members or {}):
                if not attacks and previous.get('attacks'):
                    attacks = previous['attacks']
                    local = True
                if not level.get('level_info') and previous.get('level_payload', {}).get('level_info'):
                    level = previous['level_payload']
                    local = True
            validate_level(level)
            verified_members = members
            members_reference = False
            if not season['active']:
                # Prefer a roster captured in this season. A first offseason
                # query must not discard the complete roster we just fetched:
                # keep it as an explicitly labelled comparison, not as proof
                # that a newly joined member participated last season.
                season_members = previous.get('members') if previous else None
                if season_members and not previous.get('members_reference', False):
                    members = dict(season_members)
                elif verified_members is not None:
                    members = dict(verified_members)
                    members_reference = True
                    notes.append('按当前完整成员名单对照上期记录；0/3表示该成员无上期Day2记录，新入会成员不据此认定上期实际漏刀。')
                else:
                    members = None
                if members is not None:
                    # Historical attackers may since have left the guild.
                    # Preserve their real records alongside the roster.
                    for attack in attacks:
                        members.setdefault(attack['openid'], attack['nickname'])
                if members is None:
                    notes.append('历史参战名单以出刀记录为准；未取得上期完整名单，0刀未知。')
            fetched_at = previous['fetched_at'] if local else self.wall_clock()
            snapshot={'attacks': attacks, 'members': members, 'guild_name': guild_name,
                      'warnings': notes, 'fetched_at': fetched_at, '_cached_at':self.clock(), 'level_payload':level,
                      '_verified_members': verified_members, 'members_reference': members_reference,
                      'finalized':bool(historical and attacks and level.get('level_info')
                                       and (not local or previous.get('finalized',False))),
                      'season':season_context(season, local=local),
                      '_group': (*group, season['id'], season['active'], season['live_endpoint']),
                      '_period':(season['id'],season['active'],season['live_endpoint'])}
            if local:
                notes.append('复用本联盟该赛季已验证历史快照；数据时间见卡片，可用刷新指令主动重新查询。')
            if not attacks and not level.get('level_info'):
                notes.append('社区未返回本联盟该赛季记录，本地也没有可用快照；未将空响应当成Day1或0刀。')
            build_union_context(attacks,members,own_openid=bind.intl_open_id,fetched_at=snapshot['fetched_at'])
            if store and guild_id and not local:
                store.save(group,season['id'],snapshot)
            return snapshot
        if guild_id is None:
            return await load_snapshot()
        # Each new account first confirms its own current guild. Only share
        # after that and only when the cached verified roster includes it.
        group=(str(bind.game_id),int(bind.area_id),guild_id,season['id'],season['active'],season['live_endpoint'])
        async with self._guild_locks.setdefault(group,asyncio.Lock()):
            cached=self._guild_cache.get(group)
            if not refresh and cached and 0<=self.clock()-cached[0]<self.cache_ttl():
                if str(bind.intl_open_id) in (cached[1].get('_verified_members') or {}):
                    return cached[1]
            snapshot=await load_snapshot()
            if str(bind.intl_open_id) in (snapshot.get('_verified_members') or {}):
                self._guild_cache[group]=(self.clock(),snapshot)
            return snapshot

    async def _snapshot(self, client, bind, *, refresh=False):
        account, key = self.account(bind), self.cache_key(bind)
        # Reject identity mismatch before consulting any cached personal data.
        if (str(client.region.game_id), str(client.credentials.openid), int(client.region.area_id)) != account:
            raise UnionDataError('客户端与本人绑定不一致，已停止查询。')
        from .season import load_seasons, select_season
        season = select_season(await (self.season_loader or load_seasons)(), self.wall_clock())
        period = (season['id'],season['active'],season['live_endpoint'])
        async with self._locks.setdefault(account, asyncio.Lock()):
            cached = self._cache.get(key)
            if not refresh and cached is not None and cached[1].get('_period') == period and 0 <= self.clock() - cached[0] < self.cache_ttl() and 0 <= self.clock() - cached[1]['_cached_at'] < self.cache_ttl():
                data = cached[1]
                shared = self._guild_cache.get(data.get('_group'))
                if shared and str(bind.intl_open_id) in (shared[1].get('_verified_members') or {}):
                    data = shared[1]
                    self._cache[key] = cached[0], data
            else:
                now = self.clock()
                if account in self._last_remote and now - self._last_remote[account] < self.cooldown:
                    raise UnionCooldown('出刀刷新较频繁，请至少等待5秒后再查询。')
                try:
                    data = await self._fetch(client, bind, account, season, refresh=refresh)
                    # Validate membership consistency before publishing cache.
                    build_union_context(data['attacks'], data['members'], own_openid=bind.intl_open_id,
                                        fetched_at=data['fetched_at'])
                    self._cache[key] = self.clock(), data
                except NikkeLoginRequired:
                    self.invalidate(bind)
                    raise
                except NikkeApiError as exc:
                    if exc.code in (401, 403, 300001):
                        self.invalidate(bind)
                    raise
            return data

    async def query(self, client, bind, *, view='quick', day=None, refresh=False, static=None, character_map=(), target_rank=None):
        data = await self._snapshot(client,bind,refresh=refresh)
        requested_day = day
        if day is None:
            day = 1 if view in ('detail','missing','tails') or not data['attacks'] or any(a['day'] == 1 for a in data['attacks']) else 0
        context = build_union_context(**{k:data[k] for k in ('attacks','members','guild_name','warnings','fetched_at')}, own_openid=bind.intl_open_id, day=day, view=view,
                                      static=static, character_map=character_map,
                                      members_reference=data.get('members_reference', False),
                                      raid_active=data['season'].get('raid_active', False), target_rank=target_rank)
        if requested_day == 1 and not context['day2_active']:
            context['warnings'].append('当前没有Day2出刀记录，Day2是否激活未知；不据此断言本期已开打。')
        context.update(data['season'])
        context['records_available'] = bool(data['attacks'])
        if not context['records_available']:
            # An empty endpoint is not evidence of Day1, Day2 or 32 zero-hit
            # players. Keep season/status visible without inventing a phase.
            context.update(title='会战记录',rows=[],missing=[],tails=[],details=[],
                           damage_leaders=[],kill_leaders=[],counts={},total_attacks=0,
                           members_known=False,members_reference=False,coverage='出刀记录暂不可用，0刀未知',
                           completion='暂无可确认的出刀记录')
        context.update(_snapshot_token=data.setdefault('_card_token', object()),
                       commander_name=getattr(bind,'nickname','') or '昵称未知',
                       commander_uid=getattr(bind,'uid','') or '未知',
                       commander_region=client.region.label,
                       cache_seconds=self.cache_ttl())
        return context

    def context_current(self, context, bind):
        """A later snapshot/revocation must prevent old in-flight card publication."""
        token = context.get('_snapshot_token')
        if token is None:
            return True
        cached = self._cache.get(self.cache_key(bind))
        return cached is not None and cached[1].get('_card_token') is token

    async def query_bosses(self, client, bind, *, refresh=False):
        from ..nikke_status.builder import build_bosses
        data=await self._snapshot(client,bind,refresh=refresh)
        context=build_bosses(data.get('level_payload'),bind=bind,region=client.region,
                             fetched_at=data['fetched_at'],ttl=self.cache_ttl(),guild_name=data['guild_name'])
        context['notes'].extend(data.get('warnings',[]))
        context.update(data['season'])
        if not context['available']:
            context['notes'] = [note for note in context['notes'] if '未以旧赛季' not in note]
            context['phase'] = '该赛季暂无可用血量记录'
        if not context['raid_active'] and context['available']:
            context['notes'].append('以上为上一期结束前的血量记录，并非当前实时血量。')
        return context


def guild_info(payload):
    """Only consume the reviewed wrapper; unknown wrappers are not guessed."""
    if 'card' not in payload:
        raise UnionDataError('联盟信息响应缺少card，无法确认名单；请联系管理员。')
    card = payload['card']
    if card is None:
        return None
    if not isinstance(card, dict):
        raise UnionDataError('联盟信息card格式异常。')
    identifier(card.get('guild_id'), '联盟标识')
    return card


def validate_level(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('level_info'), list):
        raise UnionDataError('联盟Boss进度响应异常，无法确认当前进度。')
    from .builder import integer
    for level in payload['level_info']:
        if not isinstance(level, dict) or not isinstance(level.get('boss_info'), list):
            raise UnionDataError('联盟Boss进度结构异常。')
        for boss in level['boss_info']:
            if not isinstance(boss, dict):
                raise UnionDataError('联盟Boss血量格式异常。')
            maximum = integer(boss.get('max_hp'), 'Boss最大血量')
            current = integer(boss.get('current_hp'), 'Boss当前血量')
            if maximum and current > maximum:
                raise UnionDataError('联盟Boss血量超出范围。')


union_queries = UnionService(persistent=True)
