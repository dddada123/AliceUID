"""Validated adapter for the pinned GsCore StringConfig save chain.

Importing this module does not import Core. The factory constructs a genuine
StringConfig subclass lazily, so standalone policy tests need no Core runtime.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from threading import RLock

from .policy import GroupPolicyError, LIST_NAMES, decode_policy, validate_lists

GROUP_WHITELIST_KEY = "AliceUID_GroupWhitelist"
GROUP_BLACKLIST_KEY = "AliceUID_GroupBlacklist"
USER_WHITELIST_KEY = "AliceUID_UserWhitelist"
USER_BLACKLIST_KEY = "AliceUID_UserBlacklist"
CONFIG_KEYS = dict(zip(LIST_NAMES, (GROUP_WHITELIST_KEY, GROUP_BLACKLIST_KEY, USER_WHITELIST_KEY, USER_BLACKLIST_KEY)))
_CONFIG_LOCK = RLock()
_VALIDATED_TYPE = None


def config_lists(config):
    with _CONFIG_LOCK:
        return validate_lists({name: config.config[key].data for name, key in CONFIG_KEYS.items()})


def set_config_lists(config, values):
    """Validate four plugin lists, perform one Core write, restore memory on error."""
    values = validate_lists(values)
    with _CONFIG_LOCK:
        previous = copy.deepcopy(config.config)
        try:
            for name, key in CONFIG_KEYS.items():
                config.config[key].data = values[name]
            config.write_config()
        except Exception:
            config.config = previous
            raise


def _preflight(path):
    """Reject invalid access data before Core repair can reset it to permissive defaults."""
    if not path.exists():
        return False
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise GroupPolicyError("已存在的配置文件须为非空对象，请Bot主从备份检查恢复")
    present = any(key in raw for key in CONFIG_KEYS.values())
    if present and not all(key in raw for key in CONFIG_KEYS.values()):
        raise GroupPolicyError("权限配置四名单缺项，请Bot主检查原文件")
    values = {}
    for name, key in CONFIG_KEYS.items():
        entry = raw.get(key, {"data": []})
        if not isinstance(entry, dict) or "data" not in entry:
            raise GroupPolicyError("权限配置格式异常：" + key)
        # Prevent Core reconcile from replacing a malformed typed access item.
        if key in raw and (entry.get("type") != "GsListStrConfig"
                           or not isinstance(entry.get("title"), str)
                           or not isinstance(entry.get("desc"), str)
                           or type(entry.get("secret", False)) is not bool
                           or not isinstance(entry.get("options", []), list)
                           or any(not isinstance(v, str) for v in entry.get("options", []))):
            raise GroupPolicyError("权限配置类型异常：" + key)
        values[name] = entry["data"]
    validate_lists(values)
    return present


def ValidatedStringConfig(config_name, CONFIG_PATH, config_list, *, legacy_path=None):
    """Return an actual StringConfig subclass instance; same three Core arguments.

    Add the four keys as GsListStrConfig defaults before calling this factory.
    Must replace the first StringConfig construction for this name (Core caches it).
    """
    global _VALIDATED_TYPE
    from gsuid_core.utils.plugins_config.gs_config import StringConfig
    if _VALIDATED_TYPE is None or not issubclass(_VALIDATED_TYPE, StringConfig):
        class _ValidatedStringConfig(StringConfig):
            def _get_caller_plugin_name(self):
                # Core's stack-depth based detector sees this adapter; establish
                # the plugin owner explicitly so config appears under AliceUID.
                return "AliceUID"

            def update_config(self):
                _preflight(self.CONFIG_PATH)
                previous = copy.deepcopy(getattr(self, "config", {}))
                try:
                    return super().update_config()
                except Exception:
                    self.config = previous
                    raise

            def repair_config(self):
                # Core repair can replace structurally valid entries when another
                # item is corrupt. Never allow that to erase existing denials.
                if _preflight(self.CONFIG_PATH):
                    raise GroupPolicyError("配置修复可能重置权限名单，请Bot主检查原文件")
                return super().repair_config()

            def _migrate_config(self, old_path, new_path):
                if not new_path.exists():
                    _preflight(old_path)
                return super()._migrate_config(old_path, new_path)

            def write_config(self):
                config_lists(self)
                return super().write_config()

            def set_config(self, key, value):
                with _CONFIG_LOCK:
                    from ..nikke_commands import ENABLED_KEY, PREFIX_KEY, DISABLE_KEY, valid_prefix
                    from ..nikke_community.pacing import RANGE_KEYS, parse_range
                    if key in (ENABLED_KEY, DISABLE_KEY) and type(value) is not bool:
                        return False
                    if key == PREFIX_KEY and not valid_prefix(value):
                        return False
                    if key in RANGE_KEYS:
                        try:
                            parse_range(value)
                        except ValueError:
                            return False
                    if key == 'AliceUID_CommunitySignTime':
                        from ..nikke_community.schedule import valid_time
                        if not valid_time(value):
                            return False
                    if key in ('AliceUID_GlassStrength', 'AliceUID_ForwardJpegQuality'):
                        if type(value) is not int or not 0<=value<=100:
                            return False
                    if key == 'AliceUID_CardFont':
                        from ..nikke_render.fonts import font_options
                        if not isinstance(value,str) or value not in font_options():
                            return False
                    if key in CONFIG_KEYS.values():
                        candidate = config_lists(self)
                        name = next(name for name, config_key in CONFIG_KEYS.items() if config_key == key)
                        candidate[name] = value
                        try:
                            validate_lists(candidate)
                        except GroupPolicyError:
                            return False
                    previous = copy.deepcopy(self.config)
                    try:
                        result = super().set_config(key, value)
                        if result and key == 'AliceUID_CommunitySignTime':
                            from ..nikke_community.runtime import apply_sign_schedule
                            try:
                                apply_sign_schedule(value)
                            except Exception:
                                self.config = previous
                                super().write_config()
                                try:
                                    apply_sign_schedule(previous[key].data)
                                except Exception:
                                    pass
                                return False
                        return result
                    except Exception:
                        self.config = previous
                        raise
        _VALIDATED_TYPE = _ValidatedStringConfig
    path = Path(CONFIG_PATH[-1] if isinstance(CONFIG_PATH, list) else CONFIG_PATH)
    source = path
    if not path.exists() and isinstance(CONFIG_PATH, list):
        source = next((Path(p) for p in CONFIG_PATH[:-1] if Path(p).exists()), path)
    present = _preflight(source)
    legacy = None
    if not present and legacy_path is not None and Path(legacy_path).exists():
        text = Path(legacy_path).read_text(encoding="utf-8")
        raw = json.loads(text)
        if not isinstance(raw, dict) or not raw:
            raise GroupPolicyError("已存在的旧权限策略不得为空")
        legacy = decode_policy(raw)
    defaults = copy.deepcopy(config_list)
    if source.exists():
        original = json.loads(source.read_text('utf-8'))
        from ..nikke_community.pacing import REQUEST_KEY
        old_interval = original.get('AliceUID_CommunityIntervalSeconds', {}).get('data')
        if REQUEST_KEY not in original and type(old_interval) is int and 10 <= old_interval <= 300 and old_interval != 15:
            defaults[REQUEST_KEY].data = f'{old_interval}-{old_interval}'
    if legacy is not None:
        for name, key in CONFIG_KEYS.items():
            defaults[key].data = legacy[name]
    instance = _VALIDATED_TYPE(config_name, CONFIG_PATH, defaults)
    if not isinstance(instance, _VALIDATED_TYPE):
        raise GroupPolicyError("此配置已由原生StringConfig初始化；必须先使用ValidatedStringConfig")
    return instance
