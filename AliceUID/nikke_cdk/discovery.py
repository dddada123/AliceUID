"""Durable public-source discoveries; catalog queries themselves remain read-only."""
from __future__ import annotations

import asyncio
import json
from .models import code_key


class PublicDiscoveries:
    def __init__(self, automatic, contexts):
        self.automatic, self.contexts = automatic, contexts
        self.store = automatic.commands.redemptions.store
        self.lock = asyncio.Lock()
        with self.store.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auto_public_codes (
                    code_key TEXT PRIMARY KEY, item TEXT NOT NULL, enabled INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS auto_public_dispatch (
                    code_key TEXT, bot TEXT, PRIMARY KEY(code_key,bot));
            ''')

    def discover(self, items, enabled):
        with self.store.tx() as db:
            if not enabled:
                # A pause discards pending work too, without changing individual preferences.
                db.execute('UPDATE auto_public_codes SET enabled=0')
            for item in items:
                if not {'official', 'gamewith'} & set(item.get('sources', [])):
                    continue
                db.execute('INSERT OR IGNORE INTO auto_public_codes VALUES(?,?,?)',
                    (code_key(item['code']), json.dumps(item, ensure_ascii=False),
                     int(enabled)))

    def remember_member(self, items):
        """This version's member additions already have their own automatic trigger."""
        with self.store.tx() as db:
            db.executemany('INSERT OR IGNORE INTO auto_public_codes VALUES(?,?,0)',
                [(code_key(item['code']), json.dumps(item, ensure_ascii=False)) for item in items])

    def pending(self, bot, items):
        available = {code_key(item['code']): item for item in items}
        with self.store.tx() as db:
            keys = [r[0] for r in db.execute('''SELECT code_key FROM auto_public_codes
                WHERE enabled=1 AND NOT EXISTS (SELECT 1 FROM auto_public_dispatch AS done
                    WHERE done.code_key=auto_public_codes.code_key AND done.bot=?)''', (str(bot),))]
        return [available[key] for key in keys if key in available]

    def complete(self, bot, items):
        with self.store.tx() as db:
            db.executemany('INSERT OR IGNORE INTO auto_public_dispatch VALUES(?,?)',
                           [(code_key(item['code']), str(bot)) for item in items])

    async def tick(self):
        if self.lock.locked():
            return
        async with self.lock:
            auto = self.automatic
            report = auto.commands.catalog.report()
            enabled = auto.enabled() and auto.commands.enabled()
            self.discover(report['items'], enabled)
            if not enabled:
                return
            seen = set()
            for source in await self.contexts():
                if str(source.bot_id) in seen:
                    continue
                seen.add(str(source.bot_id))
                items = self.pending(source.bot_id, auto.commands.catalog.report()['items'])
                if not items:
                    continue
                await auto.run(None, source, None, items, [], background=True)
                self.complete(source.bot_id, items)
