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
            raise StatusCooldown(f'上次请求未完成，请{remaining}秒后重试；尚未进入5分钟图片缓存窗口。')
        self._failures.pop(key,None)

    def _record_failure(self,key,exc):
        # Separate from the successful-image window. Never automatically retry
        # authentication/refusal/rate-limit errors; manual retries stay paced.
        from ..nikke_api.client import NikkeApiError
        delay=60 if isinstance(exc,NikkeApiError) and exc.code in (403,429) else 5
        self._failures[key]=self.clock()+delay

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
                       await self.query(client,bind,refresh=refresh,actor=actor))
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

    async def query(self,client,bind,*,refresh=False,actor=None,fresh=False):
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
            try:
                async with (self.reads or account_reads).transaction(client,bind,wait=True) as paced:
                    basic=await paced.get_basic_info()
                    await paced.get_outpost_info()
                    try:
                        daily=await paced.get_daily_progress()
                    except Exception as exc:
                        from ..nikke_api.client import NikkeApiError
                        if not isinstance(exc,NikkeApiError) or exc.code!=1302127:
                            raise
                        # One bounded read-only recheck after five-second pacing.
                        daily=await paced.get_daily_progress()
                context=build_resources(basic,daily,bind=bind,region=client.region,
                                        fetched_at=self.wall_clock(),ttl=self.cache_ttl())
                if self._epochs.get(key,0)!=epoch:
                    raise StatusDataError('绑定已更新，旧收菜资料已失效。')
            except Exception as exc:
                self._cache.pop(key,None)
                self._record_failure(key,exc)
                from ..nikke_api.client import NikkeApiError
                if isinstance(exc,NikkeApiError) and exc.code==1302127:
                    raise StatusDataError('社区暂未返回有效收菜资料（1302127），本次未生成图片；请5秒后重试，尚未进入5分钟图片缓存窗口。') from None
                raise
            self._cache[key]=(self.clock(),context)
            return copy.deepcopy(context)


resource_status=ResourceStatusService()
