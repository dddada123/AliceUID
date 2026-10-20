"""Sequential APScheduler adapter; current binding list is the source of truth."""
from __future__ import annotations

import asyncio

from .commands import CommunityCommands
from .schedule import DEFAULT, clock_parts, normalized_time
from .cycle import cycle_day

JOB_ID = "aliceuid-community"


class CommunityScheduler:
    def __init__(self, commands: CommunityCommands, list_bindings, *, sign_time=lambda: DEFAULT):
        """list_bindings(): awaitable iterable of (actor_id, bot_id, revision).

        It must include all current bindings, even those without valid cookies.
        Missing/changed revisions revoke old consent before any work is started.
        """
        self.commands, self.list_bindings = commands, list_bindings
        self._lock = asyncio.Lock()
        self.sign_time = sign_time
        self.scheduler = None

    def reschedule(self, value):
        if self.scheduler is None:
            return None
        hour, minute = clock_parts(value)
        update = getattr(self.scheduler, 'reschedule_job', None)
        if callable(update):
            job = update(JOB_ID, trigger='cron', hour=hour, minute=minute, timezone='Asia/Shanghai')
            modify = getattr(self.scheduler, 'modify_job', None)
            if callable(modify):
                modify(JOB_ID, name=f'AliceUID每日签到（{normalized_time(value)}北京时间）')
            return job
        return register_scheduler(self, self.scheduler, time_value=value)

    async def tick(self):
        if self._lock.locked():
            return
        async with self._lock:
            if not self.commands.enabled():
                return
            batch_day = cycle_day(self.commands.service.clock())
            rows = list(await self.list_bindings())
            service = self.commands.service
            owners = {service.owner(str(actor), str(bot), str(revision)) for actor, bot, revision in rows}
            service.store.reconcile(owners)
            for actor, bot, revision in rows:
                if cycle_day(service.clock()) != batch_day:
                    break
                if not self.commands.enabled():
                    return
                if not service.user_allowed(str(actor)):
                    service.pause_owner(str(actor), str(bot), str(revision))
                    continue
                binding = await self.commands.load_binding(str(actor), str(bot))
                if binding is None:
                    continue
                try:
                    if (str(binding.actor_id), str(binding.bot_id), binding.revision) != (str(actor), str(bot), str(revision)):
                        continue
                    await service.run(binding.client, str(actor), str(bot), str(revision))
                finally:
                    await binding.client.close()


def register_scheduler(runner: CommunityScheduler, scheduler=None, *, time_value=None):
    """One daily Core cron, live-rescheduled by validated WebUI saves."""
    if scheduler is None:
        from gsuid_core.aps import scheduler
    runner.scheduler = scheduler
    value = normalized_time(runner.sign_time() if time_value is None else time_value)
    hour, minute = clock_parts(value)
    return scheduler.add_job(runner.tick, 'cron', hour=hour, minute=minute, timezone='Asia/Shanghai',
                             id=JOB_ID, name=f'AliceUID每日签到（{value}北京时间）',
                             replace_existing=True, max_instances=1, coalesce=True,
                             misfire_grace_time=3600)
