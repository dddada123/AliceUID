"""Season-aware durable three-part guide cache, shared across groups."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time

from ..nikke_calendar.service import _atomic_write
from ..nikke_union.season import load_seasons, select_season
from .source import (AUTHOR, TTL, GuideUnavailable, find_post, example_image,
                     download_image, capture_post, validate_image, matches)

_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class Guide:
    title: str
    team: bytes
    screenshot: bytes


class GuideService:
    def __init__(self, root, *, seasons=load_seasons, finder=find_post,
                 download=download_image, capture=None, clock=time.time,
                 channel='auto', quality=95):
        self.root = Path(root)
        self.seasons, self.finder, self.download = seasons, finder, download
        self.capture, self.clock = capture, clock
        self.channel, self.quality = channel, quality

    def read_meta(self):
        try:
            meta = json.loads((self.root/'guide.json').read_text('utf-8'))
            if not isinstance(meta, dict) or meta.get('author') != AUTHOR:
                return {}
            for field in ('saved_at', 'retry_after'):
                value = meta.get(field, 0)
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    return {}
            return meta
        except (OSError, ValueError, TypeError):
            return {}

    def save_meta(self, meta):
        _atomic_write(self.root/'guide.json', json.dumps(meta, ensure_ascii=False).encode())

    def cached(self, meta):
        try:
            post = meta['post']
            if not matches(post, meta['season'], self.clock()):
                return None
            team, screenshot = (self.root/'team.image').read_bytes(), (self.root/'post.jpg').read_bytes()
            if [hashlib.sha256(b).hexdigest() for b in (team, screenshot)] != meta['hashes']:
                return None
            validate_image(team)
            validate_image(screenshot, screenshot=True)
            return Guide(post['title'], team, screenshot)
        except (OSError, KeyError, ValueError, TypeError, GuideUnavailable):
            return None

    async def get(self):
        async with _LOCK:
            now = self.clock()
            try:
                season = select_season(await self.seasons(), now)
            except Exception:
                raise GuideUnavailable('官方会战日程暂不可用，无法确认本期攻略，请稍后重试。') from None
            sid = str(season['id'])
            meta = self.read_meta()
            if meta.get('season_id') != sid:
                # Persist the new identity first: a failed fetch/restart cannot reuse old guides.
                self.save_meta(dict(author=AUTHOR, season_id=sid, retry_after=0, saved_at=0))
                for name in ('team.image', 'post.jpg'):
                    (self.root/name).unlink(missing_ok=True)
                meta = self.read_meta()
            cached = self.cached(meta)
            age = now - meta.get('saved_at', 0)
            if cached and 0 <= age and (not season['combat_active'] or age < TTL):
                return cached
            if now < meta.get('retry_after', 0):
                raise GuideUnavailable('本期攻略暂未就绪，查询冷却5分钟后可重试。')
            meta.update(author=AUTHOR, season_id=sid, retry_after=now+300)
            self.save_meta(meta)
            try:
                async def fetch():
                    post = await self.finder(season, now)
                    if not matches(post, season, now):
                        raise GuideUnavailable('未找到作者的本期攻略。')
                    team = await self.download(example_image(post.get('content', '')))
                    shot = await (self.capture(post) if self.capture else capture_post(
                        post, channel=self.channel, quality=self.quality))
                    validate_image(team)
                    validate_image(shot, screenshot=True)
                    return post, team, shot
                post, team, shot = await asyncio.wait_for(fetch(), timeout=180)
                # A request spanning a season boundary must not publish the previous raid.
                current = select_season(await self.seasons(), self.clock())
                if str(current['id']) != sid:
                    raise GuideUnavailable('会战已切换至新一期，请重新查询攻略。')
                _atomic_write(self.root/'team.image', team)
                _atomic_write(self.root/'post.jpg', shot)
                # Only keep public identity/title/timestamp, never a user profile or account data.
                public_post = {k:post[k] for k in ('title','post_uuid','created_on','intl_openid')}
                public_post['user'] = {'intl_openid': AUTHOR}
                self.save_meta(dict(author=AUTHOR, season_id=sid, season=season, post=public_post,
                    saved_at=self.clock(), retry_after=0,
                    hashes=[hashlib.sha256(b).hexdigest() for b in (team, shot)]))
                return Guide(post['title'], team, shot)
            except asyncio.CancelledError:
                raise
            except GuideUnavailable:
                raise
            except Exception:
                raise GuideUnavailable('攻略读取或完整截图暂不可用，请5分钟后重试。') from None


def get_guide():
    from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
    return GuideService(MAIN_PATH/'cache'/'raid_guide',
        channel=AliceUIDConfig.get_config('AliceUID_BrowserChannel').data or 'auto',
        quality=AliceUIDConfig.get_config('AliceUID_ForwardJpegQuality').data)
