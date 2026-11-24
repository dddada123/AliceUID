"""Startup initialization and twice-daily incremental scan on GsCore's shared scheduler."""
from __future__ import annotations

from datetime import datetime, timezone

from .service import get_guide_service

STARTUP_JOB_ID = 'aliceuid-guide-startup'
DAILY_AM_JOB_ID = 'aliceuid-guide-daily-am'
DAILY_PM_JOB_ID = 'aliceuid-guide-daily-pm'


class GuideScheduler:
    def __init__(self, service_factory=get_guide_service):
        self.service_factory = service_factory

    async def startup_tick(self):
        service = self.service_factory()
        try:
            await service.ensure_indexed(force=not service.is_initialized(), allow_stale_on_error=True)
        except Exception as exc:
            try:
                from ..nikke_logs.store import record_failure
                record_failure('攻略查询', 'STARTUP_INDEX', exc)
            except Exception:
                pass

    async def daily_tick(self):
        service = self.service_factory()
        try:
            await service.ensure_indexed(force=True, allow_stale_on_error=True)
        except Exception as exc:
            try:
                from ..nikke_logs.store import record_failure
                record_failure('攻略查询', 'DAILY_INDEX', exc)
            except Exception:
                pass


def setup(scheduler=None, *, service_factory=get_guide_service):
    if scheduler is None:
        from gsuid_core.aps import scheduler
    runner = GuideScheduler(service_factory)
    scheduler.add_job(
        runner.startup_tick,
        'date',
        run_date=datetime.now(timezone.utc),
        id=STARTUP_JOB_ID,
        name='AliceUID攻略索引启动检查',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        runner.daily_tick,
        'cron',
        hour=4,
        minute=15,
        timezone='Asia/Shanghai',
        id=DAILY_AM_JOB_ID,
        name='AliceUID攻略索引凌晨增量扫描',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        runner.daily_tick,
        'cron',
        hour=14,
        minute=15,
        timezone='Asia/Shanghai',
        id=DAILY_PM_JOB_ID,
        name='AliceUID攻略索引日间增量扫描',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return runner
