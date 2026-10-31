"""Owned, serialized redemption. Durable receipts precede user feedback."""
from __future__ import annotations

import asyncio
import random
import time

from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from . import api
from .models import PRODUCT, identity, code_text, clean, retirement_at, code_key, code_lookup

ERRORS = {
    1302002: '兑换参数异常', 1302003: '兑换码无效', 1302004: '游戏产品不匹配',
    1302005: '账号标识异常', 1302006: '角色标识异常', 1302007: '平台或系统参数异常',
    1302008: '无兑换权限', 1302009: '不在有效时间内，已暂停此码自动兑换',
    1302010: '当前区服不适用', 1302011: '当前国家或地区不适用', 1302012: '当前平台不适用',
    1302013: '官方服务异常，结果未确认', 1302014: '兑换码已被使用', 1302015: '兑换码不存在',
    1302016: '本账号已领取', 1302017: '账号兑换次数达到上限', 1302018: '请求过频，已停止本轮',
    1302019: '官方网络异常，结果未确认', 1302020: '多次错误限制，已停止本轮',
    1302021: '无法取得角色信息', 401: '登录失效，请重新登录',
    300001: '登录失效，请重新登录', 403: '官方拒绝请求，已停止本轮', 429: '官方限流，已停止本轮',
}
STOP = {1302004, 1302005, 1302006, 1302007, 1302008, 1302017, 1302018, 1302020,
        1302021, 401, 300001, 403, 429}
UNCERTAIN = {-1, 1302013, 1302019}


class OwnedError(ValueError):
    pass


