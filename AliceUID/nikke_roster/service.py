"""Owned-account reads: serialized, paced, bounded and never retried."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import time
from .builder import build_roster_context, fingerprint
from .cache import RosterCache, identity
from .draw import draw_roster, prepare_images
from ..nikke_render.theme import get_card_theme_mode as get_card_theme

RENDER_VERSION = "alice-icons10-v102-game-badges"


class RosterCooldown(ValueError):
    pass


class AccountReads:
    """Shared by roster and panel refresh; adapters may use this for other reads."""
    def __init__(self, *, clock=time.monotonic, sleep=asyncio.sleep):
        self.clock, self.sleep = clock, sleep
        self.locks, self.last_batch, self.last_request = {}, {}, {}
        self.slots = asyncio.Semaphore(2)

    @staticmethod
    def account(bind):
        return str(bind.game_id), str(bind.intl_open_id), str(bind.area_id)

    @asynccontextmanager
    async def transaction(self, client, bind, *, wait=False):
        account = self.account(bind)
        async with self.locks.setdefault(account, asyncio.Lock()):
            now = self.clock()
            if account in self.last_batch and now - self.last_batch[account] < 5:
                if not wait:
                    raise RosterCooldown('查询较频繁，请至少等待5秒后重试。')
                await self.sleep(5-(now-self.last_batch[account]))
                now=self.clock()
            self.last_batch[account] = now
            try:
                async with self.slots:
                    yield PacedClient(client, self, account)
            finally:
                # Failed attempts reserve cooldown too; no automatic retry.
                self.last_batch[account] = self.clock()


class PacedClient:
    def __init__(self, client, gate, account):
        self.client, self.gate, self.account = client, gate, account
        self.region = client.region
        self.calls = 0

    def __getattr__(self, name):
        if not name.startswith('get_'):
            raise AttributeError(name)
        async def call(*args, **kwargs):
            if self.calls >= 5:
                raise ValueError('面板刷新请求预算已用尽')
            self.calls += 1
            gate = self.gate
            remaining = 5 - (gate.clock() - gate.last_request.get(self.account, -1e20))
            if remaining > 0:
                await gate.sleep(remaining)
            gate.last_request[self.account] = gate.clock()
            return await getattr(self.client, name)(*args, **kwargs)
        return call


account_reads = AccountReads()


class RosterService:
    def __init__(self, cache, resources, *, reads=None, renderer=draw_roster):
        self.cache, self.resources = cache, resources
        self.reads, self.renderer = reads or account_reads, renderer
        self.epochs = {}

    async def prepare(self, client, bind, actor, bot):
        key, owner = identity(actor, bot, bind)
        epoch = self.epochs.get(key, 0)
        async with self.reads.transaction(client, bind) as paced:
            basic = await paced.get_basic_info()
            if not isinstance(basic, dict) or str(basic.get('area_id', bind.area_id)) != str(bind.area_id):
                self.cache.invalidate_key(key)
                raise ValueError('资料区服与绑定区服不一致，已停止生成。')
            owned = await paced.get_characters()
            uid = str(getattr(bind, 'uid', '') or '')
            if not uid:
                from ..nikke_login.regions import saved_role_matches
                saved = await paced.get_saved_role_info()
                if saved_role_matches(saved, client.region):
                    uid = str(saved.get('role_id') or '')
            static = self.resources.load_static()
            if not static.characters:
                # Static character table only, and only when absent. No version checks.
                await self.resources.update_tables(targets=['nikke_list_zh-TW_v2.json'])
                static = self.resources.load_static()
            if not static.characters:
                raise ValueError('角色静态资料缺失，无法安全生成完整卡片。')
            context = build_roster_context(basic, owned, static, nickname=bind.nickname,
                                           uid=uid, area_label=client.region.label)
            from ..nikke_render.fonts import resolve_font
            from ..nikke_render.language import get_card_language
            context.update(card_theme=get_card_theme(), render_version=RENDER_VERSION,
                           font_fingerprint=resolve_font().fingerprint, card_language=get_card_language())
            from ..nikke_render.glass_settings import capture_glass
            context=capture_glass(context)
            semantic = fingerprint(context)
            meta = self.cache.metadata(key)
            if meta and meta.get('semantic') != semantic:
                self.cache.invalidate_key(key)
            context = await prepare_images(context, self.resources.images)
            # Public cache content/fallback changes affect image reuse too.
            digest_context = dict(context, cards=[{k: v for k, v in row.items() if k != 'icon_source'} for row in context['cards']])
            digest = fingerprint(digest_context)
            cached = self.cache.lookup(key, digest, owner)
            if cached is not None:
                return cached
            image = await self.renderer(context)
            if self.epochs.get(key, 0) != epoch:
                raise ValueError('资料已刷新，请重新请求卡片。')
            return self.cache.store(key, digest, owner, image, semantic=semantic)

    def mark_sent(self, prepared):
        return self.cache.mark_sent(prepared)

    def invalidate_binding(self, bind, actor=None, bot=None):
        actor = str(actor if actor is not None else bind.user_id)
        bot = str(bot if bot is not None else bind.bot_id)
        key, _ = identity(actor, bot, bind)
        self.epochs[key] = self.epochs.get(key, 0) + 1
        self.cache.invalidate_key(key)

    def invalidate_actor(self, actor, bot):
        self.cache.invalidate_actor(actor, bot)


_service = None


def get_roster_service():
    global _service
    if _service is None:
        from ..nikke_config.config import MAIN_PATH
        from ..nikke_resource.service import get_resources
        _service = RosterService(RosterCache(MAIN_PATH / 'cache' / 'roster'), get_resources())
    return _service


def invalidate_binding(bind):
    get_roster_service().invalidate_binding(bind)


def invalidate_actor(actor, bot):
    get_roster_service().invalidate_actor(actor, bot)


def revoke_cached_binding(bind, actor, bot):
    """Erase only this actor's derived cards, without constructing a downloader."""
    if _service is not None:
        if bind is not None:
            _service.invalidate_binding(bind, actor=str(actor), bot=str(bot))
        _service.invalidate_actor(str(actor), str(bot))
        return
    from ..nikke_config.config import MAIN_PATH
    root = MAIN_PATH / 'cache' / 'roster'
    if root.exists():
        RosterCache(root).invalidate_actor(str(actor), str(bot))


def mark_sent(prepared):
    return get_roster_service().mark_sent(prepared)
