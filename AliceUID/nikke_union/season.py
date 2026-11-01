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
    # The official range includes review/settlement. Only the first two days
    # allow attacks; this does not select the live vs historical API.
    row['combat_end_ts'] = min(row['start_ts'] + 48 * 3600, row['end_ts'] + 1)
    row['combat_active'] = row['start_ts'] <= now < row['combat_end_ts']
    row['combat_phase'] = ('day1' if now < row['start_ts'] + 24 * 3600 else 'day2') if row['combat_active'] else (
        'settlement' if now <= row['end_ts'] else 'offseason')
    # The website continues using live endpoints through settlement + one day.
    row['live_endpoint'] = now <= row['caculate_ts'] + 86400
    return row


def season_context(season, *, local=False):
    from ..nikke_time import beijing_text
    label = 'S' + str(season['id'] - 1000000) if season['id'] >= 1000000 else str(season['id'])
    fmt = lambda ts: beijing_text(ts, seconds=False, label=False)
    phase = season.get('combat_phase', 'day1' if season['active'] else 'offseason')
    combat_end = season.get('combat_end_ts', min(season['start_ts'] + 48 * 3600, season['end_ts'] + 1))
    combat_active = phase in ('day1', 'day2')
    status = ('正在进行 · '+('Day1' if phase == 'day1' else 'Day2')) if combat_active else (
        '出刀已结束，排名结算中 · 展示本期记录' if phase == 'settlement' else '当前不是会战期间，展示上一期数据')
    return dict(season_id=str(season['id']), season_label=label,
                season_dates=f"出刀期：{fmt(season['start_ts'])} ～ {fmt(combat_end)}（北京时间）",
                official_season_dates=f"官方赛季区间：{fmt(season['start_ts'])} ～ {fmt(season['end_ts'])}（北京时间，含结算期）",
                raid_phase=phase, raid_active=combat_active,
                raid_cache_seconds=(max(0, season['end_ts'] + 1 - combat_end) if phase == 'settlement'
                                    else 5 * 86400 if phase == 'offseason' else None),
                raid_status=status,
                history_local=local,
                source=('本联盟历史快照' if local else '社区当期记录' if season['active'] else '社区上一期记录') + ' · ' + label)