class Redemptions:
    def __init__(self, store, clock=time.time, submit=api.redeem, read_history=api.history,
                 sleep=asyncio.sleep, interval=lambda: random.uniform(3, 5)):
        self.store, self.clock = store, clock
        self.submit, self.read_history, self.sleep, self.interval = submit, read_history, sleep, interval

    async def role_matches(self, client, bind):
        if (str(bind.game_id) != PRODUCT or str(client.credentials.openid) != str(bind.intl_open_id)
                or int(client.region.area_id) != int(bind.area_id) or str(client.region.game_id) != str(bind.game_id)
                or not str(bind.uid or '')):
            raise OwnedError('本人绑定或区服不一致，请重新核对登录账号')
        role = await client.get_saved_role_info()
        if (str(role.get('game_id')) != str(bind.game_id)
                or str(role.get('area_id')) != str(bind.area_id)
                or str(role.get('role_id')) != str(bind.uid)):
            raise OwnedError('官网当前保存角色与绑定不一致，本次未兑换；请先在官网确认角色')

    async def confirm(self, client, account, code):
        try:
            rows = await self.read_history(client)
            if any(isinstance(r, dict) and isinstance(r.get('cdk'), str) and r['cdk'].casefold() == code_key(code)
                   and (r.get('status') is True or (type(r.get('status')) is int and r['status'] == 1)) for r in rows):
                self.store.record(account, code, 'claimed', '官方记录确认本账号已领取', self.clock())
                return True
        except Exception:
            pass
        return False

    async def run(self, client, bind, items, *, current, enabled, contribute=False):
        account = identity(bind)
        lease_key = 'account:' + account
        token = self.store.acquire(lease_key, self.clock())
        if not token:
            return [dict(code='', status='stopped', result='本账号已有兑换任务，本次未重复提交')]
        results = []
        seen, sent = set(), False
        def source_expired(item):
            detail = self.store.detail(PRODUCT, item['code']) or {}
            window = {**item, **{k: v for k, v in detail.items() if v is not None}}
            end = retirement_at(window)
            now = self.clock()
            return ((end is not None and now >= end)
                    or (window.get('valid_from') and now < window['valid_from']))
        try:
            for item in items:
                code = code_text(item['code'])
                key = code_key(code)
                if key in seen:
                    continue
                seen.add(key)
                if not await current() or not enabled():
                    results.append(dict(code=code, status='stopped', result='绑定、权限或兑换开关已变化，剩余项未尝试'))
                    break
                blocked = code_lookup(self.store.blocked(PRODUCT), code)
                if blocked:
                    results.append(dict(code=code, status='skipped', result=blocked['reason']))
                    continue
                if source_expired(item):
                    results.append(dict(code=code, status='skipped', result='不在已知有效期内或已过5分钟宽限，本次未兑换'))
                    continue
                receipt = self.store.receipt(account, code)
                if receipt and receipt['state'] in ('success', 'claimed'):
                    row = dict(code=code, status='claimed', result='本账号已领取，本次未重复提交')
                    if contribute:
                        pool_status = self.store.contribute_recent(account, PRODUCT, code, self.clock())
                        if pool_status is not None:
                            row.update(pool_status=pool_status, result='本人48小时内官方明确记录已核验，本次未重复提交',
                                       pool_basis='claimed' if receipt['state'] == 'claimed' else 'success')
                    results.append(row)
                    continue
                if receipt and receipt['state'] in ('submitting', 'uncertain'):
                    confirmed = await self.confirm(client, account, code)
                    results.append(dict(code=code, status='claimed' if confirmed else 'uncertain',
                        result='官方记录确认本账号已领取' if confirmed else '上次提交结果未确认，本次未重复提交'))
                    if not confirmed:
                        break
                    continue
                if sent:
                    await self.sleep(max(0, float(self.interval())))
                if not self.store.renew(lease_key, token, self.clock()):
                    raise OwnedError('账号任务锁已变化，剩余项未尝试')
                # Default role belongs to the official account, not the request body.
                await self.role_matches(client, bind)
                if not await current() or not enabled():
                    raise OwnedError('绑定、权限或兑换开关已变化，剩余项未尝试')
                if code_lookup(self.store.blocked(PRODUCT), code):
                    results.append(dict(code=code, status='skipped', result='共享状态已停用此码，未提交'))
                    continue
                if source_expired(item):
                    results.append(dict(code=code, status='skipped', result='不在已知有效期内或已过5分钟宽限，本次未兑换'))
                    continue
                if not self.store.claim(account, code, token, self.clock()):
                    raise OwnedError('本地提交状态变化，已停止防止重复请求')
                sent = True
                try:
                    await self.submit(client, code)
                except NikkeApiError as exc:
                    status = 'failed'
                    result = ERRORS.get(exc.code, '官方返回未知结果，已停止本轮') + f'（{exc.code}）'
                    uncertain = (getattr(exc, 'network_uncertain', False) or api.network_message(exc.msg) or exc.code in UNCERTAIN
                                 or 500 <= exc.code < 600 or exc.code not in ERRORS)
                    if uncertain:
                        status = 'uncertain'
                        result = '官方或网络结果未确认，未停用此码' + f'（{exc.code}）'
                    elif exc.code == 1302016:
                        status = 'claimed'
                    elif exc.code == 1302009:
                        expired = getattr(exc, 'confirmed_expired', False)
                        result = '官方确认兑换码已过期' if expired else result
                        self.store.block(PRODUCT, code, 'expired' if expired else 'out_of_window', result, self.clock())
                    elif exc.code in (1302003, 1302015):
                        self.store.block(PRODUCT, code, 'invalid', result, self.clock())
                    pool_status = None
                    if status == 'claimed':
                        pool_status = self.store.complete_claimed(account, PRODUCT, code, self.clock(), contribute=contribute)
                    else:
                        self.store.record(account, code, status, result, self.clock())
                    if uncertain and await self.confirm(client, account, code):
                        status, result = 'claimed', '官方记录确认本账号已领取'
                    row = dict(code=code, status=status, result=result)
                    if pool_status is not None:
                        row.update(pool_status=pool_status, pool_basis='claimed')
                    results.append(row)
                    if exc.code in STOP or uncertain:
                        break
                except Exception:
                    # Receipt remains uncertain even for an unexpected adapter exception.
                    self.store.record(account, code, 'uncertain', '提交结果未确认，未重试', self.clock())
                    results.append(dict(code=code, status='uncertain', result='提交结果未确认，未重试'))
                    break
                else:
                    pool_status = self.store.complete_success(account, PRODUCT, code, self.clock(), contribute=contribute)
                    row = dict(code=code, status='success', result='兑换成功', reward=clean(item.get('reward', '')))
                    if contribute:
                        row['pool_status'] = pool_status
                    results.append(row)
        except (OwnedError, NikkeApiError) as exc:
            reason = str(exc) if isinstance(exc, OwnedError) else ERRORS.get(exc.code, '角色核验请求失败')
            results.append(dict(code='', status='stopped', result=reason))
        finally:
            self.store.release(lease_key, token)
        processed = {code_key(r['code']) for r in results if r.get('code')}
        remaining = len({code_key(i['code']) for i in items} - processed)
        if remaining:
            results.append(dict(code='', status='remaining', result=f'其余{remaining}个码未尝试'))
        return results
