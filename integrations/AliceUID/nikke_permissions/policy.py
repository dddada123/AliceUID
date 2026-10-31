"""Standalone access policy; GsCore is only needed by config/registration adapters."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
from pathlib import Path


class GroupPolicyError(ValueError):
    pass


_LOCKS: dict[str, asyncio.Lock] = {}
LIST_NAMES = ("whitelist", "blacklist", "user_whitelist", "user_blacklist")


def group_key(value) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise GroupPolicyError("名单号码须为ASCII数字")
    result = str(value)
    if not result or len(result) > 32 or not result.isascii() or not result.isdigit():
        raise GroupPolicyError("名单号码须为ASCII数字")
    return result


def validate_lists(values: dict) -> dict:
    result = {}
    for key in LIST_NAMES:
        value = values.get(key, [])
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise GroupPolicyError("名单须为字符串列表")
        result[key] = sorted({group_key(v) for v in value})
    for white, black in (("whitelist", "blacklist"), ("user_whitelist", "user_blacklist")):
        overlap = set(result[white]) & set(result[black])
        if overlap:
            raise GroupPolicyError("白黑名单冲突，未保存：" + "、".join(sorted(overlap)))
    return result


def decode_policy(data) -> dict:
    if data is None or data == {}:
        data = {"version": 2}
    if not isinstance(data, dict) or data.get("version") not in (1, 2):
        raise GroupPolicyError("权限策略文件异常，请联系Bot主检查")
    if data.get("mode", "blacklist") not in ("blacklist", "whitelist"):
        raise GroupPolicyError("权限策略模式异常")
    lists = validate_lists(data)
    groups = data.get("groups", {})
    if not isinstance(groups, dict) or any(type(v) is not bool for v in groups.values()):
        raise GroupPolicyError("旧群开关数据异常")
    for key in groups:
        group_key(key)
    # Legacy disabled groups become explicit denials; conflicting legacy intent
    # requires owner repair instead of silently choosing a list.
    lists["blacklist"] = sorted(set(lists["blacklist"]) | {k for k, v in groups.items() if not v})
    lists = validate_lists(lists)
    return {"version": 2, "mode": data.get("mode", "blacklist"), **lists, "groups": {}}


class GroupPolicy:
    def __init__(self, path: str | Path, *, config=None):
        self.path = Path(path).resolve()
        self.config = config
        self._lock = _LOCKS.setdefault(str(self.path).casefold(), asyncio.Lock())

    @staticmethod
    def _default():
        return decode_policy(None)

    def _load(self):
        try:
            if self.config is not None:
                from .config import config_lists
                return {**self._default(), **config_lists(self.config)}
            if not self.path.exists():
                return self._default()
            text = self.path.read_text(encoding="utf-8")
            raw = json.loads(text)
            if not isinstance(raw, dict) or not raw:
                raise GroupPolicyError("已存在的权限策略不得为空")
            return decode_policy(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise GroupPolicyError("权限策略文件异常，请联系Bot主检查：" + str(exc)) from exc

    def _save(self, data):
        data = decode_policy(data)
        if self.config is not None:
            from .config import set_config_lists
            set_config_lists(self.config, data)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".group-policy-", suffix=".tmp", dir=self.path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise GroupPolicyError("保存权限策略失败") from exc
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _allowed(data, group):
        return (not data["whitelist"] or group in data["whitelist"]) and group not in data["blacklist"]

    async def query_allowed(self, group_id):
        try:
            data = self._load()
            if group_id is None or group_id == "":
                return True
            return self._allowed(data, group_key(group_id))
        except GroupPolicyError:
            return False

    def user_allowed(self, user_id) -> bool:
        """Check the authenticated actor for every command, including Bot owners.

        No chat maintenance bypass exists; broken policy fails closed.
        """
        try:
            user = group_key(user_id)
            data = self._load()
            return user not in data["user_blacklist"] and (not data["user_whitelist"] or user in data["user_whitelist"])
        except GroupPolicyError:
            return False

    async def snapshot(self):
        async with self._lock:
            return copy.deepcopy(self._load())

    async def group_status(self, group_id):
        group = group_key(group_id)
        data = self._load()
        return {"local_enabled": group not in data["blacklist"], "allowed": self._allowed(data, group),
                "mode": data["mode"], "blacklisted": group in data["blacklist"], "whitelisted": group in data["whitelist"]}

    async def set_group_enabled(self, group_id, enabled):
        if type(enabled) is not bool:
            raise GroupPolicyError("查询开关只能为开启或关闭")
        await self.update_list("blacklist", group_id, add=not enabled)

    async def set_mode(self, mode):
        if mode not in {"blacklist", "whitelist"}:
            raise GroupPolicyError("策略只能为黑名单或白名单")
        async with self._lock:
            data = self._load()
            data["mode"] = mode
            self._save(data)

    async def update_list(self, list_name, group_id, *, add):
        if list_name not in LIST_NAMES or type(add) is not bool:
            raise GroupPolicyError("名单类型不正确")
        group = group_key(group_id)
        async with self._lock:
            data = self._load()
            values = set(data[list_name])
            values.add(group) if add else values.discard(group)
            data[list_name] = sorted(values)
            self._save(data)
