"""Shared production access policy and explicit standalone dependency injection.

Unconfigured standalone callers fail closed. Tests may install an isolated policy
with set_policy(); production initialization errors must propagate, never allow.
"""
from __future__ import annotations

import os

_policy = None


class _UnavailablePolicy:
    def user_allowed(self, user_id):
        return False

    async def query_allowed(self, group_id):
        return False


_unavailable = _UnavailablePolicy()


def set_policy(policy):
    """Install the one shared policy (or reset with None in isolated tests)."""
    global _policy
    _policy = policy
    return policy


def get_policy():
    global _policy
    if _policy is None:
        if os.environ.get("ALICEUID_STANDALONE") == "1":
            return _unavailable
        from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
        from .policy import GroupPolicy
        _policy = GroupPolicy(MAIN_PATH / "group_policy.json", config=AliceUIDConfig)
    return _policy
