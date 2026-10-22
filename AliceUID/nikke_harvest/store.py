"""Durable account progress, per-conversation consent and at-most-once notices."""
from contextlib import contextmanager
import json
from decimal import Decimal
from pathlib import Path
import sqlite3


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS accounts (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS subscriptions (id TEXT PRIMARY KEY, account TEXT NOT NULL,
                    enabled INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS sub_account ON subscriptions(account, enabled);
                CREATE TABLE IF NOT EXISTS nightly (account TEXT, day TEXT, full INTEGER,
                    sampled REAL, PRIMARY KEY(account, day));
                CREATE TABLE IF NOT EXISTS notices (id TEXT PRIMARY KEY, sub TEXT, account TEXT,
                    status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS notice_status ON notices(status);
                CREATE TABLE IF NOT EXISTS leases (account TEXT PRIMARY KEY, until REAL);
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

    def account(self, key):
        with self.tx() as db:
            row = db.execute('SELECT payload FROM accounts WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def accounts(self):
        with self.tx() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT payload FROM accounts')]

    def sub(self, sid):
        with self.tx() as db:
            row = db.execute('SELECT payload FROM subscriptions WHERE id=?', (sid,)).fetchone()
            return json.loads(row[0]) if row else None

    def subs(self, key, active=True):
        with self.tx() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT payload FROM subscriptions WHERE account=?' +
                    (' AND enabled=1' if active else ''), (key,))]

    def save_sub(self, sub):
        with self.tx() as db:
            db.execute('INSERT OR REPLACE INTO subscriptions VALUES(?,?,?,?)',
                       (sub['id'], sub['account'], int(sub['enabled']), encode(sub)))

    def save_account(self, account, expected=None):
        with self.tx() as db:
            row = db.execute('SELECT payload FROM accounts WHERE key=?', (account['key'],)).fetchone()
            if expected is not None and (not row or json.loads(row[0])['generation'] != expected):
                return False
            db.execute('INSERT OR REPLACE INTO accounts VALUES(?,?)', (account['key'], encode(account)))
            return True

    def enqueue(self, notice):
        with self.tx() as db:
            return db.execute("INSERT INTO notices VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status='ready',payload=excluded.payload WHERE notices.status='discarded'",
                              (notice['id'], notice['sub'], notice['account'], 'ready', encode(notice))).rowcount == 1

    def seen(self, sid, cycle):
        with self.tx() as db:
            row = db.execute('SELECT status FROM notices WHERE id=?', (f'{sid}:{cycle}',)).fetchone()
            return row is not None and row[0] != 'discarded'

    def ready(self):
        with self.tx() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM notices WHERE status='ready'")]

    def mark(self, nid, status):
        with self.tx() as db:
            db.execute('UPDATE notices SET status=? WHERE id=?', (status, nid))

    def reserve(self, nid):
        with self.tx() as db:
            return db.execute("UPDATE notices SET status='unknown' WHERE id=? AND status='ready'", (nid,)).rowcount == 1

    def disable_sub(self, sid, reason='manual'):
        with self.tx() as db:
            row = db.execute('SELECT payload FROM subscriptions WHERE id=?', (sid,)).fetchone()
            if not row:
                return None
            sub = json.loads(row[0])
            sub.update(enabled=False, reason=reason, generation=sub['generation']+1)
            db.execute('UPDATE subscriptions SET enabled=0,payload=? WHERE id=?', (encode(sub), sid))
            db.execute("UPDATE notices SET status='discarded' WHERE sub=? AND status='ready'", (sid,))
            return sub

    def stop(self, key, generation, reason, now):
        with self.tx() as db:
            row = db.execute('SELECT payload FROM accounts WHERE key=?', (key,)).fetchone()
            if not row:
                return None
            acc = json.loads(row[0])
            if acc['generation'] != generation:
                return None
            acc.update(phase='AUTO_STOPPED' if reason == 'two_full_nights' else 'OFF',
                       generation=generation+1, due=None, reason=reason, stopped_at=now)
            db.execute('UPDATE accounts SET payload=? WHERE key=?', (encode(acc), key))
            for row in db.execute('SELECT id,payload FROM subscriptions WHERE account=? AND enabled=1', (key,)).fetchall():
                sub = json.loads(row['payload'])
                sub.update(enabled=False, generation=sub['generation']+1, reason=reason)
                db.execute('UPDATE subscriptions SET enabled=0,payload=? WHERE id=?', (encode(sub), row['id']))
            db.execute("UPDATE notices SET status='discarded' WHERE account=? AND status='ready'", (key,))
            return acc

    def nightly(self, account, snap):
        from datetime import datetime, timedelta
        from .planner import TZ
        dt = datetime.fromtimestamp(snap['at'], TZ)
        if dt.hour != 23:
            return account
        day = dt.date().isoformat()
        full = Decimal(snap['p']) == 100
        with self.tx() as db:
            current = db.execute('SELECT payload FROM accounts WHERE key=?', (account['key'],)).fetchone()
            if not current or json.loads(current[0])['generation'] != account['generation']:
                return account
            added = db.execute('INSERT OR IGNORE INTO nightly VALUES(?,?,?,?)',
                               (account['key'], day, int(full), snap['at'])).rowcount
            if added:
                yesterday = (dt.date()-timedelta(days=1)).isoformat()
                count = account.get('full_nights', 0)
                count = count+1 if full and account.get('night_date') == yesterday else int(full)
                account.update(full_nights=count, night_date=day)
                db.execute('UPDATE accounts SET payload=? WHERE key=?', (encode(account), account['key']))
        return account

    def reset_nights(self, key):
        with self.tx() as db:
            db.execute('DELETE FROM nightly WHERE account=?', (key,))

    def claim(self, key, now):
        with self.tx() as db:
            row = db.execute('SELECT until FROM leases WHERE account=?', (key,)).fetchone()
            if row and row[0] > now:
                return False
            db.execute('INSERT OR REPLACE INTO leases VALUES(?,?)', (key, now+180))
            return True

    def release(self, key):
        with self.tx() as db:
            db.execute('DELETE FROM leases WHERE account=?', (key,))
