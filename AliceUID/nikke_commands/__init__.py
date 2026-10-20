"""One startup snapshot for command dispatch and visible command examples."""
from __future__ import annotations

import re

ENABLED_KEY = 'AliceUID_CustomPrefixEnabled'
PREFIX_KEY = 'AliceUID_CustomPrefix'
DISABLE_KEY = 'AliceUID_DisableDefaultPrefix'
PREFIX_KEYS = {ENABLED_KEY, PREFIX_KEY, DISABLE_KEY}
_active = ('nk',)


def valid_prefix(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9\u3400-\u9fff_-]{1,12}', value) is not None


def resolve_prefixes(enabled=False, custom='alice', disable=False):
    if type(enabled) is not bool or type(disable) is not bool or not valid_prefix(custom):
        raise ValueError('唤醒指令配置无效')
    if not enabled:
        return ('nk',)
    if disable:
        return (custom,)
    return tuple(dict.fromkeys(('nk', custom)))


def configure(config):
    global _active
    _active = resolve_prefixes(config.get_config(ENABLED_KEY).data,
                               config.get_config(PREFIX_KEY).data,
                               config.get_config(DISABLE_KEY).data)


def command_prefix():
    return _active[0]


def bind_triggers(plugin):
    if _active == ('nk',):
        return 0
    from gsuid_core.sv import SL
    from gsuid_core.trigger import Trigger, bump_registry_version
    count = 0
    for service in SL.detail_lst.get(plugin, []):
        for kind, triggers in service.TL.items():
            if kind in ('file', 'message', 'meta'):
                continue
            rebuilt = {}
            for trigger in triggers.values():
                for prefix in _active:
                    key = prefix + trigger.keyword
                    if key not in rebuilt:
                        rebuilt[key] = Trigger(trigger.type, trigger.keyword, trigger.func,
                                               prefix, trigger.block, trigger.to_me)
                        count += 1
            service.TL[kind] = rebuilt
    plugin.prefix = []
    plugin.force_prefix = list(_active)
    plugin.disable_force_prefix = False
    plugin.allow_empty_prefix = False
    bump_registry_version()
    return count
