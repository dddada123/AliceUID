"""Durable notification defaults, per-route overrides and recoverable bulk saves."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid


class NotificationPolicy:
    def __init__(self, path, enabled=True, white=(), black=()):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS notify_policy (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS notify_overrides (route TEXT PRIMARY KEY, enabled INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS notify_policy_pending (id INTEGER PRIMARY KEY, token TEXT, enabled INTEGER)')
            seed=dict(default=bool(enabled),config_value=bool(enabled),epoch=0,white=list(white),black=list(black))
            db.execute('INSERT OR IGNORE INTO notify_policy VALUES(1,?)',(json.dumps(seed),))

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback();raise
        finally:
            db.close()

    @staticmethod
    def apply(db, value):
        old=json.loads(db.execute('SELECT payload FROM notify_policy WHERE id=1').fetchone()[0])
        state=dict(default=bool(value),config_value=bool(value),epoch=old['epoch']+1,white=[],black=[])
        db.execute('UPDATE notify_policy SET payload=? WHERE id=1',(json.dumps(state),))
        db.execute('DELETE FROM notify_overrides')
        db.execute('DELETE FROM notify_policy_pending')

    def sync(self, value):
        if type(value) is not bool:raise ValueError('invalid notification default')
        with self.tx() as db:
            state=json.loads(db.execute('SELECT payload FROM notify_policy WHERE id=1').fetchone()[0])
            pending=db.execute('SELECT enabled FROM notify_policy_pending WHERE id=1').fetchone()
            if pending:
                if bool(pending[0])==value:self.apply(db,value)
                else:db.execute('DELETE FROM notify_policy_pending')
            elif state['config_value']!=value:
                self.apply(db,value)

    def prepare(self, value):
        token=uuid.uuid4().hex
        with self.tx() as db:
            db.execute('INSERT OR REPLACE INTO notify_policy_pending VALUES(1,?,?)',(token,int(value)))
        return token

    def finish(self, token):
        with self.tx() as db:
            row=db.execute('SELECT enabled FROM notify_policy_pending WHERE token=?',(token,)).fetchone()
            if row:self.apply(db,bool(row[0]))

    def cancel(self, token):
        with self.tx() as db:db.execute('DELETE FROM notify_policy_pending WHERE token=?',(token,))

    def bulk(self, value):
        with self.tx() as db:self.apply(db,value)

    @staticmethod
    def key(bot, own, group):
        if not all(isinstance(v,str) and v for v in (bot,own,group)):
            raise ValueError('missing group route identity')
        return json.dumps([bot,own,group],separators=(',',':'))

    def set_group(self, bot, own, group, value):
        key=self.key(bot,own,group)
        with self.tx() as db:db.execute('INSERT OR REPLACE INTO notify_overrides VALUES(?,?)',(key,int(value)))

    def state(self, bot=None, own=None, group=None):
        with self.tx() as db:
            state=json.loads(db.execute('SELECT payload FROM notify_policy WHERE id=1').fetchone()[0])
            state['overrides']=db.execute('SELECT count(*) FROM notify_overrides').fetchone()[0]
            override=None
            if bot and own and group:
                override=db.execute('SELECT enabled FROM notify_overrides WHERE route=?',(self.key(bot,own,group),)).fetchone()
            value=state['default']
            if value and state['white']:value=group in state['white']
            elif value and state['black']:value=group not in state['black']
            state.update(enabled=bool(override[0]) if override else bool(value),individual=override is not None)
            return state
