"""Backward-compatible owner-only alias for the incremental database updater."""
from __future__ import annotations

from gsuid_core.sv import SV

sv_resources = SV('妮姬资源维护', pm=0, priority=3)


@sv_resources.on_fullmatch('更新资源')
async def update_resources(bot, ev):
    from ..nikke_database.commands import DatabaseCommands
    from ..nikke_database.service import get_database
    await DatabaseCommands(get_database()).handle(bot, ev)
