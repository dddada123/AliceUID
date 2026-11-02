"""Durable, single-user reconciliation created after a new binding commits."""
from __future__ import annotations
import asyncio
from .models import revision
from types import SimpleNamespace

class BindingJobs:
    def __init__(self, automatic, contexts):
        self.auto, self.contexts = automatic, contexts
        self.store = automatic.commands.redemptions.store
        self.lock = asyncio.Lock()
        with self.store.tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS auto_binding_jobs (
                bot TEXT,user TEXT,revision TEXT,group_id TEXT,state TEXT,
                PRIMARY KEY(bot,user,revision))""")

    def enqueue(self, bind, group):
        state = 'pending' if self.auto.active(SimpleNamespace(bot_id=bind.bot_id,user_id=bind.user_id)) else 'skipped'
        with self.store.tx() as db:
            db.execute('INSERT OR IGNORE INTO auto_binding_jobs VALUES(?,?,?,?,?)',
                       (str(bind.bot_id),str(bind.user_id),revision(bind),str(group or ''),state))

    def finish(self, job, state):
        with self.store.tx() as db:
            db.execute('UPDATE auto_binding_jobs SET state=? WHERE bot=? AND user=? AND revision=?',
                       (state,job['bot'],job['user'],job['revision']))

    async def drain(self):
        from types import SimpleNamespace
        async with self.lock:
            with self.store.tx() as db:
                jobs = [dict(r) for r in db.execute("SELECT * FROM auto_binding_jobs WHERE state='pending'")]
            rows = {(str(r.bot_id),str(r.user_id)):r for r in await self.auto.bindings()}
            for job in jobs:
                row = rows.get((job['bot'],job['user']))
                if row is None or revision(row) != job['revision']:
                    self.finish(job, 'cancelled');continue
                if not self.auto.enabled() or not self.auto.commands.enabled() or not self.auto.store.enabled(row.bot_id,row.user_id):
                    self.finish(job, 'skipped');continue
                source = next((c for c in await self.contexts() if str(c.bot_id)==job['bot']),None)
                if source is None:
                    continue
                ev = self.auto.event(source,row,job['group_id'] or None)
                if self.auto.background_event is not None:
                    ev = await self.auto.background_event(ev)
                if ev is None or not await self.auto.permitted(ev):
                    continue
                # A fresh stock publication may queue a separate global new-code event.
                await self.auto.commands.catalog.ensure()
                items = self.auto.inventory([])
                if not items:
                    report = self.auto.commands.catalog.report()
                    if report.get('complete'):
                        self.finish(job, 'done')
                    continue
                result = await self.auto.run(None, ev, row, items, [], background=True, only_user=row.user_id)
                if result is not None:
                    self.finish(job, 'done')
