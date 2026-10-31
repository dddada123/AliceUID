"""GsCore wiring. Catalog scheduler is public and can never redeem."""
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
    register(_commands)

    async def refresh():
        try:
            await catalog.ensure(force=True)
        except Exception as exc:
            from gsuid_core.logger import logger
            logger.warning(f'[AliceUID] CDK catalog refresh failed error_type={type(exc).__name__}')

    async def startup():
        if catalog.needs(catalog.clock(), scheduled=True):
            await refresh()

    scheduler.add_job(refresh, 'cron', hour='0,8,16', minute=0, timezone='Asia/Shanghai',
        id='aliceuid-cdk-catalog', name='AliceUID兑换码双源汇总', replace_existing=True,
        max_instances=1, coalesce=True)
    try:
        _startup = asyncio.get_running_loop().create_task(startup())
    except RuntimeError:
        # Core may import plugins before its event loop starts. Use its existing scheduler.
        scheduler.add_job(startup, 'date', id='aliceuid-cdk-startup', replace_existing=True,
                          max_instances=1, coalesce=True)
    return _commands
