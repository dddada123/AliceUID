"""Transactional catalog, scoped shared blocks and owned redemption receipts."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS blocks (
                    product TEXT, code TEXT, state TEXT NOT NULL, reason TEXT NOT NULL,
                    checked REAL NOT NULL, PRIMARY KEY(product,code));
                CREATE TABLE IF NOT EXISTS receipts (
                    account TEXT, code TEXT, state TEXT NOT NULL, result TEXT NOT NULL,
                    updated REAL NOT NULL, PRIMARY KEY(account,code));
                CREATE TABLE IF NOT EXISTS leases (key TEXT PRIMARY KEY, token TEXT NOT NULL, until REAL NOT NULL);
            ''')

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def meta(self, key, default=None):
        with self.tx() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        with self.tx() as db:
            self._meta(db, key, value)

    @staticmethod
    def _meta(db, key, value):
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def snapshots(self):
        with self.tx() as db:
            return {r['name']: json.loads(r['value']) for r in db.execute('SELECT * FROM sources')}

    def publish(self, snapshots, now, errors, user_day=None, lease=None, cooldown=900):
        with self.tx() as db:
            if lease and not self._owns(db, 'catalog', lease, now):
                raise RuntimeError('catalog lease lost')
            for name, value in snapshots.items():
                db.execute('INSERT OR REPLACE INTO sources VALUES(?,?)',
                           (name, json.dumps(value, ensure_ascii=False)))
            self._meta(db, 'last_attempt', now)
            self._meta(db, 'errors', errors)
            if not errors:
                self._meta(db, 'catalog_checked_at', now)
                self._meta(db, 'cooldown_until', 0)
                if user_day:
                    self._meta(db, 'first_user_refresh_day', user_day)
            else:
                self._meta(db, 'cooldown_until', now + max(900, cooldown))

    def blocked(self, product):
        with self.tx() as db:
            return {r['code']: dict(r) for r in db.execute('SELECT * FROM blocks WHERE product=?', (product,))}

    def block(self, product, code, state, reason, now):
        with self.tx() as db:
            # Refreshes never write this table. A weaker time-window error cannot erase proven expiry.
            row = db.execute('SELECT state FROM blocks WHERE product=? AND code=?', (product, code)).fetchone()
            if row and row[0] == 'expired':
                return
            db.execute('INSERT OR REPLACE INTO blocks VALUES(?,?,?,?,?)', (product, code, state, reason, now))

    def receipt(self, account, code):
        with self.tx() as db:
            row = db.execute('SELECT * FROM receipts WHERE account=? AND code=?', (account, code)).fetchone()
            return dict(row) if row else None

    def record(self, account, code, state, result, now):
        with self.tx() as db:
            old = db.execute('SELECT state FROM receipts WHERE account=? AND code=?', (account, code)).fetchone()
            if old and old[0] in ('success', 'claimed'):
                return
            db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?,?)', (account, code, state, result, now))

    def claim(self, account, code, token, now):
        with self.tx() as db:
            if not self._owns(db, 'account:' + account, token, now):
                return False
            old = db.execute('SELECT state FROM receipts WHERE account=? AND code=?', (account, code)).fetchone()
            if old and old[0] in ('success', 'claimed', 'submitting', 'uncertain'):
                return False
            db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?,?)', (account, code, 'submitting', '', now))
            return True

    @staticmethod
    def _owns(db, key, token, now):
        return db.execute('SELECT 1 FROM leases WHERE key=? AND token=? AND until>?', (key, token, now)).fetchone() is not None

    def acquire(self, key, now, ttl=120):
        token = uuid.uuid4().hex
        with self.tx() as db:
            row = db.execute('SELECT until FROM leases WHERE key=?', (key,)).fetchone()
            if row and row[0] > now:
                return None
            db.execute('INSERT OR REPLACE INTO leases VALUES(?,?,?)', (key, token, now + ttl))
        return token

    def renew(self, key, token, now, ttl=120):
        with self.tx() as db:
            if not self._owns(db, key, token, now):
                return False
            db.execute('UPDATE leases SET until=? WHERE key=? AND token=?', (now + ttl, key, token))
            return True

    def release(self, key, token):
        with self.tx() as db:
            db.execute('DELETE FROM leases WHERE key=? AND token=?', (key, token))
