"""Durable public-source discoveries; catalog queries themselves remain read-only."""
from __future__ import annotations

import asyncio
import json
from .models import code_key, PRODUCT


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

    def migrate_baseline(self):
        """Seed old inventory without replaying it; preserve existing pending public work."""
        with self.store.tx() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='auto_discovery_v123'").fetchone():
                return
            for row in db.execute('SELECT code FROM inventory_codes WHERE product=?', (PRODUCT,)).fetchall():
                db.execute('INSERT OR IGNORE INTO auto_public_codes VALUES(?,?,0)',
                           (code_key(row['code']), json.dumps(dict(code=row['code'], sources=[]))))
            # Contributions from versions predating the discovery ledger already triggered a batch.
            for row in db.execute('SELECT code FROM member_codes WHERE product=?', (PRODUCT,)).fetchall():
                key = code_key(row['code'])
                db.execute('INSERT OR IGNORE INTO auto_public_codes VALUES(?,?,0)',
                           (key, json.dumps(dict(code=row['code'], sources=['member']))))
                db.execute('UPDATE auto_public_codes SET enabled=0 WHERE code_key=?', (key,))
            self.store._meta(db, 'auto_discovery_v123', True)

    def discover(self, items, enabled, *, member=False):
        with self.store.tx() as db:
            if not enabled:
                db.execute('UPDATE auto_public_codes SET enabled=0')
            for item in items:
                if not member and not {'official', 'gamewith'} & set(item.get('sources', [])):
                    continue
                key = code_key(item['code'])
                old = db.execute('SELECT item FROM auto_public_codes WHERE code_key=?', (key,)).fetchone()
                value = dict(item)
                if member:
                    value['sources'] = ['member']
                if old:
                    prior = json.loads(old['item'])
                    value['sources'] = sorted(set(prior.get('sources', [])) | set(value.get('sources', [])))
                    db.execute('UPDATE auto_public_codes SET item=? WHERE code_key=?',
                               (json.dumps(value, ensure_ascii=False), key))
                else:
                    db.execute('INSERT INTO auto_public_codes VALUES(?,?,?)',
                               (key, json.dumps(value, ensure_ascii=False), int(enabled)))

    def remember_member(self, items):
        # Compatibility API for already-dispatched contributions.
        with self.store.tx() as db:
            db.executemany('INSERT OR IGNORE INTO auto_public_codes VALUES(?,?,0)',
                           [(code_key(i['code']), json.dumps(i)) for i in items])

    def pending(self, bot, items):
        available = {code_key(i['code']): i for i in items}
        with self.store.tx() as db:
            rows = list(db.execute("""SELECT code_key,item FROM auto_public_codes
                WHERE enabled=1 AND NOT EXISTS (SELECT 1 FROM auto_public_dispatch AS done
                    WHERE done.code_key=auto_public_codes.code_key AND done.bot=?)""", (str(bot),)))
        return [dict(available[r['code_key']], sources=json.loads(r['item']).get('sources', []))
                for r in rows if r['code_key'] in available]

    def complete(self, bot, items):
        with self.store.tx() as db:
            db.executemany('INSERT OR IGNORE INTO auto_public_dispatch VALUES(?,?)',
                           [(code_key(i['code']), str(bot)) for i in items])

    async def contribute(self, bot, source, bind, items, seed, *, seed_client=None):
        async with self.lock:
            auto = self.automatic
            enabled = auto.enabled() and auto.commands.enabled()
            self.discover(items, enabled, member=True)
            fresh = self.pending(source.bot_id, items)
            if enabled and fresh:
                result = await auto.run(bot, source, bind, fresh, seed, seed_client=seed_client)
                if result is not None:
                    self.complete(source.bot_id, fresh)
                return result

    async def tick(self):
        # Queue the event rather than dropping a publication while another batch is running.
        async with self.lock:
            auto = self.automatic
            enabled = auto.enabled() and auto.commands.enabled()
            self.discover(auto.commands.catalog.report()['items'], enabled)
            if not enabled:
                return
            seen = set()
            for source in await self.contexts():
                if str(source.bot_id) in seen:
                    continue
                seen.add(str(source.bot_id))
                items = self.pending(source.bot_id, auto.commands.catalog.report()['items'])
                if items:
                    result = await auto.run(None, source, None, items, [], background=True)
                    if result is not None:
                        self.complete(source.bot_id, items)
