"""GsCore wiring: public catalog fetch and opt-in automatic redemption jobs."""
from __future__ import annotations

import asyncio
from .store import Store
from .catalog import Catalog
from .service import Redemptions
from .commands import Commands, register
from .models import revision

_commands = None
_startup = None


def setup(policy, scheduler=None):
    global _commands, _startup
    if _commands is not None:
        return _commands
    from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
    from ..nikke_commands import command_prefix
    from ..nikke_user.models import AliceBind
    from ..nikke_user.service import load_client
    from ..nikke_message import send_with_forward
    if scheduler is None:
        from gsuid_core.aps import scheduler
    store = Store(MAIN_PATH / 'cdk.sqlite3')
    catalog = Catalog(store)

    async def allowed(ev):
        return policy.user_allowed(ev.user_id) and await policy.query_allowed(getattr(ev, 'group_id', None))

    async def current(ev, bind):
        actual = await AliceBind.get_bind(ev.user_id, ev.bot_id)
        return actual is not None and revision(actual) == revision(bind) and await allowed(ev)

    async def load(ev):
        return await load_client(ev.user_id, ev.bot_id)

    async def profile(ev):
        return await AliceBind.get_bind(ev.user_id, ev.bot_id)

    def enabled():
        return AliceUIDConfig.get_config('AliceUID_EnableWriteOps').data is True

    _commands = Commands(catalog, Redemptions(store), load=load, allowed=allowed,
                         current=current, enabled=enabled, prefix=command_prefix,
                         forward=send_with_forward, profile=profile,
                         result_forward_enabled=lambda: AliceUIDConfig.get_config('AliceUID_CDKResultForward').data is True)
    user_sv, _ = register(_commands)
    from .automatic import Automatic

    def known_routes():
        from ..nikke_community.runtime import setup_community
        import time
        routes = _commands.automatic.store.routes()
        previous = setup_community(policy=policy).runner.notifier.store.routes(time.time())
        routes.extend(dict(bot=r['bot_id'], self_id=r['self_id'], ws=r['ws_id'], group_id=r['group_id']) for r in previous)
        return routes

    async def contexts():
        from gsuid_core.gss import gss
        from types import SimpleNamespace
        contexts, seen = [], set()
        for route in known_routes():
            key = (route['bot'], route['self_id'], route['ws'])
            transport = gss.active_bot.get(route['ws'])
            if key in seen or transport is None or getattr(transport, 'bot', None) is None:
                continue
            seen.add(key)
            contexts.append(SimpleNamespace(bot_id=key[0], bot_self_id=key[1], WS_BOT_ID=key[2],
                                             user_id='', group_id=None, user_pm=6))
        return contexts

    def masters():
        from gsuid_core.config import core_config
        return core_config.get_config('masters') or []

    async def permitted(ev):
        from gsuid_core.sv import SL
        from gsuid_core.gss import gss
        from gsuid_core.utils.plugins_config.gs_config import sp_config
        from ..nikke_harvest.runtime import native_allowed
        if not await allowed(ev):
            return False
        group = getattr(ev, 'group_id', None)
        route = dict(kind='group' if group else 'direct', target=str(group or ev.user_id),
                     user=str(ev.user_id), pm=ev.user_pm)
        targets = {str(ev.user_id)} | ({str(group)} if group else set())
        if targets & set(map(str, sp_config.get_config('BlackList').data)):
            return False
        plugin = SL.plugins.get('AliceUID')
        if not native_allowed(plugin, route) or not native_allowed(user_sv, route, parent_area=getattr(plugin, 'area', None)):
            return False
        transport = gss.active_bot.get(ev.WS_BOT_ID)
        return transport is not None and getattr(transport, 'bot', None) is not None

    async def notify(source, group, text):
        from gsuid_core.gss import gss
        from types import SimpleNamespace
        route = _commands.automatic.store.route(source, group)
        if route is None:
            # Upgrade compatibility: reuse an already observed exact connection.
            from ..nikke_community.runtime import setup_community
            import time
            previous = setup_community(policy=policy).runner.notifier.store.routes(time.time())
            known = next((r for r in previous if r['group_id'] == str(group)
                          and r['bot_id'] == str(source.bot_id)
                          and r['self_id'] == str(source.bot_self_id)), None)
            if known is None:
                return
            route = dict(bot=known['bot_id'], self_id=known['self_id'], ws=known['ws_id'])
        ev = SimpleNamespace(user_id=source.user_id, bot_id=route['bot'], group_id=group,
                             bot_self_id=route['self_id'], WS_BOT_ID=route['ws'], user_pm=getattr(source, 'user_pm', 6))
        if not await permitted(ev):
            return
        transport = gss.active_bot.get(route['ws'])
        from .commands import pages
        for page in pages(text):
            if not await permitted(ev):
                break
            await transport.target_send(page, 'group', group, route['bot'], route['self_id'],
                                        group_id=group, at_sender=False, wait_recall=True)

    _commands.automatic = Automatic(_commands, config=AliceUIDConfig, bindings=AliceBind.get_all_binds,
                                    permitted=permitted, notify=notify, masters=masters)

    async def background_event(ev):
        from gsuid_core.gss import gss
        from copy import copy
        for route in known_routes():
            if route['bot'] != ev.bot_id or route.get('group_id') != ev.group_id:
                continue
            transport = gss.active_bot.get(route['ws'])
            if transport is None or getattr(transport, 'bot', None) is None:
                continue
            candidate = copy(ev)
            candidate.bot_self_id, candidate.WS_BOT_ID = route['self_id'], route['ws']
            if await permitted(candidate):
                return candidate
        return ev if await permitted(ev) else None

    _commands.automatic.background_event = background_event
    from .discovery import PublicDiscoveries
    _commands.public_discoveries = PublicDiscoveries(_commands.automatic, contexts)

    async def automatic_tick():
        try:
            await _commands.public_discoveries.tick()
        except Exception as exc:
            from gsuid_core.logger import logger
            logger.warning(f'[AliceUID] automatic CDK scan incomplete error_type={type(exc).__name__}')

    _commands.public_tick = automatic_tick

    async def refresh():
        try:
            await catalog.ensure(force=True)
            await automatic_tick()
        except Exception as exc:
            from gsuid_core.logger import logger
            logger.warning(f'[AliceUID] CDK catalog refresh failed error_type={type(exc).__name__}')

    async def startup():
        if catalog.needs(catalog.clock(), scheduled=True):
            await refresh()
        else:
            await automatic_tick()

    scheduler.add_job(refresh, 'cron', hour='0,8,16', minute=0, timezone='Asia/Shanghai',
        id='aliceuid-cdk-catalog', name='AliceUID兑换码双源汇总', replace_existing=True,
        max_instances=1, coalesce=True)
    scheduler.add_job(automatic_tick, 'interval', seconds=60, id='aliceuid-cdk-automatic',
                      name='AliceUID公开新码自动兑换', replace_existing=True, max_instances=1, coalesce=True)
    try:
        _startup = asyncio.get_running_loop().create_task(startup())
    except RuntimeError:
        # Core may import plugins before its event loop starts. Use its existing scheduler.
        scheduler.add_job(startup, 'date', id='aliceuid-cdk-startup', replace_existing=True,
                          max_instances=1, coalesce=True)
    return _commands


def observe_group(ev):
    if _commands is not None and _commands.automatic is not None:
        _commands.automatic.store.observe(ev)
