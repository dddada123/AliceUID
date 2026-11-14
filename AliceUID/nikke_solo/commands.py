"""Experimental command: actor-only binding, bounded work, guarded delivery."""
import asyncio
import time
from dataclasses import replace
from gsuid_core.sv import SV
from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from ..nikke_commands import command_prefix
from ..nikke_permissions.runtime import get_policy
from ..nikke_user.models import AliceBind
from ..nikke_user.service import load_client, binding_lock
from ..nikke_user.auth_state import unavailable_message, RELOGIN, is_login_error, expired, known_invalid, mark_invalid
from ..nikke_api.client import NikkeApiError, NikkeLoginRequired
from ..nikke_status.service import binding_key
from ..nikke_logs.store import record_failure
from .service import NOTICE, SoloUnavailable, owned_account, capture
from .draw import draw_solo, get_solo_theme_mode
from ..nikke_render.theme import get_card_theme
from ..nikke_api.client import REGIONS, HMT_REGION
from .cache import get_cache, identity, style_key
from .selection import parse_selection
from .site import get_monitor, revision
from .service import SERVERS
from .errors import SoloTransient, RetryAborted
from .resilience import RetryBudget, RequestGate, IDLE_SECONDS
from datetime import datetime
from zoneinfo import ZoneInfo

sv_solo = SV('妮姬个人突袭推荐（实验性）',pm=6,priority=3)
_requests = RequestGate()
_active = _requests.active

async def allowed(ev):
    policy = get_policy()
    return policy.user_allowed(ev.user_id) and await policy.query_allowed(getattr(ev,'group_id',None))

def authenticated(bind):
    return bool(bind.cookie_enc) and not expired(bind) and not known_invalid(bind)

async def current(ev, bind):
    latest = await AliceBind.get_bind(ev.user_id,ev.bot_id)
    return latest is not None and binding_key(latest)==binding_key(bind) and await allowed(ev)

