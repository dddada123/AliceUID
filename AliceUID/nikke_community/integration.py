"""Explicit integration point; this module has no import-time registrations."""
from __future__ import annotations

from dataclasses import dataclass

from .commands import CommunityCommands, register_commands
from .scheduler import CommunityScheduler, register_scheduler
from .service import CommunityService, Policy
from .store import CommunityStore
from .schedule import DEFAULT


@dataclass
class CommunityRuntime:
    service: CommunityService
    commands: CommunityCommands
    runner: CommunityScheduler
    sv: object = None
    job: object = None

    def revoke_binding(self, actor_id: str, bot_id: str, revision: str):
        """Invoke before changing/removing an existing login binding."""
        self.service.revoke(str(actor_id), str(bot_id), revision)


def setup(*, state_path, load_binding, list_bindings, paused=lambda: False,
          interval_seconds=5, max_interval_seconds=15, account_interval=(10,120), daily_requests=30, scheduler=None, register=True,
          sign_time=lambda: DEFAULT, group_report=None, binding_hint=None):
    """Call once from the root plugin after gsuid_core is ready.

    load_binding(actor_id,bot_id) -> Binding | None (opens owned client).
    list_bindings() -> [(actor_id,bot_id,revision)] for ALL current bindings.
    revision should be sha256(cookie_enc.encode()).hexdigest(), never cookie_enc.
    """
    allowed = lambda: not paused()
    service = CommunityService(CommunityStore(state_path),
                               policy=Policy(interval_seconds, daily_requests, max_interval_seconds, *account_interval), allowed=allowed)
    commands = CommunityCommands(service, load_binding, allowed, sign_time=sign_time, group_report=group_report, binding_hint=binding_hint)
    runner = CommunityScheduler(commands, list_bindings, sign_time=sign_time)
    runtime = CommunityRuntime(service, commands, runner)
    if register:
        runtime.sv = register_commands(commands)
        runtime.job = register_scheduler(runner, scheduler)
    return runtime
