"""Selectable cadence for game reads; third-party SOLO and writes stay independent."""
import asyncio
from contextvars import ContextVar

STRATEGY_KEY = 'AliceUID_PanelRiskStrategy'
STRATEGIES = ('极速', '快速', '中速', '低速')


def normalize_strategy(value):
    if not isinstance(value, str):
        return '中速'
    aliases = {'aggressive': '快速', 'conservative': '中速',
               'turbo': '极速', 'fast': '快速', 'medium': '中速', 'slow': '低速'}
    return aliases.get(value, value if value in STRATEGIES else '中速')


def panel_interval():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(STRATEGY_KEY).data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        value = '中速'
    return {'极速': 0.8, '快速': 1.0, '中速': 2.0, '低速': 5.0}[normalize_strategy(value)]


parallel_game_reads = ContextVar('alice_parallel_game_reads', default=False)


async def run_group(operations, *, turbo=False):
    """Cancel and drain siblings on failure; never leave reads running after return."""
    if not turbo:
        return [await operation() for operation in operations]
    limit = asyncio.Semaphore(4)
    async def one(operation):
        async with limit:
            token = parallel_game_reads.set(True)
            try:
                return await operation()
            finally:
                parallel_game_reads.reset(token)
    tasks = [asyncio.create_task(one(operation)) for operation in operations]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def game_reads(client, calls):
    custom = getattr(type(client), 'read_many', None)
    if custom is not None:
        return await client.read_many(calls)
    return await run_group([lambda name=name,args=args: getattr(client,name)(*args)
                            for name,args in calls], turbo=getattr(client,'turbo',False))
