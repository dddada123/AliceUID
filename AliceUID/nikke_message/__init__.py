"""Standard title/image nodes, optional encoding and NapCat delivery confirmation."""
from __future__ import annotations
import asyncio
from collections import OrderedDict
from time import monotonic

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from .images import prepare_forward_content

# Connection metadata only, no image/user content. Bound storage and give a stuck
# Highway upload time to finish before this plugin attempts another forward.
_paused = OrderedDict()
PAUSE_SECONDS = 60
_retry_receipts = {}
_image_slots = asyncio.Semaphore(1)


def _pause(key):
    _paused[key] = monotonic() + PAUSE_SECONDS
    _paused.move_to_end(key)
    while len(_paused) > 64:
        expired, _ = _paused.popitem(last=False)
        _retry_receipts.pop(expired, None)


def _receipt_timeout():
    from .receipt import configured_timeout
    return configured_timeout()


async def _pending(bot, at_sender, key, message):
    _pause(key)
    logger.warning(f'[AliceUID] 转发上传未确认，普通发送原内容一次，暂停本连接转发{PAUSE_SECONDS}秒；迟到成功可能重复，不再重试转发')
    return await bot.send(message, at_sender=at_sender)

def display_name(value, fallback):
    """Keep player/guild names as plain text and prevent a multiline preview."""
    return ' '.join(str(value or '').split())[:100] or fallback


async def send_with_forward(bot, ev, message, *, config_key, title=None):
    """Keep transport metadata out of nodes and all sends behind actor guards.

    xiowo's NapCat adapter catches OneBot errors outside Core's send coroutine.
    For that known connection use Core's wait_recall receipt support; otherwise
    a websocket write returning None says nothing about delivery to QQ.
    """
    from ..nikke_config.config import AliceUIDConfig
    from gsuid_core import bot as core_bot

    event = ev if ev is not None else getattr(bot, 'ev', None)
    group = getattr(event, 'group_id', None)
    onebot = getattr(event, 'bot_id', '') == 'onebot'
    at_sender = bool(group) if event is not None else True
    mode = getattr(core_bot, 'enable_forward', '允许')
    eligible = mode in (None, '允许') and not (onebot and not group)
    ws_id = str(getattr(event, 'WS_BOT_ID', '') or '')
    napcat = onebot and (ws_id == 'napcat' or ws_id.startswith('napcat-'))
    transport = getattr(bot, 'bot', None)
    connection = (ws_id, str(getattr(event, 'bot_self_id', '') or ''))
    if napcat and _paused.get(connection, 0) > monotonic():
        eligible = False
    elif connection in _paused:
        _paused.pop(connection, None)
        retry_transport = _retry_receipts.pop(connection, None)
        if retry_transport is transport and getattr(transport, '_supports_recall', None) is False:
            # Only retry a capability latch caused by this plugin's own send.
            # A connection already unsupported before our attempt stays untouched.
            transport._supports_recall = None
            transport._recall_timeout_streak = 0
    if napcat and (getattr(transport, '_supports_recall', None) is False
                   or not isinstance(getattr(transport, '_recall_waiters', None), dict)
                   or getattr(event, 'task_event', None) is not None):
        # Older Core / latched unsupported receipts: never send then blindly
        # duplicate an unobservable forward. Use the proven ordinary path.
        eligible = False
    if bool(AliceUIDConfig.get_config(config_key).data) and eligible:
        items = message if isinstance(message, list) else [message]
        content = [
            MessageSegment.text(item) if isinstance(item, str) else
            MessageSegment.image(item) if isinstance(item, bytes) else item
            for item in items if getattr(item, 'type', None) not in ('at', 'at_all')
        ]
        if title:
            content.insert(0, MessageSegment.text(str(title)))
        if config_key != 'AliceUID_LoginForward':
            try:
                async with _image_slots:
                    content = await asyncio.to_thread(prepare_forward_content, content)
            except Exception as exc:
                logger.warning(f'[AliceUID] 转发图片准备失败，保留完整原图普通发送 error_type={type(exc).__name__}')
                return await bot.send(message, at_sender=at_sender)
        node = MessageSegment.node(content)
        kind = {'AliceUID_HelpForward': 'help', 'AliceUID_RosterForward': 'roster',
                'AliceUID_UnionForward': 'union', 'AliceUID_LoginForward': 'login'}.get(config_key, 'other')
        logger.info(f'[AliceUID] 转发发送 kind={kind} nodes={len(content)} '
                    f'images={sum(getattr(item, "type", None) == "image" for item in content)} '
                    f'strategy={"login_original" if kind == "login" else "classic_node"}')
        from .receipt import receipt_scope, install_timeout_override, core_timeout
        receipt_seconds = _receipt_timeout() if napcat else None
        if napcat and not install_timeout_override(transport):
            receipt_seconds = core_timeout(transport)
            logger.warning(f'[AliceUID] 当前Core不支持单次回执等待覆盖，沿用Core等待{receipt_seconds}秒；自定义值未应用')
        previous_support = getattr(transport, '_supports_recall', None)
        started = monotonic()
        try:
            # Core Bot.send defaults at_sender=False: keep this a pure node
            # frame, matching fix1. Only the ordinary fallback may mention.
            if napcat:
                # Keep the original Bot.send / live access guard. Only the
                # awaited Core call receives this task-local timeout value.
                with receipt_scope(transport, receipt_seconds):
                    result = await bot.send(node, wait_recall=True)
            else:
                result = await bot.send(node)
        except (TimeoutError, ConnectionError):
            if napcat:
                return await _pending(bot, at_sender, connection, message)
            logger.warning('[AliceUID] 转发调用中断，回退普通消息')
        except Exception as exc:
            logger.warning(f'[AliceUID] 转发发送失败，回退普通消息 error_type={type(exc).__name__}')
        else:
            if napcat:
                elapsed = monotonic() - started
                logger.info(f'[AliceUID] 转发回执 kind={kind} elapsed_ms={int(elapsed * 1000)} '
                            f'wait_seconds={receipt_seconds} confirmed={isinstance(result, list) and any(type(item) in (str, int) and str(item).strip() for item in result)}')
                if isinstance(result, list) and any(
                    type(item) in (str, int) and str(item).strip() for item in result
                ):
                    logger.info('[AliceUID] NapCat转发已取得消息ID回执')
                    return result
                if previous_support is not False and getattr(transport, '_supports_recall', None) is False:
                    _retry_receipts[connection] = transport
                # Empty results near the Core wait deadline do NOT prove API
                # failure: NapCat may still be uploading minutes later.
                if monotonic() - started >= receipt_seconds * .9:
                    return await _pending(bot, at_sender, connection, message)
                logger.warning('[AliceUID] NapCat转发未返回消息ID且未到等待上限，回退普通消息一次')
                _pause(connection)
            elif result is not False:
                return result  # Other adapters' None / [] is not a failure.
            else:
                logger.warning('[AliceUID] 转发返回失败，回退普通消息')
    return await bot.send(message, at_sender=at_sender)
