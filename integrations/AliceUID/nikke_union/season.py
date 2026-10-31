"""Official public raid calendar; private requests never carry CDN credentials."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, timedelta

import httpx

from ..nikke_api.resource import obfuscate_path
from .builder import UnionDataError, integer

_lock = asyncio.Lock()
_cached = None
_loaded_at = 0.0


def normalize_seasons(rows):
    if not isinstance(rows, list) or not rows:
        raise UnionDataError('官方会战赛季表暂不可用，未猜测赛季。')
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise UnionDataError('官方会战赛季表结构变化。')
        sid = integer(row.get('id'), '赛季编号', minimum=1)
        start = integer(row.get('start_ts'), '赛季开始时间')
        end = integer(row.get('end_ts'), '赛季结束时间')
        calculate = integer(row.get('caculate_ts'), '结算时间')
        if sid in seen or not start <= end <= calculate:
            raise UnionDataError('官方会战赛季时间或编号异常。')
        seen.add(sid)
        result.append(dict(id=sid, start_ts=start, end_ts=end, caculate_ts=calculate))
    return sorted(result, key=lambda item: (item['start_ts'], item['id']))


async def load_seasons():
    global _cached, _loaded_at
    async with _lock:
        now = time.monotonic()
        if _cached is not None and 0 <= now - _loaded_at < 60:
            return _cached
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as http:
                response = await http.get(obfuscate_path('/raid/raid_list.json'))
                response.raise_for_status()
                rows = normalize_seasons(response.json())
        except Exception:
            raise UnionDataError('官方会战赛季表读取失败，请稍后重试；未猜测当期赛季。') from None
        _cached, _loaded_at = rows, now
        return rows


def select_season(rows, now):
    started = [row for row in normalize_seasons(rows) if row['start_ts'] <= now]
    if not started:
        raise UnionDataError('官方赛季表尚无已开始的会战记录。')
    row = dict(started[-1])
    row['active'] = row['start_ts'] <= now <= row['end_ts']
    # The website continues using live endpoints through settlement + one day.
    row['live_endpoint'] = now <= row['caculate_ts'] + 86400
    return row


def season_context(season, *, local=False):
    from ..nikke_time import beijing_text
    label = 'S' + str(season['id'] - 1000000) if season['id'] >= 1000000 else str(season['id'])
    fmt = lambda ts: beijing_text(ts, seconds=False, label=False)
    return dict(season_id=str(season['id']), season_label=label,
                season_dates=f"{fmt(season['start_ts'])} ～ {fmt(season['end_ts'])}（北京时间）",
                raid_active=season['active'],
                raid_status='正在进行' if season['active'] else '当前不是会战期间，展示上一期数据',
                history_local=local,
                source=('本联盟历史快照' if local else '社区当期记录' if season['active'] else '社区上一期记录') + ' · ' + label)
