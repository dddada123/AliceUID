"""Transactional catalog, scoped shared blocks and owned redemption receipts."""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from .models import PRODUCT, RECENT_SUCCESS, retirement_at, clean, code_text, code_key


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
                CREATE TABLE IF NOT EXISTS member_codes (
                    product TEXT, code TEXT, state TEXT NOT NULL, verified_by TEXT NOT NULL,
                    first_verified REAL NOT NULL, last_verified REAL NOT NULL,
                    reason TEXT NOT NULL, PRIMARY KEY(product,code));
                CREATE TABLE IF NOT EXISTS code_details (
                    product TEXT, code TEXT, reward TEXT NOT NULL, expires_at REAL,
                    valid_from REAL, updated REAL NOT NULL, PRIMARY KEY(product,code));
                CREATE TABLE IF NOT EXISTS inventory_codes (
                    position INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL,
                    code_key TEXT NOT NULL, code TEXT NOT NULL, UNIQUE(product,code_key));
            ''')
            members = list(db.execute("SELECT * FROM member_codes WHERE state='active' ORDER BY first_verified,code"))
            names = {}
            for row in members:
                names.setdefault((row['product'], code_key(row['code'])), row['code'])
            sources = {row['name']: json.loads(row['value']) for row in db.execute('SELECT * FROM sources')}
            for source in ('official', 'gamewith'):
                for item in sources.get(source, {}).get('items', []):
                    if item.get('state') == 'candidate':
                        self._remember_inventory(db, PRODUCT, names.get((PRODUCT, code_key(item['code'])), item['code']))
            for row in members:
                self._remember_inventory(db, row['product'], row['code'])
            old = db.execute("SELECT value FROM sources WHERE name='gamewith'").fetchone()
            if old:
                snapshot = json.loads(old[0])
                self._remember_details(db, snapshot, snapshot.get('checked_at', 0))

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

    @staticmethod
    def _remember_inventory(db, product, code):
        db.execute('INSERT OR IGNORE INTO inventory_codes(product,code_key,code) VALUES(?,?,?)',
                   (product, code_key(code), code))

    def inventory(self, product):
        with self.tx() as db:
            return [dict(row) for row in db.execute('SELECT * FROM inventory_codes WHERE product=? ORDER BY position', (product,))]

    def publish(self, snapshots, now, errors, user_day=None, lease=None, cooldown=900):
        with self.tx() as db:
            if lease and not self._owns(db, 'catalog', lease, now):
                raise RuntimeError('catalog lease lost')
            for name, value in snapshots.items():
                for item in value.get('items', []):
                    if item.get('state') == 'candidate':
                        self._remember_inventory(db, PRODUCT, item['code'])
                db.execute('INSERT OR REPLACE INTO sources VALUES(?,?)',
                           (name, json.dumps(value, ensure_ascii=False)))
                if name == 'gamewith':
                    self._remember_details(db, value, now)
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

    @staticmethod
    def _remember_details(db, snapshot, now):
        for item in snapshot.get('items', []):
            try:
                code = code_text(item.get('code'))
            except (ValueError, AttributeError):
                continue
            old = db.execute('SELECT code FROM code_details WHERE product=? AND code=? COLLATE NOCASE ORDER BY updated DESC LIMIT 1',
                             (PRODUCT, code)).fetchone()
            if old:
                code = old['code']
            def timestamp(key):
                value = item.get(key)
                return value if (item.get('state') != 'uncertain' and type(value) in (int, float)
                                 and math.isfinite(value) and value > 0) else None
            db.execute('''INSERT INTO code_details VALUES(?,?,?,?,?,?)
                ON CONFLICT(product,code) DO UPDATE SET
                    reward=CASE WHEN excluded.reward!='' THEN excluded.reward ELSE code_details.reward END,
                    expires_at=COALESCE(excluded.expires_at,code_details.expires_at),
                    valid_from=COALESCE(excluded.valid_from,code_details.valid_from),updated=excluded.updated
                WHERE excluded.updated>=code_details.updated''',
                (PRODUCT, code, clean(item.get('reward')), timestamp('expires_at'), timestamp('valid_from'), now))

    def details(self, product):
        with self.tx() as db:
            result = {}
            for row in db.execute('SELECT * FROM code_details WHERE product=? ORDER BY updated DESC,LENGTH(reward) DESC', (product,)):
                key = code_key(row['code'])
                if key not in result:
                    result[key] = dict(row)
                else:
                    for field in ('reward', 'expires_at', 'valid_from'):
                        if not result[key][field] and row[field]:
                            result[key][field] = row[field]
            return result

    def detail(self, product, code):
        return self.details(product).get(code_key(code))

    def block(self, product, code, state, reason, now):
        with self.tx() as db:
            # Refreshes never write this table. A weaker time-window error cannot erase proven expiry.
            row = db.execute("SELECT code,state FROM blocks WHERE product=? AND code=? COLLATE NOCASE ORDER BY CASE WHEN state IN ('expired','invalid') THEN 0 ELSE 1 END,checked DESC LIMIT 1", (product, code)).fetchone()
            if row and row['state'] in ('expired', 'invalid'):
                return
            if row:
                code = row['code']
            db.execute('INSERT OR REPLACE INTO blocks VALUES(?,?,?,?,?)', (product, code, state, reason, now))
            db.execute('UPDATE member_codes SET state=?,reason=? WHERE product=? AND code=? COLLATE NOCASE',
                       (state if state in ('expired', 'invalid') else 'paused', reason, product, code))

    def members(self, product):
        with self.tx() as db:
            return [dict(r) for r in db.execute(
                "SELECT code,first_verified,last_verified FROM member_codes WHERE product=? AND state='active' ORDER BY first_verified,code",
                (product,))]

    def complete_success(self, account, product, code, now, *, contribute=False):
        """The verified submit's receipt and optional public admission commit together."""
        with self.tx() as db:
            receipt = self._receipt(db, account, code)
            if not receipt or receipt['state'] != 'submitting':
                raise RuntimeError('successful submit has no matching journal entry')
            db.execute('UPDATE receipts SET state=?,result=?,updated=? WHERE account=? AND code=? COLLATE NOCASE',
                       ('success', '兑换成功', now, account, code))
            if not contribute:
                return None
            return self._admit(db, account, product, code, now, now)

    @staticmethod
    def _admit(db, account, product, code, now, verified):
        if db.execute('SELECT 1 FROM blocks WHERE product=? AND code=? COLLATE NOCASE', (product, code)).fetchone():
            return 'blocked'
        detail = db.execute('SELECT expires_at FROM code_details WHERE product=? AND code=? COLLATE NOCASE AND expires_at IS NOT NULL ORDER BY updated DESC LIMIT 1', (product, code)).fetchone()
        if detail and retirement_at(dict(detail)) and now >= retirement_at(dict(detail)):
            return 'blocked'
        old = db.execute("SELECT state FROM member_codes WHERE product=? AND code=? COLLATE NOCASE ORDER BY CASE WHEN state='active' THEN 1 ELSE 0 END LIMIT 1", (product, code)).fetchone()
        if old:
            if old[0] != 'active':
                return 'blocked'
            db.execute('UPDATE member_codes SET last_verified=MAX(last_verified,?) WHERE product=? AND code=? COLLATE NOCASE',
                       (verified, product, code))
            return 'existing'
        Store._remember_inventory(db, product, code)
        db.execute('INSERT INTO member_codes VALUES(?,?,?,?,?,?,?)',
                   (product, code, 'active', account, verified, verified, '官方明确成功记录'))
        return 'added'

    def contribute_recent(self, account, product, code, now):
        """Reuse only this bound account's actual success; never renew its timestamp."""
        with self.tx() as db:
            receipt = self._receipt(db, account, code)
            if not receipt or receipt['state'] != 'success' or not 0 <= now - receipt['updated'] <= RECENT_SUCCESS:
                return None
            return self._admit(db, account, product, code, now, receipt['updated'])

    def receipt(self, account, code):
        with self.tx() as db:
            row = self._receipt(db, account, code)
            return dict(row) if row else None

    @staticmethod
    def _receipt(db, account, code):
        # Legacy casing duplicates stay on disk; strongest evidence wins.
        return db.execute("""SELECT * FROM receipts WHERE account=? AND code=? COLLATE NOCASE
            ORDER BY CASE state WHEN 'success' THEN 0 WHEN 'claimed' THEN 1
                WHEN 'submitting' THEN 2 WHEN 'uncertain' THEN 3 ELSE 4 END,updated DESC LIMIT 1""",
            (account, code)).fetchone()

    def record(self, account, code, state, result, now):
        with self.tx() as db:
            old = self._receipt(db, account, code)
            if old and old['state'] in ('success', 'claimed'):
                return
            if old:
                code = old['code']
            db.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?,?,?)', (account, code, state, result, now))

    def claim(self, account, code, token, now):
        with self.tx() as db:
            if not self._owns(db, 'account:' + account, token, now):
                return False
            old = self._receipt(db, account, code)
            if old and old['state'] in ('success', 'claimed', 'submitting', 'uncertain'):
                return False
            if old:
                code = old['code']
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
