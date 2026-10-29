"""Owner snapshots and a five-minute window committed only after a usable image."""
import asyncio
from collections import OrderedDict
import copy
from dataclasses import dataclass
import hashlib
import math
import time

from .builder import StatusDataError,build_resources


class StatusCooldown(StatusDataError):
    pass


class StatusRetryExhausted(StatusDataError):
    pass


@dataclass(frozen=True)
class ResourceCard:
    image: bytes
    reused: bool


def binding_key(bind):
    return (str(bind.game_id),str(bind.intl_open_id),int(bind.area_id),
            hashlib.sha256(bind.cookie_enc.encode()).hexdigest())


def check_client(client, bind):
    actual=(str(client.region.game_id),str(client.credentials.openid),int(client.region.area_id))
    if actual!=binding_key(bind)[:3]:raise StatusDataError('客户端与本人绑定不一致，已停止查询。')


class ResourceStatusService:
    MAX_IMAGE_BYTES=24*1024*1024

    def __init__(self, *, clock=time.monotonic,wall_clock=time.time,ttl=None,reads=None):
        self.clock,self.wall_clock,self.ttl=clock,wall_clock,ttl
        self.reads=reads
        self._cache,self._locks,self._failures={},{},{}
        self._failure_codes = {}
        self._ready=OrderedDict()
        self._work_locks,self._epochs={},{}

    def cache_ttl(self):
        if self.ttl is not None:return max(0,int(self.ttl))
        return 300

    @staticmethod
    def owner_key(bind,actor=None):
        owner=actor or (getattr(bind,'user_id',''),getattr(bind,'bot_id',''))
        return tuple(map(str,owner))+binding_key(bind)

    def invalidate(self,bind):
        revision=binding_key(bind)
        keys=set(self._cache)|set(self._ready)|set(self._locks)|set(self._work_locks)
        for key in keys:
            if key[2:]==revision:
                self._cache.pop(key,None)
                self._ready.pop(key,None)
                self._epochs[key]=self._epochs.get(key,0)+1
        # Keep the brief failure gate on the old revision; refreshing cannot
        # bypass upstream refusal. A new credential revision has its own key.
        from .draw import invalidate_status_images
        invalidate_status_images((str(getattr(bind,'user_id','')),str(getattr(bind,'bot_id','')),*revision))

    def _check_failure(self,key):
        until=self._failures.get(key,0)
        remaining=math.ceil(until-self.clock())
        if remaining>0:
            code = self._failure_codes.get(key)
            if code in (401, 300001):
                from ..nikke_api.client import NikkeLoginRequired
                raise NikkeLoginRequired(code, '登录凭据不可用')
            if code in (403, 429):
                raise StatusCooldown('社区请求暂时受限，请稍后重试。')
            raise StatusCooldown('社区查询暂未完成，可能是网络原因，请稍后重试。')
        self._failures.pop(key,None)
        self._failure_codes.pop(key,None)

    def _record_failure(self,key,exc):
        # This gate is independent from the successful-image window.
        # Only transient read failures retry; auth/refusal/rate-limit errors stop.
        from ..nikke_api.client import NikkeApiError
        delay=60 if isinstance(exc,NikkeApiError) and exc.code in (403,429) else 5
        self._failures[key]=self.clock()+delay
        self._failure_codes[key] = getattr(exc, 'code', None)

    @staticmethod
    def _style_key():
        from .draw import status_style_key
        return status_style_key()

    def _prune_ready(self):
        for key,(created,_,_) in list(self._ready.items()):
            if not 0<=self.clock()-created<self.cache_ttl():
                self._ready.pop(key,None)
        while sum(len(value[1]) for value in self._ready.values())>self.MAX_IMAGE_BYTES:
            self._ready.popitem(last=False)

    async def prepare_image(self,client,bind,*,refresh=False,actor=None,renderer=None,still_current=None,on_snapshot=None):
        """Single-flight fetch -> render -> ready. Missing images always fetch anew.

        A send failure keeps the successfully rendered image for the next send;
        neither fetching nor rendering failures start a five-minute window.
        """
        check_client(client,bind)
        key=self.owner_key(bind,actor)
        async with self._work_locks.setdefault(key,asyncio.Lock()):
            epoch=self._epochs.get(key,0)
            if still_current is not None and not await still_current():
                raise StatusDataError('绑定或查询权限已变化，已停止查询。')
            self._prune_ready()
            style=self._style_key()
            ready=self._ready.get(key)
            if ready is not None and ready[2]==style:
                self._ready.move_to_end(key)
                return ResourceCard(ready[1],True)
            self._check_failure(key)
            # A data-only snapshot is not a successfully cached image. Refresh
            # it after render failure, cache loss, expiration or invalidation.
            if ready is None:
                self._cache.pop(key,None)
            cached = self._cache.get(key) if ready is not None else None
            context = (copy.deepcopy(cached[1]) if cached is not None else
                       await self.query(client,bind,refresh=refresh,actor=actor,still_current=still_current))
            try:
                if still_current is not None and not await still_current():
                    raise StatusDataError('绑定或查询权限已变化，已停止生成图片。')
                if on_snapshot is not None:
                    await on_snapshot(copy.deepcopy(context))
                if renderer is None:
                    from .draw import draw_status
                    renderer=draw_status
                image=await renderer(context,owner_key=key)
                from ..nikke_resource.cache import validate_image
                validate_image(image)
                if self._epochs.get(key,0)!=epoch or (still_current is not None and not await still_current()):
                    raise StatusDataError('绑定或查询权限已变化，旧状态图已失效。')
            except asyncio.CancelledError:
                if ready is None:
                    self._cache.pop(key,None)
                raise
            except Exception as exc:
                if ready is None:
                    self._cache.pop(key,None)
                self._record_failure(key,exc)
                raise
            self._ready[key]=(ready[0] if ready is not None else self.clock(),image,style)
            self._ready.move_to_end(key)
            self._prune_ready()
            return ResourceCard(image,False)

    def peek(self,bind,actor=None):
        cached=self._cache.get(self.owner_key(bind,actor))
        return copy.deepcopy(cached[1]) if cached else None

    @staticmethod
    def _retryable(exc):
        import httpx
        from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
        if isinstance(exc, NikkeLoginRequired):
            return False
        if isinstance(exc, NikkeApiError):
            return exc.code == 1302127 or (type(exc.code) is int and 500 <= exc.code < 600)
        return isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError))

    async def query(self,client,bind,*,refresh=False,actor=None,fresh=False,still_current=None):
        """Data cache only. Production commands commit the window via prepare_image."""
        check_client(client,bind)
        key=self.owner_key(bind,actor)
        async with self._locks.setdefault(key,asyncio.Lock()):
            cached=self._cache.get(key)
            if not fresh and cached and 0<=self.clock()-cached[0]<self.cache_ttl():
                return copy.deepcopy(cached[1])
            self._check_failure(key)
            epoch=self._epochs.get(key,0)
            from ..nikke_roster.service import account_reads
            fetched = {}

            async def check_current():
                if self._epochs.get(key, 0) != epoch:
                    raise StatusDataError('绑定已更新，旧收菜资料已失效。')
                if still_current is not None and not await still_current():
                    raise StatusDataError('绑定或查询权限已变化，已停止查询。')

            try:
                for attempt in range(1, 4):
                    await check_current()
                    try:
                        async with (self.reads or account_reads).transaction(client,bind,wait=True) as paced:
                            for method in ('get_basic_info', 'get_outpost_info', 'get_daily_progress'):
                                if method not in fetched:
                                    await check_current()
                                    fetched[method] = await getattr(paced, method)()
                        context=build_resources(fetched['get_basic_info'],fetched['get_daily_progress'],
                                                bind=bind,region=client.region,
                                                fetched_at=self.wall_clock(),ttl=self.cache_ttl())
                        await check_current()
                        break
                    except Exception as exc:
                        if not self._retryable(exc):
                            raise
                        import logging
                        logging.getLogger(__name__).info(
                            'AliceUID resource read transient failure attempt=%d code=%s error_type=%s',
                            attempt, getattr(exc, 'code', None), type(exc).__name__)
                        if attempt == 3:
                            self._record_failure(key,exc)
                            raise StatusRetryExhausted('社区查询连续3次未成功，可能是网络原因，请稍后重试。') from None
                        # Shared account pacing delays the next attempt by at least
                        # five seconds. Successful endpoints are not requested again.
            except Exception as exc:
                self._cache.pop(key,None)
                if not isinstance(exc, StatusRetryExhausted):
                    self._record_failure(key,exc)
                raise
            self._cache[key]=(self.clock(),context)
            return copy.deepcopy(context)


resource_status=ResourceStatusService()
