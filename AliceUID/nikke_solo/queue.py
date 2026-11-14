"""FIFO admission for complete browser jobs; waiting never spends retry time."""
import asyncio
import time
from contextlib import asynccontextmanager
from .errors import SoloUnavailable
from ..nikke_logs.store import event


class BrowserQueue:
    def __init__(self, limit=20):
        self.limit = limit
        self.tickets = []

    @asynccontextmanager
    async def turn(self, notify):
        if len(self.tickets) >= self.limit + 1:
            raise SoloUnavailable('单人突袭推荐等待队列已满，请稍后再试。')
        ticket = asyncio.get_running_loop().create_future()
        ahead = len(self.tickets)
        self.tickets.append(ticket)
        started = time.monotonic()
        if ahead == 0:
            ticket.set_result(None)
        try:
            await notify(ahead)
            event('个人突袭', '排队', 'ENQUEUED', count=ahead)
            await asyncio.shield(ticket)
            event('个人突袭', '执行', 'STARTED', queue_wait_ms=int((time.monotonic()-started)*1000))
            yield
        finally:
            head = self.tickets and self.tickets[0] is ticket
            if ticket in self.tickets:
                self.tickets.remove(ticket)
            if head and self.tickets and not self.tickets[0].done():
                self.tickets[0].set_result(None)


browser_queue = BrowserQueue()
