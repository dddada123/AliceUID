"""Register one cron on GsCore's shared scheduler; never start another scheduler."""
from __future__ import annotations

from .service import get_database

JOB_ID = 'aliceuid-database-weekly'


class DatabaseScheduler:
    def __init__(self, service):
        self.service = service

    async def tick(self):
        if self.service.config('DatabaseWeeklyUpdate') is not False:
            return await self.service.run_continuous(reason='weekly')
        return None


def register_scheduler(runner, scheduler=None):
    if scheduler is None:
        from gsuid_core.aps import scheduler
    return scheduler.add_job(runner.tick, 'cron', day_of_week='fri', hour=2, minute=33,
                             timezone='Asia/Shanghai', id=JOB_ID, name='AliceUID数据库周检',
                             replace_existing=True, max_instances=1, coalesce=True)


def setup(config_getter=None, scheduler=None):
    service = get_database(config_getter)
    weekly = register_scheduler(DatabaseScheduler(service), scheduler)
    if scheduler is None:
        from gsuid_core.aps import scheduler
    from datetime import datetime, timezone
    from .calendar_update import CalendarUpdates
    runner = CalendarUpdates(service)
    scheduler.add_job(runner.tick, 'interval', seconds=60, next_run_time=datetime.now(timezone.utc),
                      id='aliceuid-database-calendar', name='AliceUID日历数据库静默检查',
                      replace_existing=True, max_instances=1, coalesce=True)
    return weekly