async def _solo_command(bot,ev):
    if not await allowed(ev):
        return
    try:
        selection = parse_selection(ev.text)
    except ValueError:
        await bot.send(f'用法：{command_prefix()}个人突袭推荐[火/水/风/电/铁][刷新] [亮色/暗色/随机]；支持燃烧/水冷/风压/电击/铁甲及单人突袭推荐。不填属性自动跟随网站赛季，练度变化请刷新。',at_sender=True)
        return
    refresh = selection.refresh
    refresh_command = f'{command_prefix()}个人突袭推荐{selection.suffix}刷新'
    theme = get_card_theme(selection.theme or get_solo_theme_mode())
    actor = (str(ev.user_id),str(ev.bot_id))
    retries = RetryBudget()
    client = bind = reply = fallback = None
    cache_warning = ''
    async def retry_allowed():
        return bind is not None and authenticated(bind) and await current(ev,bind)
    try:
        bind = await AliceBind.get_bind(*actor)
        if bind is None:
            reply = unavailable_message(bind)
        elif not authenticated(bind):
            reply = unavailable_message(bind)
        else:
            cache = get_cache()
            key = identity(bind,actor,selection.mode)
            try:
                cache.cleanup()
            except (OSError, ValueError) as exc:
                logger.warning(f'[AliceUID] solo cache cleanup error_type={type(exc).__name__}')
            latest = None
            if selection.mode == 'default':
                # Fetch the public season before even reading the personal result cache.
                try:
                    latest = await retries.run(lambda:get_monitor().inspect(selection.mode, SERVERS[int(bind.area_id)][0]),
                                               valid=retry_allowed, timeout=IDLE_SECONDS)
                except (SoloTransient,RetryAborted):
                    raise
                except Exception as exc:
                    record_failure('个人突袭', '赛季预检', exc)
                    # Do not label old results as current when the latest season is unknown.
                    raise SoloUnavailable('本次赛季检查未完成，未使用旧缓存。' + str(exc) if isinstance(exc, ValueError)
                                          else '本次赛季检查失败，请稍后重试；尚未确认是否已有本期排行。') from None
            image = None if refresh else cache.read(key)
            if image is not None:
                try:
                    if latest is None:
                        latest = await retries.run(lambda:get_monitor().inspect(selection.mode, SERVERS[int(bind.area_id)][0]),
                                                   valid=retry_allowed, timeout=IDLE_SECONDS)
                    if not image.site or revision(latest) != revision(image.site) or (latest.get('active') is not False and time.time()-image.captured_at >= 21600):
                        fallback, image = image, None
                except RetryAborted:
                    raise
                except Exception as exc:
                    record_failure('个人突袭', '网站更新检查', exc)
                    cache_warning = '本次网站更新检查失败，以下为此前生成的缓存结果；赛季与阵容可能已有变化。\n'
            region = REGIONS.get(int(bind.area_id)) or (HMT_REGION if int(bind.area_id)==91 else None)
            if image is not None and region is not None:
                from .identity import prepare_identity
                decoration = await prepare_identity(bind=bind)
                if decoration:
                    image = replace(image, presentation=decoration)
                style = style_key(image,bind,theme)
                png = cache.card(key,image,style)
                if png is None:
                    png = await draw_solo(image,bind,region,theme=theme)
                    async with binding_lock(*actor):
                        if not await current(ev,bind) or not authenticated(bind):return
                        try:
                            cache.save(key,image,style,png)
                        except (OSError,ValueError) as exc:
                            logger.warning(f'[AliceUID] solo cache write error_type={type(exc).__name__}')
                stamp = datetime.fromtimestamp(image.captured_at,ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
                reply = [MessageSegment.image(png), cache_warning + f'已使用本地缓存（{stamp} 北京时间生成，最长保存5天，读取不顺延）。\n'
                         f'如练度发生了变化，请发送{refresh_command}重新导入并计算。']
            else:
                try:
                    await bot.send(NOTICE,at_sender=True)
                except Exception as exc:
                    record_failure('个人突袭','等待提示发送',exc)
                    return
                previous_key = key
                client,bind = await load_client(*actor)
                if client is None:
                    reply = unavailable_message(bind)
                elif await current(ev,bind):
                    # A binding replacement during local loading must use its own cache identity.
                    key = identity(bind,actor,selection.mode)
                    if key != previous_key:
                        fallback = None
                    async def prepare():
                        account = await owned_account(client,bind)
                        if not await current(ev,bind) or not authenticated(bind):return None
                        image = await retries.run(lambda:capture(account, mode=selection.mode),
                                                  valid=retry_allowed)
                        from .identity import prepare_identity
                        image = replace(image, presentation=await prepare_identity(account, bind))
                        try:
                            await get_monitor().record(image, SERVERS[int(bind.area_id)][0])
                        except (OSError, ValueError) as exc:
                            record_failure('个人突袭', '网站快照保存', exc)
                        if not await current(ev,bind) or not authenticated(bind):return None
                        png = await draw_solo(image,bind,client.region,theme=theme)
                        if not await current(ev,bind) or not authenticated(bind):return None
                        style = style_key(image,bind,theme)
                        async with binding_lock(*actor):
                            if not await current(ev,bind) or not authenticated(bind):return None
                            try:
                                cache.save(key,image,style,png)
                            except (OSError,ValueError) as exc:
                                logger.warning(f'[AliceUID] solo cache write error_type={type(exc).__name__}')
                                return [MessageSegment.image(png),'计算成功，但本地缓存保存失败，请管理员检查存储。']
                        return [MessageSegment.image(png),
                                f'已重新同步本人公开养成并计算；后续查询先检查赛季更新。练度变化可发送{refresh_command}重新计算数据。']
                    reply = await asyncio.wait_for(prepare(),timeout=720)
    except NikkeLoginRequired:
        if bind is not None:mark_invalid(bind,401)
        reply = RELOGIN
    except RetryAborted:
        return
    except SoloTransient as exc:
        detail = f'最后阶段：{exc.stage}。' if exc.stage else ''
        reply = f'个人突袭推荐暂未完成：最多3轮静默尝试仍无响应，本次请求已停止。{detail}请稍后再试。'
    except SoloUnavailable as exc:
        reply = str(exc)
    except NikkeApiError as exc:
        record_failure('个人突袭', '本人资料读取', exc)
        if bind is not None and is_login_error(exc):mark_invalid(bind,exc.code)
        reply = RELOGIN if is_login_error(exc) else '本人账号资料查询失败，请稍后重试。'
    except asyncio.TimeoutError as exc:
        record_failure('个人突袭', '总等待', exc)
        reply = '个人突袭推荐等待超时，请稍后重试或直接访问dildoro.com。'
    except Exception as exc:
        record_failure('个人突袭', '命令执行', exc)
        logger.warning(f'[AliceUID] solo experimental error_type={type(exc).__name__}')
        reply = '实验性个人突袭推荐暂不可用，可能是网站更新或服务繁忙，请稍后重试或直接访问dildoro.com。'
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                record_failure('个人突袭','连接关闭',exc)
    if fallback is not None and reply is not None and not isinstance(reply,list) and bind is not None and authenticated(bind) and await current(ev,bind):
        try:
            # Only automatic updates may fall back; explicit refresh never reads old data.
            if latest is not None:
                fallback = replace(fallback, site={**fallback.site, 'current_raid': latest.get('current_raid'), 'active': latest.get('active'), '_listing': latest.get('_listing', {})})
            png = await draw_solo(fallback,bind,REGIONS.get(int(bind.area_id)) or HMT_REGION,theme=theme)
            stamp = datetime.fromtimestamp(fallback.captured_at,ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
            reply = [MessageSegment.image(png),f'本次养成同步或重新计算未完成：{reply}\n以下为此前生成的结果（{stamp} 北京时间），赛季与阵容可能已有变化。可用{refresh_command}重试。']
        except Exception as exc:
            record_failure('个人突袭','旧结果重绘',exc)
    if reply is not None and await allowed(ev):
        if bind is None:
            await bot.send(reply,at_sender=True)
        else:
            async with binding_lock(*actor):
                if await current(ev,bind):
                    if isinstance(reply,list) and not authenticated(bind):reply = unavailable_message(bind)
                    await bot.send(reply,at_sender=True)


@sv_solo.on_command(('个人突袭推荐', '单人突袭推荐'))
async def solo_command(bot,ev):
    if not await allowed(ev):
        return
    actor = _requests.enter(ev)
    if actor is None:
        return
    try:
        await _solo_command(bot,ev)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        record_failure('个人突袭','最终处理或发送',exc)
    finally:
        _requests.leave(actor)
