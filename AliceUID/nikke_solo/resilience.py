"""Three quiet attempts per request, with bounded idle waits and message deduplication."""
import asyncio
import time
from collections import OrderedDict
from contextvars import ContextVar
import httpx
from .errors import SoloTransient, RetryAborted

ATTEMPTS = 3
IDLE_SECONDS = 20
_HEARTBEAT = ContextVar('solo_retry_heartbeat',default=None)


def network_progress():
    heartbeat = _HEARTBEAT.get()
    if heartbeat is not None:
        heartbeat[0] = time.monotonic()


def transient(exc):
    if isinstance(exc, (SoloTransient, asyncio.TimeoutError, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 408 or 500 <= exc.response.status_code < 600
    return False


class RetryBudget:
    """Failures share a single three-round budget across preflight and capture."""
    def __init__(self, *, attempts=ATTEMPTS):
        self.attempts = attempts
        self.failures = 0

    async def run(self, operation, *, valid=None, timeout=None):
        while True:
            if valid is not None and not await valid():
                raise RetryAborted()
            token = None
            try:
                if timeout is not None:
                    heartbeat = [time.monotonic(),'赛季预检']
                    token = _HEARTBEAT.set(heartbeat)
                    return await run_with_idle_timeout(operation(),heartbeat,timeout=timeout)
                return await operation()
            except Exception as exc:
                if not transient(exc):
                    raise
                self.failures += 1
                from ..nikke_logs.store import record_failure
                record_failure('个人突袭',f'静默尝试{self.failures}',exc)
                if self.failures >= self.attempts:
                    error = SoloTransient(f'网络连续无响应，{self.attempts}轮尝试均未完成，本次请求已停止。',
                                          stage=getattr(exc, 'stage', '') or ('赛季预检' if timeout is not None else ''), reason='RETRY_EXHAUSTED')
                    raise error from None
                # The failed await has terminated, including browser cleanup.
                # No chat sends, detached jobs, or delayed recursive command calls.
                await asyncio.sleep(0)
            finally:
                if token is not None:
                    _HEARTBEAT.reset(token)


async def run_with_idle_timeout(operation, heartbeat, *, timeout=IDLE_SECONDS):
    task = asyncio.create_task(operation)
    try:
        while True:
            remaining = timeout - (time.monotonic() - heartbeat[0])
            if remaining <= 0:
                raise SoloTransient('网站连续20秒无响应。', stage=heartbeat[1], reason='IDLE_TIMEOUT')
            done, _ = await asyncio.wait({task}, timeout=remaining)
            if task in done:
                return task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


class RequestGate:
    """Per-user in-flight work and exact event IDs; never a group-wide cooldown."""
    def __init__(self, *, clock=time.monotonic, ttl=1200, limit=4096):
        self.clock, self.ttl, self.limit = clock, ttl, limit
        self.active = set()
        self.seen = OrderedDict()

    def enter(self, event):
        now = self.clock()
        while self.seen and next(iter(self.seen.values())) <= now:
            self.seen.popitem(last=False)
        platform = str(event.bot_id)
        bot = str(getattr(event, 'bot_self_id', '') or '')
        user = str(event.user_id)
        actor = (user, platform, bot)
        if actor in self.active or (bot and user == bot):
            return None
        message = str(getattr(event, 'msg_id', '') or getattr(event, 'message_id', '') or '')
        if message:
            key = (platform, bot, user, str(getattr(event, 'group_id', '') or ''), message)
            if key in self.seen:
                return None
            self.seen[key] = now + self.ttl
            while len(self.seen) > self.limit:
                self.seen.popitem(last=False)
        self.active.add(actor)
        return actor

    def leave(self, actor):
        self.active.discard(actor)
