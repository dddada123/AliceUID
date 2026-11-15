"""Serial game-read cadence; removed turbo values safely fall back to medium."""
STRATEGY_KEY = 'AliceUID_PanelRiskStrategy'
STRATEGIES = ('高速', '中速（推荐）', '缓速')
DEFAULT_STRATEGY = '中速（推荐）'
LEGACY_STRATEGIES = ('极速','turbo','快速','低速','中速','aggressive','conservative','fast','medium','slow')


def normalize_strategy(value):
    if not isinstance(value, str):
        return DEFAULT_STRATEGY
    aliases = {'快速':'高速', 'aggressive':'高速', 'fast':'高速',
               '低速':'缓速', 'slow':'缓速', '中速':DEFAULT_STRATEGY,
               'conservative':DEFAULT_STRATEGY, 'medium':DEFAULT_STRATEGY,
               '极速':DEFAULT_STRATEGY, 'turbo':DEFAULT_STRATEGY}
    return aliases.get(value,value if value in STRATEGIES else DEFAULT_STRATEGY)


def panel_interval():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(STRATEGY_KEY).data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        value = DEFAULT_STRATEGY
    return {'高速':1.0, '中速（推荐）':2.0, '缓速':5.0}[normalize_strategy(value)]
