"""Export only the sender's current complete local snapshot to this conversation."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV, SL

from ..nikke_commands import command_prefix
from ..nikke_character.cache import panel_identity
from ..nikke_character.service import character_queries
from ..nikke_permissions.runtime import get_policy
from ..nikke_roster.commands import allowed
from ..nikke_user.models import AliceBind
from ..nikke_user.service import binding_lock
from .model import ExportError, prepare
from .workbook import build_workbook

sv_export = SV('妮姬练度全量导出', pm=6, priority=3)
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


def _render(snapshot, bind):
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
    data = prepare(snapshot, bind, static, region=region.label, equipment=labels)
    return data.filename, build_workbook(data)


async def _thread_render(snapshot, bind):
    worker = asyncio.create_task(asyncio.to_thread(_render, snapshot, bind))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Do not release the user's slot while an uninterruptible local writer is still alive.
        try:
            await asyncio.shield(worker)
        except Exception:
            pass
        raise


@sv_export.on_fullmatch('练度全量导出', block=True)
async def export_cmd(bot, ev):
    at_sender = bool(getattr(ev, 'group_id', None))
    if not await access(ev):
        await bot.send('当前用户或群未开放妮姬练度导出，请联系管理员。', at_sender=at_sender)
        return
    owner = (str(ev.user_id), str(ev.bot_id))
    if owner in _active:
        await bot.send('你的练度表正在生成或发送，请稍候；本次不会重复导出。', at_sender=at_sender)
        return
    _active.add(owner)
    try:
        bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
        if bind is None:
            raise ExportError(f'请先使用 {command_prefix()}登录 绑定本人账号。')
        from ..nikke_user.panel_refresh import wait_for_refresh
        await wait_for_refresh(bind)
        async with _slots:
            async with binding_lock(ev.user_id, ev.bot_id):
                current = await AliceBind.get_bind(ev.user_id, ev.bot_id)
                if current is None or panel_identity(current) != panel_identity(bind) or not await access(ev):
                    raise ExportError('绑定或权限已变化，已停止导出。')
                store = character_queries.store()
                snapshot = deepcopy(store.read(panel_identity(bind))) if store is not None else {}
                epoch = character_queries._epochs.get(character_queries._account(bind), 0)
            filename, contents = await _thread_render(snapshot, bind)
            async with binding_lock(ev.user_id, ev.bot_id):
                current = await AliceBind.get_bind(ev.user_id, ev.bot_id)
                if current is None or panel_identity(current) != panel_identity(bind) or not await access(ev):
                    raise ExportError('绑定或权限已变化，未发送旧账号练度表。')
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
    except ExportError as exc:
        message = str(exc).replace('请先刷新面板', f'请先执行 {command_prefix()}刷新面板')
        await bot.send(message, at_sender=at_sender)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f'[AliceUID] 练度全量导出失败 error_type={type(exc).__name__}')
        await bot.send('练度表生成失败，请稍后重试或联系管理员检查日志。', at_sender=at_sender)
    finally:
        _active.discard(owner)
