"""Persistent sign-in attempts and consecutive-cycle failure policy (no credentials)."""
from datetime import date, timedelta
from .cycle import cycle_day


class Lifecycle:
    def init_lifecycle(self, db):
        columns = {r[1] for r in db.execute('PRAGMA table_info(accounts)')}
        for name, spec in {'generation':'INTEGER NOT NULL DEFAULT 0', 'fail_count':'INTEGER NOT NULL DEFAULT 0',
                           'fail_day':"TEXT NOT NULL DEFAULT ''", 'auto_disabled':"TEXT NOT NULL DEFAULT ''"}.items():
            if name not in columns:
                db.execute(f'ALTER TABLE accounts ADD COLUMN {name} {spec}')
        db.execute('''CREATE TABLE IF NOT EXISTS signin_runs (
            account TEXT, owner TEXT, day TEXT, generation INTEGER NOT NULL,
            status TEXT NOT NULL, attempts INTEGER NOT NULL, first_at REAL NOT NULL,
            updated_at REAL NOT NULL, next_at REAL, eligible INTEGER NOT NULL,
            reason TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
            streak INTEGER NOT NULL DEFAULT 0, auto_stopped INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(account,owner,day))''')
        db.execute('CREATE TABLE IF NOT EXISTS signin_checked (owner TEXT, day TEXT, PRIMARY KEY(owner,day))')
        db.execute('CREATE TABLE IF NOT EXISTS signin_login_notices (owner TEXT PRIMARY KEY, notice TEXT NOT NULL)')
        if not db.execute("SELECT 1 FROM metadata WHERE key='lifecycle_v118'").fetchone():
            # Only recognizable transient/credential pauses with still-valid consent migrate.
            for prefix in ('HTTP 异常', '网络或响应异常', '登录已失效', '社区返回业务异常'):
                db.execute("UPDATE accounts SET paused='' WHERE enabled=1 AND paused LIKE ?", (prefix+'%',))
            db.execute("INSERT INTO metadata VALUES('lifecycle_v118','1')")

    def result(self, account, owner, day):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM signin_runs WHERE account=? AND owner=? AND day=?', (account,owner,day)).fetchone()
            return dict(row) if row else None

    def owner_accounts(self, owner):
        with self.transaction() as db:
            return [dict(r) for r in db.execute('SELECT * FROM accounts WHERE owner=?', (owner,))]

    def start_run(self, account, owner, day, now, *, manual=False):
        with self.transaction() as db:
            acc = db.execute('SELECT * FROM accounts WHERE account=? AND owner=?',(account,owner)).fetchone()
            if not acc or acc['paused'] or (not acc['enabled'] and not manual):
                return None
            old = db.execute('SELECT * FROM signin_runs WHERE account=? AND owner=? AND day=?',(account,owner,day)).fetchone()
            same = old is not None and old['generation'] == acc['generation']
            if same:
                if old['status']=='running' and old['updated_at']+900>now:
                    return None
                if not manual and (old['status'] in ('success','failed','cancelled') or
                        (old['status']=='retry' and old['next_at']>now)):
                    return None
            attempts = old['attempts']+1 if same else 1
            first = old['first_at'] if same else now
            db.execute('''INSERT INTO signin_runs(account,owner,day,generation,status,attempts,first_at,updated_at,next_at,eligible)
                VALUES(?,?,?,?,'running',?,?,?,NULL,?) ON CONFLICT(account,owner,day) DO UPDATE SET
                generation=excluded.generation,status='running',attempts=excluded.attempts,
                first_at=excluded.first_at,updated_at=excluded.updated_at,next_at=NULL,
                eligible=excluded.eligible,reason='',category='',streak=0,auto_stopped=0''',
                (account,owner,day,acc['generation'],attempts,first,now,int(bool(acc['enabled']))))
            return dict(account=account,owner=owner,day=day,generation=acc['generation'],attempts=attempts,
                        first_at=first,eligible=bool(acc['enabled']))

    def finish_run(self, token, now, *, success=False, reason='', category='', retryable=False, cancelled=False):
        account,owner,day,gen = (token[k] for k in ('account','owner','day','generation'))
        with self.transaction() as db:
            acc = db.execute('SELECT * FROM accounts WHERE account=? AND owner=? AND generation=?',(account,owner,gen)).fetchone()
            run = db.execute('SELECT * FROM signin_runs WHERE account=? AND owner=? AND day=? AND generation=?',
                             (account,owner,day,gen)).fetchone()
            if not acc or not run or run['attempts']!=token['attempts']:
                return None
            if run['status']=='success' and not success:
                return dict(run)
            if cycle_day(now)!=day:
                cancelled=True
            status, next_at, streak, stopped = 'failed',None,0,0
            if cancelled:
                status='cancelled'
            elif success:
                status='success'
                db.execute("UPDATE accounts SET fail_count=0,fail_day='',last_day=? WHERE account=? AND generation=?",(day,account,gen))
            else:
                delay = 120 if run['attempts']==1 else 600
                if (retryable and run['eligible'] and acc['enabled'] and not acc['paused'] and run['attempts']<3
                        and now+delay<=run['first_at']+1200 and cycle_day(now+delay)==day):
                    status,next_at='retry',now+delay
                    db.execute("UPDATE accounts SET last_day='' WHERE account=? AND generation=?",(account,gen))
                elif run['eligible'] and acc['enabled']:
                    yesterday=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
                    streak = acc['fail_count'] if acc['fail_day']==day else (acc['fail_count']+1 if acc['fail_day']==yesterday else 1)
                    stopped=int(streak>=3)
                    db.execute('''UPDATE accounts SET fail_count=?,fail_day=?,last_day=?,enabled=?,
                        auto_disabled=? WHERE account=? AND generation=?''',
                        (streak,day,day,0 if stopped else 1,'consecutive_failures' if stopped else '',account,gen))
            db.execute('''UPDATE signin_runs SET status=?,updated_at=?,next_at=?,reason=?,category=?,streak=?,auto_stopped=?
                       WHERE account=? AND owner=? AND day=? AND generation=?''',
                       (status,now,next_at,reason,category,streak,stopped,account,owner,day,gen))
            return dict(db.execute('SELECT * FROM signin_runs WHERE account=? AND owner=? AND day=?',(account,owner,day)).fetchone())

    def due_runs(self, now):
        with self.transaction() as db:
            return [dict(r) for r in db.execute('''SELECT r.* FROM signin_runs r JOIN accounts a ON r.account=a.account
                AND r.owner=a.owner AND r.generation=a.generation WHERE a.enabled=1 AND a.paused=''
                AND ((r.status='retry' AND r.next_at<=?) OR (r.status='running' AND r.updated_at+900<=?))''',(now,now))]

    def recovery_snapshot(self, account, owner):
        state=self.state(account)
        if state.get('owner')!=owner:
            return None
        return dict(account=account,owner=owner,generation=state['generation'],
                    restore=bool(state['enabled'] or state['auto_disabled']=='consecutive_failures'),likes=state['likes'])

    def transfer_login(self, snapshot, new_owner, day):
        if not snapshot:
            return False
        with self.transaction() as db:
            old=db.execute('SELECT * FROM accounts WHERE account=? AND owner=? AND generation=?',
                           (snapshot['account'],snapshot['owner'],snapshot['generation'])).fetchone()
            if not old:
                return False
            restore=bool(snapshot['restore'])
            db.execute('''UPDATE accounts SET owner=?,generation=generation+1,enabled=?,likes=?,paused='',
                lease='',lease_until=0,manual_lease=0,fail_count=0,fail_day='',auto_disabled=''
                WHERE account=? AND owner=? AND generation=?''',
                (new_owner,int(restore),snapshot['likes'] if restore else 0,snapshot['account'],snapshot['owner'],snapshot['generation']))
            db.execute('UPDATE signin_confirmations SET owner=? WHERE account=? AND owner=? AND day=?',
                       (new_owner,snapshot['account'],snapshot['owner'],day))
            db.execute("UPDATE signin_runs SET status='cancelled',next_at=NULL WHERE account=? AND owner=? AND status IN ('running','retry')",
                       (snapshot['account'],snapshot['owner']))
            return restore

    def login_notice(self, owner, value=None):
        with self.transaction() as db:
            if value is not None:
                db.execute('INSERT OR REPLACE INTO signin_login_notices VALUES(?,?)',(owner,value))
            row=db.execute('SELECT notice FROM signin_login_notices WHERE owner=?',(owner,)).fetchone()
            return row[0] if row else ''

    def mark_processed(self, owner, day):
        with self.transaction() as db:db.execute('INSERT OR IGNORE INTO signin_checked VALUES(?,?)',(owner,day))

    def processed(self, owner, day):
        with self.transaction() as db:
            return db.execute('SELECT 1 FROM signin_checked WHERE owner=? AND day=?',(owner,day)).fetchone() is not None


    def cancel_pending(self, now, reason):
        with self.transaction() as db:
            rows=[dict(r) for r in db.execute("SELECT * FROM signin_runs WHERE status='retry'")]
        for row in rows:
            self.finish_run(row,now,cancelled=True,reason=reason)
