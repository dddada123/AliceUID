"""Reviewed official Shiftyspad fields; unknown values never become zero."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import math


class StatusDataError(ValueError):
    pass


CURRENCIES = (
    ('钻石',(98,99)), ('信用点',(2000,)), ('黄金积分券',(12000,)),
    ('白银积分券',(11000,)), ('战斗数据辑',(1000,)), ('芯尘',(3000,)),
    ('招募券',(5100,)), ('高级招募券',(5200,)),
)
HIDDEN = {-1,-99,-9999}


def integer(value, field):
    if isinstance(value,bool) or not isinstance(value,(str,int)):
        raise StatusDataError(f'{field}格式异常，未用零替代。')
    if isinstance(value,str) and (len(value)>40 or not value.isascii() or not (value[1:] if value.startswith('-') else value).isdigit()):
        raise StatusDataError(f'{field}格式异常，未用零替代。')
    result=int(value)
    if result<0 and result not in HIDDEN:
        raise StatusDataError(f'{field}数值超出范围。')
    return result


def timestamp(value):
    return datetime.fromtimestamp(value,timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S UTC+8')


def identity(bind, region, fetched_at, ttl):
    return dict(commander_name=bind.nickname or '昵称未知', commander_uid=bind.uid or '未知',
                commander_region=region.label, fetched_at=timestamp(fetched_at),cache_seconds=ttl,
                source='blablalink · 繁体中文接口快照')


def compact_number(value):
    if value>=1000000:
        return f'{Decimal(value)/1000000:.2f}M'
    return f'{value:,}'


def storage_estimates(storage, fetched_at):
    """Linear 24-hour estimate from this snapshot, using Beijing calendar days."""
    if storage is None:
        return dict(storage_color='',storage_90_text='容量未知，无法预计到90%的时间',
                    storage_full_text='容量未知，无法预计回满时间')
    now=datetime.fromtimestamp(fetched_at,timezone(timedelta(hours=8)))
    def estimate(target,label):
        if storage>=target:
            return '已达到90%' if target==90 else '已满 MAX'
        seconds=math.ceil(float((Decimal(target)-storage)*Decimal(864)))
        moment=now+timedelta(seconds=seconds)
        day='今天' if moment.date()==now.date() else '明天'
        return f'预计{day}{moment:%H:%M}{label}'
    return dict(storage_color='#d84b50' if storage>90 else '#e39327' if storage>70 else '',
                storage_90_text=estimate(90,'达到90%'),storage_full_text=estimate(100,'回满'))


def build_resources(basic, daily, *, bind, region, fetched_at, ttl):
    if not isinstance(basic,dict) or not isinstance(basic.get('currencies'),list):
        raise StatusDataError('社区未返回资源明细，请检查游戏资料权限或稍后重试。')
    rows={}
    for row in basic['currencies']:
        if not isinstance(row,dict):raise StatusDataError('资源明细结构变化。')
        kind=integer(row.get('type'),'资源类型')
        if kind in rows:raise StatusDataError('资源类型重复，无法可靠合计。')
        rows[kind]=integer(row.get('value'),'资源数量')
    items=[]
    for index,(name,kinds) in enumerate(CURRENCIES,1):
        values=[rows.get(kind) for kind in kinds]
        known=all(value is not None and value>=0 for value in values)
        value=sum(values) if known else None
        items.append(dict(name=name,value=compact_number(value) if known else '—',
                          exact=f'{value:,}' if known else '未提供或已隐藏',known=known,
                          icon_name=f'icon-res-pic{index}.png'))
    if not isinstance(daily,dict) or not isinstance(daily.get('daily_progress'),list):
        raise StatusDataError('社区未返回日常进度，无法核对保管箱容量。')
    progress=daily['daily_progress']
    if progress and not isinstance(progress[0],dict):raise StatusDataError('日常进度结构变化。')
    fullness=(progress[0] if progress else {}).get('outpost_battle_storage_fullness')
    storage=None
    if fullness is not None:
        if isinstance(fullness,bool):raise StatusDataError('保管箱容量格式异常。')
        try:
            decimal=Decimal(str(fullness))
        except InvalidOperation:
            raise StatusDataError('保管箱容量格式异常。') from None
        if not decimal.is_finite():raise StatusDataError('保管箱容量格式异常。')
        if decimal not in HIDDEN:
            if not 0<=decimal<=1:raise StatusDataError('保管箱容量比例超出范围。')
            storage=decimal*100
    return dict(identity(bind,region,fetched_at,ttl),kind='resources',title='我的资源',items=items,
                storage_text='MAX' if storage==100 else f'{storage:.1f}%' if storage is not None else '未知',
                storage_width=format(storage,'f') if storage is not None else '0',
                storage_known=storage is not None,
                **storage_estimates(storage,fetched_at),
                notes=['钻石合计付费与免费钻石；缺失或隐藏的资源显示「—」。',
                       '保管箱按24小时回满线性估算，北京时间；实际收取、游戏加成或社区同步延迟会影响结果。'])


def hp_percentage(current, maximum):
    hundredths=current*10000//maximum
    return f'{hundredths//100}.{hundredths%100:02d}'


def build_bosses(payload, *, bind, region, fetched_at, ttl, guild_name='当前联盟'):
    if not isinstance(payload,dict) or not isinstance(payload.get('level_info'),list):
        raise StatusDataError('联盟进度接口结构变化，无法确认当前阶段。')
    levels=payload['level_info']
    base=dict(identity(bind,region,fetched_at,ttl),kind='bosses',title='会战血量',guild_name=guild_name,
              bosses=[],available=bool(levels),notes=['数据来自当前联盟进度接口；非实时推送，以查询时间为准。'])
    if not levels:
        return dict(base,phase='暂无当前会战进度',progress_text='未知',
                    notes=['社区未返回当前BOSS阶段。可能尚未开放或本期已结束；未以旧赛季或构造数据替代。'])
    # The official homepage uses level_info.at(0), not the largest level.
    level=levels[0]
    if not isinstance(level,dict) or not isinstance(level.get('boss_info'),list):
        raise StatusDataError('BOSS进度结构变化。')
    difficulty=integer(level.get('difficulty'),'会战难度')
    phase=integer(level.get('level'),'会战等级')
    if difficulty not in (1,2) or phase<1:raise StatusDataError('未知会战难度或阶段，停止推断。')
    bosses=[]
    seen=set()
    for row in level['boss_info']:
        if not isinstance(row,dict):raise StatusDataError('BOSS血量格式异常。')
        boss_id=str(row.get('boss_id') or '')
        if not boss_id or boss_id in seen:raise StatusDataError('BOSS标识缺失或重复。')
        seen.add(boss_id)
        maximum=integer(row.get('max_hp'),'BOSS最大血量')
        current=integer(row.get('current_hp'),'BOSS当前血量')
        if min(maximum,current)<0 or maximum and current>maximum:
            raise StatusDataError('BOSS血量超出范围，未截断或用零替代。')
        local=row.get('name_localvalues')
        if not isinstance(local,dict):raise StatusDataError('BOSS名称字段变化。')
        name=local.get('zh-tw') or local.get('zh-TW') or local.get('en')
        if not isinstance(name,str) or not name.strip():raise StatusDataError('BOSS名称缺失。')
        infinite=maximum==0
        percent=hp_percentage(current,maximum) if maximum else None
        bosses.append(dict(name=name,boss_id=boss_id,current=f'{current:,}',maximum=f'{maximum:,}',
                           current_raw=current,maximum_raw=maximum,percent=percent,
                           infinite=infinite,hp_text=f'{current:,} / ∞' if infinite else f'{current:,} / {maximum:,}'))
    finite=bool(bosses) and all(not b['infinite'] for b in bosses)
    progress=(hp_percentage(sum(b['maximum_raw']-b['current_raw'] for b in bosses),
                            sum(b['maximum_raw'] for b in bosses))+'%') if finite else '不适用'
    return dict(base,phase=f'{"困难" if difficulty==2 else "普通"} · 第{phase}阶段',
                bosses=bosses,progress_text=progress,
                notes=base['notes']+(['当前为无限血量阶段，不展示虚构百分比。'] if not finite and bosses else []))
