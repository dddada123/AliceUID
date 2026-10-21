"""Core owns command registration; migrate legacy prefix settings once at startup."""
from __future__ import annotations
import json
import re
from copy import deepcopy

ENABLED_KEY = 'AliceUID_CustomPrefixEnabled'
PREFIX_KEY = 'AliceUID_CustomPrefix'
DISABLE_KEY = 'AliceUID_DisableDefaultPrefix'
PREFIX_KEYS = {ENABLED_KEY, PREFIX_KEY, DISABLE_KEY}
_active = ('nk',)


def valid_prefix(value):
    """Only for validating old settings during migration, not a Core restriction."""
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9\u3400-\u9fff_-]{1,12}', value) is not None


def resolve_prefixes(enabled=False, custom='alice', disable=False):
    if type(enabled) is not bool or type(disable) is not bool or not valid_prefix(custom):
        raise ValueError('旧唤醒指令配置无效，请检查配置文件')
    if not enabled:
        return ('nk',)
    return (custom,) if disable else tuple(dict.fromkeys(('nk', custom)))


def effective_prefixes(settings):
    custom = settings.get('prefix', [])
    if isinstance(custom, str):
        custom = [custom] if custom else []
    forced = [] if settings.get('disable_force_prefix', False) else ['nk']
    prefixes = [p for p in forced + custom if p]
    if settings.get('allow_empty_prefix', False):
        prefixes.append('')
    return tuple(dict.fromkeys(prefixes)) or ('',)


def configure(plugin, config_path):
    """Run BEFORE any SV or plugin StringConfig is constructed.

    Use the Core config store, then let native SV registration build every Trigger.
    Existing Core customizations win. The marker prevents old fields from being
    reapplied after a user subsequently changes Core's own settings.
    """
    global _active
    from gsuid_core.config import plugin_config_store, plugins_sample
    from gsuid_core.logger import logger
    from ..nikke_resource.cache import atomic_write
    marker = config_path.with_name('prefix_migration_v112.json')
    settings = deepcopy(plugin_config_store.get(plugin.name))
    if not marker.exists():
        raw = json.loads(config_path.read_text('utf-8')) if config_path.exists() else {}
        legacy = {key: raw[key]['data'] for key in PREFIX_KEYS if key in raw}
        outcome = 'native'
        if legacy.get(ENABLED_KEY, False):
            custom = legacy.get(PREFIX_KEY, 'alice')
            disable = legacy.get(DISABLE_KEY, False)
            resolve_prefixes(legacy[ENABLED_KEY], custom, disable)
            native_custom = (bool(settings.get('prefix')) or settings.get('disable_force_prefix', False)
                             or settings.get('allow_empty_prefix', False))
            if native_custom:
                outcome = 'kept_existing_core'
                logger.warning('[AliceUID] 已保留Core前缀配置；旧插件前缀未覆盖Core设置，迁移记录已保存')
            else:
                updated = deepcopy(settings or plugins_sample)
                updated.update(name=plugin.name, prefix=[custom], force_prefix=['nk'],
                               disable_force_prefix=disable, allow_empty_prefix=False)
                plugin_config_store.set(plugin.name, updated)
                try:
                    plugin_config_store.save(plugin.name)
                except (OSError, RuntimeError):
                    plugin_config_store.set(plugin.name, settings)
                    raise
                settings = updated
                outcome = 'migrated'
                logger.info('[AliceUID] 旧自定义前缀已迁移到Core；后续请在Core插件管理中配置')
        atomic_write(marker, json.dumps(dict(version=1, outcome=outcome, legacy=legacy,
            prefix=settings.get('prefix', []), disable_force_prefix=settings.get('disable_force_prefix', False)),
            ensure_ascii=False).encode('utf-8'))
    _active = effective_prefixes(settings)


def command_prefix():
    """Display the effective startup prefix; native triggers use the same snapshot."""
    return _active[0]
