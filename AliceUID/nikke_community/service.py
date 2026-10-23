"""Opt-in community runner, independent of the bot framework.

Only the binding owner may authorize. Caller must resolve the client's current
binding, and supply a binding revision that changes on every rebind.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .api import CommunityAPI, CommunityError, DYNAMICS, POINTS, STAR, parse_tasks
from .store import CommunityStore, digest
from .cycle import cycle_day


class CycleBoundary(Exception):
    """A response arrived after the server-period boundary."""


@dataclass(frozen=True)
class Policy:
    min_interval: float = 5.0
    daily_requests: int = 30
    max_interval: float = 15.0
    switch_min: float = 10.0
    switch_max: float = 120.0

    def __post_init__(self):
        values = (self.min_interval, self.max_interval, self.switch_min, self.switch_max)
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in values)
                or not 1 <= self.min_interval <= self.max_interval <= 3600
                or not 1 <= self.switch_min <= self.switch_max <= 3600
                or type(self.daily_requests) is not int or not 1 <= self.daily_requests <= 30):
            raise ValueError("Community ranges: 1..3600s, daily requests 1..30")


class CommunityService:
    def __init__(self, store: CommunityStore, *, policy: Policy | None = None,
                 clock: Callable = time.time, sleep: Callable = asyncio.sleep,
                 allowed: Callable = lambda: True, user_allowed: Callable = lambda actor_id: True,
                 uniform: Callable = random.uniform):
        self.allowed = allowed
        self.user_allowed = user_allowed
        self.store = store
        self.policy = policy or Policy()
        self.clock, self.sleep = clock, sleep
        self.uniform = uniform
        self._serial = asyncio.Lock()
        self.binding_current = None

    def prepare_cycle(self):
        day = cycle_day(self.clock())
        self.store.migrate_cycle(day, datetime.fromtimestamp(self.clock(),timezone.utc).date().isoformat())
        return day

    @staticmethod
    def identity(client) -> str:
        return digest(client.credentials.game_id, client.credentials.openid)

    @staticmethod
    def owner(actor_id: str, bot_id: str, binding_revision: str) -> str:
        if not actor_id or not bot_id or not binding_revision:
            raise ValueError("actor, bot and stable binding revision are required")
        return digest(actor_id, bot_id, binding_revision)

    def configure(self, client, actor_id: str, bot_id: str, binding_revision: str,
                  *, enabled: bool, likes: bool = False):
        self.store.consent(self.identity(client), self.owner(actor_id, bot_id, binding_revision), enabled, likes)

    def pause_owner(self, actor_id: str, bot_id: str, binding_revision: str):
        owner = self.owner(actor_id, bot_id, binding_revision)
        with self.store.transaction() as db:
            db.execute("UPDATE accounts SET paused=? WHERE owner=?",
                       ("当前用户无权使用AliceUID，社区任务已暂停", owner))

    def revoke(self, actor_id: str, bot_id: str, binding_revision: str):
        self.store.revoke(self.owner(actor_id, bot_id, binding_revision))

    def disable_likes(self, client, actor_id: str, bot_id: str, binding_revision: str):
        self.store.disable_likes(self.identity(client), self.owner(actor_id, bot_id, binding_revision))

    def status(self, client, actor_id: str | None = None, bot_id: str | None = None,
               binding_revision: str | None = None) -> dict:
        # No account identifier, credential, post text or backend response is exposed.
        state = self.store.state(self.identity(client))
        if actor_id is not None and state.get('owner') != self.owner(actor_id, bot_id, binding_revision):
            return {'enabled': 0, 'likes': 0, 'paused': '当前绑定尚未授权', 'last_day': ''}
        return {k: state.get(k, 0 if k=="fail_count" else "") for k in ("enabled", "likes", "paused", "last_day", "fail_count", "auto_disabled")}

    async def run(self, client, actor_id, bot_id, binding_revision, *, manual=False, signin_only=False):
        account, owner = self.identity(client), self.owner(actor_id,bot_id,binding_revision)
        day, now = self.prepare_cycle(), self.clock()
        if not self.allowed() or not self.user_allowed(actor_id):
            return {'result':'skipped','actions':0}
        if self.store.signin_status(account,owner,day)['confirmed']:
            return {'result':'skipped','actions':0}
        previous=self.store.result(account,owner,day)
        if (not manual and previous and previous['generation']==self.store.state(account).get('generation')
                and previous['status']=='retry' and now>previous['first_at']+1200):
            final=self.store.finish_run(previous,now,reason=previous['reason']+'；重试窗口已结束',category=previous['category'])
            if final:
                return dict(result='failed',actions=0,reason=final['reason'],attempts=final['attempts'],
                            streak=final['streak'],auto_stopped=bool(final['auto_stopped']),auto_enabled=bool(self.store.state(account).get('enabled')))
            return {'result':'skipped','actions':0}
        token=self.store.start_run(account,owner,day,now,manual=manual)
        if token is None:
            return {'result':'skipped','actions':0}
        try:
            result=await self._execute(client,actor_id,bot_id,binding_revision,manual=manual,signin_only=signin_only,expected_generation=token["generation"])
        except asyncio.CancelledError:
            self.store.finish_run(token,self.clock(),cancelled=True,reason='任务中断，本周期未继续执行')
            raise
        if self.binding_current is not None and not await self.binding_current(actor_id,bot_id,binding_revision):
            self.store.finish_run(token,self.clock(),cancelled=True)
            return {'result':'skipped','actions':0}
        success=bool(result.get('signin_confirmed') or self.store.signin_status(account,owner,day)['confirmed'])
        cancelled=(result['result'] in ('skipped','cycle_changed') or result.get('category')=='policy'
                   or not self.allowed() or not self.user_allowed(actor_id))
        reason=result.get('reason') or ('请求预算已用尽，签到尚未确认' if result['result']=='daily_limit' else '本轮尚未确认签到成功')
        final=self.store.finish_run(token,self.clock(),success=success,cancelled=cancelled,
                reason=reason if not success or result.get('reason') else '',
                category=result.get('category','unconfirmed'),retryable=bool(result.get('retryable') or (not success and result['result']=='completed' and self.store.signin_status(account,owner,day).get('uncertain'))))
        if final is None:
            return {'result':'skipped','actions':0}
        if final['status']=='cancelled' and cycle_day(self.clock())!=day:
            return dict(result, result='cycle_changed')
        if not success and not cancelled:
            result.update(result='retry_pending' if final['status']=='retry' else 'failed',reason=reason,
                          attempts=final['attempts'],streak=final['streak'],auto_stopped=bool(final['auto_stopped']),
                          next_at=final['next_at'],auto_enabled=bool(self.store.state(account).get('enabled')))
        return result

    def unavailable(self, actor_id, bot_id, revision, reason='本地凭据已过期、缺失或不可解析，请本人重新登录'):
        owner=self.owner(actor_id,bot_id,revision)
        day=self.prepare_cycle()
        for state in self.store.owner_accounts(owner):
            token=self.store.start_run(state['account'],owner,day,self.clock())
            if token:
                self.store.finish_run(token,self.clock(),reason=reason,category='credentials')

    async def _execute(self, client, actor_id: str, bot_id: str, binding_revision: str, *, manual=False, signin_only=False, expected_generation=None) -> dict:
        async with self._serial:
            account = self.identity(client)
            owner = self.owner(actor_id, bot_id, binding_revision)
            generation = self.store.state(account).get("generation",0)
            if generation != expected_generation:
                return {"result":"skipped","actions":0}
            lease = uuid.uuid4().hex
            day = self.prepare_cycle()
            if self.store.signin_status(account, owner, day)['confirmed']:
                return {'result':'skipped','actions':0}
            if not self.store.acquire(account, owner, lease, self.clock(), day, manual=manual):
                return {"result": "skipped", "actions": 0}
            api = CommunityAPI(client)
            completed = 0
            finished = False
            signin_confirmed = False
            counts = {'signin': 0, 'browse': 0, 'like': 0}
            switch_interval = self.uniform(self.policy.switch_min, self.policy.switch_max)
            def outcome(kind, **values):
                return dict(result=kind, actions=completed, counts=dict(counts), signin_confirmed=signin_confirmed, **values)
            try:
                if client.credentials.expired:
                    raise CommunityError("本地凭据已过期，请本人重新登录", category="credentials")

                async def request(method, path, *, body=None, params=None, action=None):
                    interval = self.uniform(self.policy.min_interval, self.policy.max_interval)
                    while True:
                        if self.store.state(account).get("generation") != generation:
                            raise CommunityError("自动任务授权已变化，本轮已取消")
                        if self.binding_current is not None and not await self.binding_current(actor_id,bot_id,binding_revision):
                            raise CommunityError('绑定已变更，社区任务已停止')
                        if not self.user_allowed(actor_id):
                            raise CommunityError("当前用户无权使用AliceUID，社区任务已暂停")
                        if not self.allowed():
                            raise CommunityError("社区模块已被全局暂停")
                        # A run crossing 08:00 Beijing stops; the next cycle is a separate invocation.
                        if cycle_day(self.clock()) != day:
                            return None
                        state, delay = self.store.reserve(
                            account, lease, owner, day, self.clock(), interval,
                            self.policy.daily_requests, action, switch_interval=switch_interval,
                        )
                        if state == "wait":
                            await self.sleep(delay)
                            continue
                        if state != "send":
                            return None
                        try:
                            data = await api.request(method, path, body=body, params=params)
                        except CommunityError as exc:
                            if exc.not_sent:
                                self.store.release_unsent(account, day, action)
                            if cycle_day(self.clock()) != day:
                                self.store.carry_boundary_guard(account,cycle_day(self.clock()),action)
                            raise
                        except (Exception, asyncio.CancelledError):
                            current_day = cycle_day(self.clock())
                            if current_day != day:
                                self.store.carry_boundary_guard(account, current_day, action)
                            raise
                        finally:
                            self.store.finish_request(account, self.clock(), switch_interval)
                        if action:
                            self.store.record(account, day, action)
                            counts[action[0]] += 1
                        current_day = cycle_day(self.clock())
                        if current_day != day:
                            self.store.carry_boundary_guard(account, current_day, action)
                            raise CycleBoundary
                        return data

                data = await request("GET", POINTS + "GetTaskListWithStatusV2", params={
                    "get_top": "false", "intl_game_id": client.region.game_id,
                })
                if data is None:
                    return outcome('daily_limit')
                tasks = parse_tasks(data)
                signin_confirmed = any(task['kind']=='signin' and task['completed'] is True for task in tasks)
                if signin_confirmed:
                    self.store.confirm_signin(account,owner,day,self.clock(),'server_confirmed')
                    # Already signed in elsewhere: no post list, browse, like
                    # or points request. Persist the same cycle's completion.
                    finished = True
                    return outcome('already_completed')
                pending = {}
                for task in tasks:
                    if task["kind"] and task["completed"] is False:
                        # Multiple tasks for a kind do not multiply interactions.
                        pending.setdefault(task["kind"], task)
                if "signin" in pending and pending["signin"]["id"]:
                    task_id = pending["signin"]["id"]
                    if await request("POST", POINTS + "DailyCheckIn", body={"task_id": task_id},
                                     action=("signin", task_id)) is not None:
                        completed += 1
                        signin_confirmed = True
                        self.store.confirm_signin(account,owner,day,self.clock(),'request_success')
                likes = self.store.state(account)["likes"]
                if not signin_only and ("browse" in pending or ("like" in pending and likes)):
                    posts = await request("POST", DYNAMICS + "GetPostList", body={
                        "search_type": 0, "plate_id": 38, "plate_unique_id": "outpost",
                        "nextPageCursor": "", "order_by": 1, "limit": "20" if likes else "10",
                    })
                    if posts is not None:
                        if not isinstance(posts.get("list"), list):
                            raise CommunityError("帖子列表格式变化，任务已暂停")
                        for post in posts["list"]:
                            if not isinstance(post, dict):
                                raise CommunityError("帖子结构变化，任务已暂停")
                            post_id = post.get("post_uuid")
                            if not isinstance(post_id, str) or not post_id:
                                continue
                            if "browse" in pending:
                                if await request("POST", DYNAMICS + "GetPost", body={"post_uuid": post_id},
                                                 action=("browse", post_id)) is not None:
                                    completed += 1
                            # Missing my_upvote does not prove a post has not been liked.
                            if "like" in pending and likes and "my_upvote" in post and post["my_upvote"] is None:
                                if await request("POST", STAR, body={"post_uuid": post_id, "type": 1, "like_type": 1},
                                                 action=("like", post_id)) is not None:
                                    completed += 1
                points = await request("GET", POINTS + "GetUserTotalPoints")
                total = points.get("total_points") if points else None
                if total is not None and (type(total) is not int or total < 0):
                    raise CommunityError("积分格式变化，任务已暂停")
                if manual and not signin_confirmed:
                    return outcome('unconfirmed', points=total)
                finished = True
                return outcome('completed', points=total,
                               unknown_tasks=sum(t['kind'] is None for t in tasks))
            except CycleBoundary:
                return outcome('cycle_changed')
            except CommunityError as exc:
                if exc.category == 'policy':
                    self.store.pause(account, str(exc), owner, generation)
                return outcome('paused', reason=str(exc),category=exc.category,retryable=exc.retryable)
            except asyncio.CancelledError:
                self.store.pause(account, "任务中断，结果未确认，请人工检查", owner, generation)
                raise
            except Exception:
                reason = "内部异常，结果未确认，请人工检查"
                self.store.pause(account, reason, owner, generation)
                return outcome('paused', reason=reason)
            finally:
                self.store.release(account, lease, day, finished=finished)
