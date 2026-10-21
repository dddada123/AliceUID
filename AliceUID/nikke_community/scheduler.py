"""Sequential APScheduler adapter; current binding list is the source of truth."""
from __future__ import annotations

import asyncio

from .commands import CommunityCommands
from .schedule import DEFAULT, clock_parts, normalized_time
from .cycle import cycle_day

JOB_ID = "aliceuid-community"


class CommunityScheduler:
    def __init__(self, commands: CommunityCommands, list_bindings, *, sign_time=lambda: DEFAULT, notifier=None):
        """list_bindings(): awaitable iterable of (actor_id, bot_id, revision).

        It must include all current bindings, even those without valid cookies.
        Missing/changed revisions revoke old consent before any work is started.
        """
        self.commands, self.list_bindings = commands, list_bindings
        self._lock = asyncio.Lock()
        self.sign_time = sign_time
        self.scheduler = None
        self.notifier = notifier

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
            processed = set()
            for actor, bot, revision in rows:
                if cycle_day(service.clock()) != batch_day:
                    break
                if not self.commands.enabled():
                    return
                binding = None
                cancelled = False
                try:
                    if not service.user_allowed(str(actor)):
                        service.pause_owner(str(actor), str(bot), str(revision))
                        continue
                    binding = await self.commands.load_binding(str(actor), str(bot))
                    if binding is None:
                        continue
                    if (str(binding.actor_id), str(binding.bot_id), binding.revision) != (str(actor), str(bot), str(revision)):
                        continue
                    await service.run(binding.client, str(actor), str(bot), str(revision))
                except asyncio.CancelledError:
                    cancelled = True
                    raise
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning('AliceUID community account error_type=%s',type(exc).__name__)
                finally:
                    try:
                        if binding is not None:
                            await binding.client.close()
                    finally:
                        if not cancelled:
                            processed.add((str(actor),str(bot)))
                            await self._notify(batch_day,processed)
            await self._notify(batch_day,processed)

    async def _notify(self, day, processed):
        if self.notifier is None:
            return
        try:
            await self.notifier.progress(day,processed)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('AliceUID group summary error_type=%s',type(exc).__name__)


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
