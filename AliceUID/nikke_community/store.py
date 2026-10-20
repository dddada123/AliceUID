"""SQLite stores consent, counters and deduplication hashes, never credentials.

One SQLite file must be shared by all schedulers. Short BEGIN IMMEDIATE
transactions atomically reserve budgets before a network request is sent.
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .api import CommunityError


def digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(str(p) for p in parts).encode()).hexdigest()


class CommunityStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, likes INTEGER NOT NULL DEFAULT 0,
                    paused TEXT NOT NULL DEFAULT '', last_day TEXT NOT NULL DEFAULT '',
                    lease TEXT NOT NULL DEFAULT '', lease_until REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS budgets (
                    account TEXT, day TEXT, requests INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(account, day)
                );
                CREATE TABLE IF NOT EXISTS actions (
                    account TEXT, kind TEXT, target TEXT, day TEXT,
                    outcome TEXT NOT NULL DEFAULT 'reserved',
                    PRIMARY KEY(account, kind, target, day)
                );
                CREATE TABLE IF NOT EXISTS pacing (
                    id INTEGER PRIMARY KEY CHECK(id=1), next_at REAL NOT NULL
                );
                INSERT OR IGNORE INTO pacing(id,next_at) VALUES (1, 0);
            """)
            columns = {row[1] for row in db.execute('PRAGMA table_info(accounts)')}
            if 'manual_lease' not in columns:
                db.execute('ALTER TABLE accounts ADD COLUMN manual_lease INTEGER NOT NULL DEFAULT 0')
            pacing_columns = {row[1] for row in db.execute('PRAGMA table_info(pacing)')}
            if 'last_account' not in pacing_columns:
                db.execute("ALTER TABLE pacing ADD COLUMN last_account TEXT NOT NULL DEFAULT ''")
            if 'switch_at' not in pacing_columns:
                db.execute('ALTER TABLE pacing ADD COLUMN switch_at REAL NOT NULL DEFAULT 0')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS signin_confirmations ('
                       'account TEXT, day TEXT, owner TEXT NOT NULL, confirmed_at REAL NOT NULL, source TEXT NOT NULL,'
                       'PRIMARY KEY(account,day))')
            db.execute('CREATE TABLE IF NOT EXISTS group_seen ('
                       'group_key TEXT, actor_id TEXT, seen_at REAL NOT NULL, PRIMARY KEY(group_key,actor_id))')
            if not any(db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in ('accounts','budgets','actions')):
                db.execute("INSERT OR IGNORE INTO metadata VALUES('cycle_bjt08_v104','fresh')")

    def migrate_cycle(self, day, utc_day=None):
        """Retain guards when moving old 23:00 ledgers to the 08:00 period.

        Legacy rows have no timestamps, so overlapping budgets and uncertain
        writes are conservatively carried for the first period only. Never
        manufacture a successful sign-in confirmation from last_day.
        """
        from datetime import date, timedelta
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='cycle_bjt08_v104'").fetchone():
                return
            legacy = {day}
            if db.execute("SELECT 1 FROM metadata WHERE key='cycle_bjt23'").fetchone():
                legacy.add((date.fromisoformat(day)-timedelta(days=1)).isoformat())
            placeholders = ','.join('?' for _ in legacy)
            actions = db.execute(f'SELECT * FROM actions WHERE day IN ({placeholders})',tuple(legacy)).fetchall()
            likes = db.execute("SELECT * FROM actions WHERE kind='like'").fetchall()
            for row in db.execute('SELECT account,last_day FROM accounts').fetchall():
                used = db.execute(f'SELECT COALESCE(sum(requests),0) FROM budgets WHERE account=? AND day IN ({placeholders})',
                                  (row['account'],*legacy)).fetchone()[0]
                if used:
                    db.execute('INSERT INTO budgets(account,day,requests) VALUES(?,?,?) ON CONFLICT(account,day) DO UPDATE SET requests=max(requests,excluded.requests)',
                               (row['account'],day,used))
                if row['last_day'] in legacy:
                    # Permit a bounded task-status recheck without erasing any
                    # old action reservations or treating an old run as success.
                    db.execute("UPDATE accounts SET last_day='' WHERE account=?",(row['account'],))
            for row in actions:
                outcome = day + ':legacy_' + row['outcome'].split(':')[-1]
                db.execute('INSERT INTO actions(account,kind,target,day,outcome) VALUES(?,?,?,?,?) '
                           'ON CONFLICT(account,kind,target,day) DO UPDATE SET outcome=excluded.outcome',
                           (row['account'],row['kind'],row['target'],day,outcome))
            for row in likes:
                if row['outcome'].split(':',1)[0] in legacy:
                    db.execute('UPDATE actions SET outcome=? WHERE account=? AND kind=? AND target=? AND day=?',
                               (day+':legacy_'+row['outcome'].split(':')[-1],row['account'],row['kind'],row['target'],row['day']))
            db.execute("INSERT INTO metadata VALUES('cycle_bjt08_v104',?)",(day,))

    def carry_boundary_guard(self, account, day, action=None):
        """Count a crossing request in the new period; never guess its write day."""
        with self.transaction() as db:
            db.execute('INSERT INTO budgets(account,day,requests) VALUES(?,?,1) '
                       'ON CONFLICT(account,day) DO UPDATE SET requests=requests+1',(account,day))
            if action:
                kind,target = action
                action_day = 'ever' if kind == 'like' else day
                db.execute('INSERT INTO actions(account,kind,target,day,outcome) VALUES(?,?,?,?,?) '
                           'ON CONFLICT(account,kind,target,day) DO UPDATE SET outcome=excluded.outcome',
                           (account,kind,digest(target),action_day,day+':boundary_unconfirmed'))

    def confirm_signin(self, account, owner, day, now, source):
        if source not in ('request_success','server_confirmed'):
            raise ValueError('unknown confirmation source')
        with self.transaction() as db:
            row = db.execute('SELECT owner FROM accounts WHERE account=?',(account,)).fetchone()
            if row is None or row['owner'] != owner:
                raise CommunityError('绑定授权已变化，签到记录未写入新绑定')
            db.execute('INSERT INTO signin_confirmations(account,day,owner,confirmed_at,source) VALUES(?,?,?,?,?) '
                       'ON CONFLICT(account,day) DO UPDATE SET owner=excluded.owner,confirmed_at=excluded.confirmed_at,source=excluded.source',
                       (account,day,owner,now,source))

    def signin_status(self, account, owner, day):
        with self.transaction() as db:
            row = db.execute('SELECT confirmed_at,source FROM signin_confirmations WHERE account=? AND owner=? AND day=?',
                             (account,owner,day)).fetchone()
            if row is not None:
                return dict(confirmed=True,**dict(row))
            attempts = db.execute("SELECT outcome FROM actions WHERE account=? AND kind='signin' AND day=?",(account,day)).fetchall()
            return dict(confirmed=False,uncertain=any('reserved' in r['outcome'] or 'legacy_' in r['outcome'] or 'boundary_' in r['outcome'] for r in attempts),
                        attempted=bool(attempts))

    def observe_group(self, actor_id, bot_id, group_id, now):
        if not all(isinstance(v,str) and 0<len(v)<=128 for v in (actor_id,bot_id,group_id)):
            return
        key = digest('group',bot_id,group_id)
        with self.transaction() as db:
            db.execute('INSERT INTO group_seen(group_key,actor_id,seen_at) VALUES(?,?,?) '
                       'ON CONFLICT(group_key,actor_id) DO UPDATE SET seen_at=excluded.seen_at '
                       'WHERE excluded.seen_at-group_seen.seen_at>=60',(key,actor_id,now))

    def group_actors(self, bot_id, group_id, now):
        with self.transaction() as db:
            return {row['actor_id'] for row in db.execute('SELECT actor_id FROM group_seen WHERE group_key=? AND seen_at>=?',
                    (digest('group',bot_id,group_id),now-30*86400))}

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def state(self, account: str) -> dict:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM accounts WHERE account=?", (account,)).fetchone()
            return dict(row) if row else {"enabled": 0, "likes": 0, "paused": "", "last_day": ""}

    def consent(self, account: str, owner: str, enabled: bool, likes: bool = False):
        with self.transaction() as db:
            existing = db.execute("SELECT owner,enabled,paused FROM accounts WHERE account=?", (account,)).fetchone()
            if existing and existing["owner"] != owner and (existing["enabled"] or existing["paused"] != "绑定已变更"):
                raise CommunityError("该账号已有其他绑定授权，请先解除原绑定")
            # Re-enabling does not erase today's attempts, run marker, or pacing.
            db.execute("""INSERT INTO accounts(account,owner,enabled,likes) VALUES(?,?,?,?)
                ON CONFLICT(account) DO UPDATE SET enabled=excluded.enabled,
                owner=excluded.owner,likes=excluded.likes,paused='',manual_lease=0""", (account, owner, int(enabled), int(likes)))

    def disable_likes(self, account: str, owner: str):
        with self.transaction() as db:
            row = db.execute("SELECT owner FROM accounts WHERE account=?", (account,)).fetchone()
            if row is None:
                return
            if row["owner"] != owner:
                raise CommunityError("该账号授权属于其他绑定，不能修改")
            db.execute("UPDATE accounts SET likes=0 WHERE account=? AND owner=?", (account, owner))

    def revoke(self, owner: str):
        """Call BEFORE unbind/rebind; preserve ledgers while erasing consent."""
        with self.transaction() as db:
            db.execute("UPDATE accounts SET enabled=0,likes=0,manual_lease=0,paused='绑定已变更' WHERE owner=?", (owner,))

    def reconcile(self, active_owners: set[str]):
        with self.transaction() as db:
            for row in db.execute("SELECT account,owner FROM accounts").fetchall():
                if row["owner"] not in active_owners:
                    db.execute("UPDATE accounts SET enabled=0,likes=0,manual_lease=0,paused='绑定已变更' WHERE account=?", (row["account"],))

    def acquire(self, account: str, owner: str, lease: str, now: float, day: str, *, manual=False) -> bool:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM accounts WHERE account=?", (account,)).fetchone()
            if not row or row["owner"] != owner or (not row["enabled"] and not manual) or row["paused"] or (row["last_day"] == day and not manual):
                return False
            # A global lease also serializes separate service instances/processes.
            if db.execute("SELECT 1 FROM accounts WHERE lease_until>?", (now,)).fetchone():
                return False
            db.execute("UPDATE accounts SET lease=?,lease_until=?,manual_lease=? WHERE account=?", (lease, now + 600, int(manual and not row['enabled']),account))
            return True

    def release(self, account: str, lease: str, day: str, *, finished: bool):
        with self.transaction() as db:
            if finished:
                db.execute("UPDATE accounts SET last_day=? WHERE account=? AND lease=?", (day, account, lease))
            db.execute("UPDATE accounts SET lease='',lease_until=0,manual_lease=0 WHERE account=? AND lease=?", (account, lease))

    def pause(self, account: str, reason: str, owner: str):
        with self.transaction() as db:
            db.execute("UPDATE accounts SET paused=? WHERE account=? AND owner=?", (reason, account, owner))

    def reserve(self, account: str, lease: str, owner: str, day: str, now: float, interval: float,
                max_requests: int, action: tuple[str, str] | None = None, *, switch_interval=0) -> tuple[str, float]:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM accounts WHERE account=?", (account,)).fetchone()
            if not row or row["owner"] != owner or (not row["enabled"] and not row['manual_lease']) or row["paused"] or row["lease"] != lease or row["lease_until"] <= now:
                raise CommunityError("授权已关闭、暂停或执行租约已失效")
            if action and action[0] == "like" and not row["likes"]:
                return "disabled", 0
            kind, target = action or ("", "")
            action_day = "ever" if kind == "like" else day
            target = digest(target)
            if action and db.execute("SELECT 1 FROM actions WHERE account=? AND kind=? AND target=? AND day=?",
                                     (account, kind, target, action_day)).fetchone():
                return "duplicate", 0
            # Count reserved (including failed/uncertain) actions, not only successes.
            if action:
                limit = {"signin": 1, "browse": 5, "like": 5}[kind]
                count = db.execute("SELECT count(*) FROM actions WHERE account=? AND kind=? AND (day=? OR (kind='like' AND rowid IN (SELECT rowid FROM actions WHERE account=? AND kind='like' AND outcome LIKE ?)))",
                                   (account, kind, day, account, day + ':%')).fetchone()[0]
                if count >= limit:
                    return "limit", 0
            db.execute("INSERT OR IGNORE INTO budgets(account,day) VALUES(?,?)", (account, day))
            used = db.execute("SELECT requests FROM budgets WHERE account=? AND day=?", (account, day)).fetchone()[0]
            if used >= max_requests:
                return "limit", 0
            pacing = db.execute('SELECT next_at,last_account,switch_at FROM pacing WHERE id=1').fetchone()
            next_at = max(pacing['next_at'], pacing['switch_at'] if pacing['last_account'] and pacing['last_account'] != account else 0)
            if next_at > now:
                db.execute('UPDATE accounts SET lease_until=? WHERE account=? AND lease=?',
                           (next_at + 600, account, lease))
                return "wait", next_at - now
            db.execute('UPDATE pacing SET next_at=?,last_account=?,switch_at=? WHERE id=1',
                       (now + interval, account, now + switch_interval))
            db.execute("UPDATE accounts SET lease_until=? WHERE account=? AND lease=?", (now + 600, account, lease))
            db.execute("UPDATE budgets SET requests=requests+1 WHERE account=? AND day=?", (account, day))
            if action:
                db.execute("INSERT INTO actions(account,kind,target,day,outcome) VALUES(?,?,?,?,?)",
                           (account, kind, target, action_day, day + ':reserved'))
            return "send", 0

    def finish_request(self, account, now, switch_interval):
        with self.transaction() as db:
            db.execute('UPDATE pacing SET switch_at=max(switch_at,?) WHERE id=1 AND last_account=?',
                       (now + switch_interval, account))

    def record(self, account: str, day: str, action: tuple[str, str]):
        kind, target = action
        with self.transaction() as db:
            db.execute("UPDATE actions SET outcome=? WHERE account=? AND kind=? AND target=? AND day=?",
                       (day + ':ok', account, kind, digest(target), "ever" if kind == "like" else day))
