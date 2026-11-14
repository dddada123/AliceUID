"""Only full-panel collection uses the selectable cadence."""


def panel_interval():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config('AliceUID_PanelRiskStrategy').data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        value = 'conservative'
    return 1.0 if value == 'aggressive' else 2.0
