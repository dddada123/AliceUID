"""Export only the sender's current complete local snapshot to this conversation."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV, SL

from ..nikke_commands import command_prefix
from ..nikke_character.cache import panel_identity
from ..nikke_character.service import character_queries, CharacterDataError
from ..nikke_permissions.runtime import get_policy
from ..nikke_roster.commands import allowed
from ..nikke_user.models import AliceBind
from ..nikke_user.service import binding_lock
from .model import ExportError, prepare
from .workbook import build_workbook
from .options import ExportOptions, PATTERN, parse, require_available
from ..nikke_api.client import NikkeApiError

sv_export = SV('妮姬练度全量导出', pm=6, priority=2)
_active = set()
_slots = asyncio.Semaphore(2)


def _native_allowed(item, ev, parent_area=None):
    if item is None or not getattr(item, 'enabled', True):
        return False
    kind = 'group' if getattr(ev, 'group_id', None) else 'direct'
    area = getattr(item, 'area', 'ALL')
    if area not in ('ALL', 'SV', kind.upper()) and parent_area != 'ALL':
        return False
    if int(getattr(ev, 'user_pm', 6)) > int(getattr(item, 'pm', 6)):
        return False
    targets = {str(ev.user_id)}
    if kind == 'group':
        targets.add(str(ev.group_id))
    black = set(map(str, getattr(item, 'black_list', [])))
    white = set(map(str, getattr(item, 'white_list', []))) - {''}
    return not targets & black and (not white or bool(targets & white))


async def access(ev):
    if not await allowed(get_policy(), ev):
        return False
    plugin = SL.plugins.get('AliceUID')
    if not _native_allowed(plugin, ev) or not _native_allowed(sv_export, ev, getattr(plugin, 'area', None)):
        return False
    from gsuid_core.utils.plugins_config.gs_config import sp_config
    black = set(map(str, sp_config.get_config('BlackList').data))
    return not {str(ev.user_id), str(getattr(ev, 'group_id', '') or '')} & black


def _render(snapshot, bind, options=None):
    options = options or ExportOptions()
    require_available(options)
    from ..nikke_api.client import REGIONS, HMT_REGION
    from ..nikke_resource.service import get_resources
    region = HMT_REGION if bind.area_id == HMT_REGION.area_id else REGIONS.get(bind.area_id)
    if region is None:
        raise ExportError('当前绑定的区服未知，请检查账号绑定。')
    # load_static is local-only and has bundled fallback; no ensure/download calls.
    from .local import equipment_labels
    resources = get_resources()
    static = resources.load_static()
    labels = asyncio.run(equipment_labels(snapshot, static, getattr(resources, 'root', None)))
    attributes = snapshot.get('attributes', {})
    if getattr(resources, 'root', None) is not None and getattr(resources, 'bundled', None) is not None:
        from ..nikke_resource.attributes import get_metadata
        attributes = get_metadata(resources).compute(snapshot, static)
    simulations = None
    if options.level is not None:
        if getattr(resources, 'root', None) is not None and getattr(resources, 'bundled', None) is not None:
            simulations = get_metadata(resources).compute(snapshot, static, level=options.level)
        else:
            simulations = {}
        if simulations and all(a.get('reason') == '目标等级没有完整成长数据' for a in simulations.values()):
            raise ExportError('目标等级没有完整成长数据，请稍后更新公开资料；不会外推或截断等级。')
    data = prepare(snapshot, bind, static, region=region.label, equipment=labels,
                   attributes=attributes, simulations=simulations, target_level=options.level)
    if options.format == 'json':
        from .json_export import build_json
        return data.filename.removesuffix('.xlsx') + '.json', build_json(data)
    return data.filename, build_workbook(data)


async def _thread_render(snapshot, bind, options=None):
    worker = asyncio.create_task(asyncio.to_thread(_render, snapshot, bind, options))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Do not release the user's slot while an uninterruptible local writer is still alive.
        try:
            await asyncio.shield(worker)
        except Exception:
            pass
        raise


async def _export(bot, ev, options=None):
    options = options or ExportOptions()
    at_sender = bool(getattr(ev, 'group_id', None))
    if not await access(ev):
        await bot.send('当前用户或群未开放妮姬练度导出，请联系管理员。', at_sender=at_sender)
        return
    try:
        require_available(options)
    except ExportError as exc:
        await bot.send(str(exc).replace('nk', command_prefix()), at_sender=at_sender)
        return
    owner = (str(ev.user_id), str(ev.bot_id))
    if owner in _active:
        await bot.send('你的练度表正在生成或发送，请稍候；本次不会重复导出。', at_sender=at_sender)
        return
    _active.add(owner)
    client = None
    try:
        bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
        if bind is None:
            raise ExportError(f'请先使用 {command_prefix()}登录 绑定本人账号。')
        async def current_owner():
            current = await AliceBind.get_bind(ev.user_id, ev.bot_id)
            return current is not None and panel_identity(current) == panel_identity(bind) and await access(ev)
        public_recheck = None
        async with _slots:
            if options.share:
                from ..nikke_user.service import load_client
                from ..nikke_user.auth_state import unavailable_message
                from .public import fetch_public
                client, authenticated_bind = await load_client(ev.user_id, ev.bot_id)
                if client is None:
                    raise ExportError(unavailable_message(authenticated_bind))
                if panel_identity(authenticated_bind) != panel_identity(bind) or not await current_owner():
                    raise ExportError('绑定或权限已变化，已停止导出。')
                async with asyncio.timeout(300):
                    snapshot, target_bind, public_recheck = await fetch_public(client, bind, options.share, current_owner)
                    from ..nikke_resource.attributes import prepare_snapshot
                    await prepare_snapshot(snapshot)
            else:
                from ..nikke_user.panel_refresh import wait_for_refresh
                await wait_for_refresh(bind)
                async with binding_lock(ev.user_id, ev.bot_id):
                    if not await current_owner():
                        raise ExportError('绑定或权限已变化，已停止导出。')
                    store = character_queries.store()
                    snapshot = deepcopy(store.read(panel_identity(bind))) if store is not None else {}
                    force_refresh = False
                    if store is not None and hasattr(store, 'latest_roster'):
                        stamp, rows = store.latest_roster(panel_identity(bind), snapshot)
                        if (stamp > snapshot.get('roster_checked_at', snapshot.get('saved_at', 0))
                                and {r.get('name_code') for r in rows} != {r.get('name_code') for r in snapshot.get('roster', [])}):
                            force_refresh = True
                            snapshot['complete'] = False
                from .snapshot import ready as export_ready
                if not export_ready(snapshot):
                    from ..nikke_user.service import load_client
                    from ..nikke_user.auth_state import unavailable_message
                    client, authenticated_bind = await load_client(ev.user_id, ev.bot_id)
                    if client is None:
                        raise ExportError(unavailable_message(authenticated_bind))
                    if panel_identity(authenticated_bind) != panel_identity(bind) or not await current_owner():
                        raise ExportError('绑定或权限已变化，已停止更新旧缓存。')
                    await bot.send('首次使用新版练度导出，正在自动刷新全部角色面板并升级缓存，请稍候。', at_sender=at_sender)
                    from ..nikke_user.panel_refresh import refresh_panel
                    from ..nikke_resource.attributes import prepare_snapshot
                    async with asyncio.timeout(300):
                        await refresh_panel(client, bind, actor=ev.user_id, bot=ev.bot_id, wait=True,
                                            only_missing=not force_refresh, policy=get_policy(), event=ev,
                                            attribute_prepare=prepare_snapshot)
                async with binding_lock(ev.user_id, ev.bot_id):
                    if not await current_owner():
                        raise ExportError('绑定或权限已变化，已停止导出。')
                    snapshot = deepcopy(store.read(panel_identity(bind))) if store is not None else {}
                    if not export_ready(snapshot):
                        raise ExportError('新版面板缓存准备未完成，请稍后执行刷新面板再重试导出。')
                    epoch = character_queries._epochs.get(character_queries._account(bind), 0)
                target_bind = bind
            from ..nikke_resource.attributes import repair_snapshot_dependencies
            async with asyncio.timeout(120):
                await repair_snapshot_dependencies(snapshot, level=options.level)
            if options == ExportOptions():
                filename, contents = await _thread_render(snapshot, target_bind)
            else:
                filename, contents = await _thread_render(snapshot, target_bind, options)
            if public_recheck is not None:
                async with asyncio.timeout(60):
                    await public_recheck()
            async with binding_lock(ev.user_id, ev.bot_id):
                if not await current_owner():
                    raise ExportError('绑定或权限已变化，未发送旧账号练度表。')
                if not options.share:
                    latest = store.read(panel_identity(bind)) if store is not None else {}
                    if (latest.get('saved_at') != snapshot.get('saved_at') or
                            character_queries._epochs.get(character_queries._account(bind), 0) != epoch):
                        raise ExportError('练度缓存刚刚更新，请重新导出；未发送旧数据。')
                # Native file messages only; never render, forward to another chat or host a public download.
                try:
                    receipt = await bot.send(MessageSegment.file(contents, filename))
                    if receipt is False or receipt == []:
                        raise RuntimeError('file delivery rejected')
                except Exception as exc:
                    logger.warning(f'[AliceUID] 练度表文件发送失败 error_type={type(exc).__name__}')
                    await bot.send('练度表已生成，但文件发送失败。请管理员检查 QQ 接入端的文件上传支持及权限；未自动重复发送。', at_sender=at_sender)
    except (TimeoutError, asyncio.TimeoutError):
        await bot.send('练度数据读取超时，未发送不完整文件，请稍后重试。', at_sender=at_sender)
    except ExportError as exc:
        message = str(exc).replace('请先刷新面板', f'请先执行 {command_prefix()}刷新面板')
        await bot.send(message, at_sender=at_sender)
    except CharacterDataError as exc:
        await bot.send('面板缓存准备未完成：' + str(exc), at_sender=at_sender)
    except asyncio.CancelledError:
        raise
    except NikkeApiError as exc:
        from ..nikke_user.auth_state import RELOGIN, is_login_error
        message = RELOGIN if is_login_error(exc) else {
            1301002: '目标用户未开放资料访问，请检查 Blablalink 公开设置。',
            403: '社区拒绝访问，请稍后检查账号或公开设置。',
            429: '社区请求较频繁，请稍后重试。',
        }.get(exc.code, f'练度读取失败（{exc.code}），未生成不完整文件。')
        await bot.send(message, at_sender=at_sender)
    except Exception as exc:
        logger.error(f'[AliceUID] 练度全量导出失败 error_type={type(exc).__name__}')
        await bot.send('练度表生成失败，请稍后重试或联系管理员检查日志。', at_sender=at_sender)
    finally:
        try:
            if client is not None:
                await client.close()
        except Exception as exc:
            logger.warning(f'[AliceUID] 导出客户端关闭失败 error_type={type(exc).__name__}')
        finally:
            _active.discard(owner)


@sv_export.on_fullmatch('练度全量导出', block=True)
async def export_cmd(bot, ev):
    await _export(bot, ev)


async def _export_text(bot, ev, text):
    try:
        options = parse(text)
    except ExportError as exc:
        if await access(ev):
            await bot.send(str(exc), at_sender=bool(getattr(ev, 'group_id', None)))
        return
    await _export(bot, ev, options)


@sv_export.on_command(('练度全量导出', '全量导出'), block=True)
async def export_plain(bot, ev):
    # A longer command wins over generic 练度 even with persisted SV priority=3.
    await _export_text(bot, ev, '练度全量导出' + str(getattr(ev, 'text', '') or ''))


@sv_export.on_regex(r'^(?=[0-9])' + PATTERN[1:], block=True)
async def export_extended(bot, ev):
    groups = getattr(ev, 'regex_dict', None)
    text = ((groups.get('level') or '') + '练度全量导出' + (groups.get('tail') or '')) if groups else str(getattr(ev, 'text', ''))
    await _export_text(bot, ev, text)
