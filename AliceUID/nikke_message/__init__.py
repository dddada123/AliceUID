"""Standard title/image nodes, optional encoding and NapCat delivery confirmation."""
from __future__ import annotations
import asyncio
from collections import OrderedDict
from time import monotonic

try:
    from gsuid_core.logger import logger
    from gsuid_core.segment import MessageSegment
except ImportError:  # Standalone tests import submodules without Core runtime.
    logger = None
    MessageSegment = None
from .images import prepare_forward_content

# Connection metadata only, no image/user content. Bound storage and give a stuck
# Highway upload time to finish before this plugin attempts another forward.
_paused = OrderedDict()
_image_paused = OrderedDict()
_login_paused = OrderedDict()
PAUSE_SECONDS = 60
_retry_receipts = {}
_image_slots = asyncio.Semaphore(1)


def _pause_store(bucket: str):
    if bucket == 'image':
        return _image_paused
    if bucket == 'login':
        return _login_paused
    return _paused


def _pause(key, *, bucket: str = 'text'):
    store = _pause_store(bucket)
    store[key] = monotonic() + PAUSE_SECONDS
    store.move_to_end(key)
    while len(store) > 64:
        expired, _ = store.popitem(last=False)
        _retry_receipts.pop((bucket, expired), None)


def _receipt_timeout():
    from .receipt import configured_timeout
    return configured_timeout()


async def _pending(bot, at_sender, key, message, *, bucket: str = 'text'):
    _pause(key, bucket=bucket)
    label = '含图' if bucket == 'image' else ('登录' if bucket == 'login' else '文本')
    logger.warning(f'[AliceUID] 转发上传未确认，普通发送原内容一次，暂停本连接{label}转发{PAUSE_SECONDS}秒；迟到成功可能重复，不再重试转发')
    return await bot.send(message, at_sender=at_sender)


def display_name(value, fallback):
    """Keep player/guild names as plain text and prevent a multiline preview."""
    return ' '.join(str(value or '').split())[:100] or fallback


def _log_structure(kind: str, route: str, mode: str, payload, *, at_sender=None, skip_reason: str | None = None):
    if logger is None:
        return
    try:
        from ..nikke_logs.store import describe_payload
        extra = f' reason={skip_reason}' if skip_reason else ''
        logger.info(
            f'[AliceUID] 发送结构 kind={kind} route={route} mode={mode} '
            f'at_sender={at_sender}{extra} segments={describe_payload(payload)}'
        )
    except Exception:
        pass


async def send_with_forward(bot, ev, message, *, config_key, title=None, at_sender=None):
    """Keep transport metadata out of nodes and all sends behind actor guards.

    xiowo's NapCat adapter catches OneBot errors outside Core's send coroutine.
    For that known connection use Core's wait_recall receipt support; otherwise
    a websocket write returning None says nothing about delivery to QQ.
    """
    from ..nikke_config.config import AliceUIDConfig
    from gsuid_core import bot as core_bot

    event = ev if ev is not None else getattr(bot, 'ev', None)
    group = getattr(event, 'group_id', None)
    route = 'group' if group else 'dm'
    onebot = getattr(event, 'bot_id', '') == 'onebot'
    if at_sender is None:
        at_sender = bool(group) if event is not None else True
    items = message if isinstance(message, list) else [message]
    has_images = any(getattr(item, 'type', None) == 'image' for item in items)
    kind = {'AliceUID_HelpForward': 'help', 'AliceUID_RosterForward': 'roster',
            'AliceUID_UnionForward': 'union', 'AliceUID_RaidGuideForward': 'raid_guide', 'AliceUID_LoginForward': 'login',
            'AliceUID_CDKForward': 'cdk', 'AliceUID_CDKResultForward': 'cdk_result',
            'AliceUID_AccountListForward': 'accounts'}.get(config_key, 'other')
    bucket = 'login' if kind == 'login' else ('image' if has_images else 'text')

    mode = getattr(core_bot, 'enable_forward', '允许')
    ws_id = str(getattr(event, 'WS_BOT_ID', '') or '')
    napcat = onebot and (ws_id == 'napcat' or ws_id.startswith('napcat-'))
    transport = getattr(bot, 'bot', None)
    connection = (ws_id, str(getattr(event, 'bot_self_id', '') or ''))
    pause_store = _pause_store(bucket)

    eligible = True
    skip_reason = None
    if bool(AliceUIDConfig.get_config(config_key).data) is False:
        eligible, skip_reason = False, 'config_disabled'
    elif mode not in (None, '允许'):
        eligible, skip_reason = False, 'core_forward_disabled'
    elif onebot and not group:
        eligible, skip_reason = False, 'onebot_dm_unsupported'
    elif napcat and pause_store.get(connection, 0) > monotonic():
        eligible, skip_reason = False, 'paused_cooldown'
    elif connection in pause_store:
        pause_store.pop(connection, None)
        retry_transport = _retry_receipts.pop((bucket, connection), None)
        if retry_transport is transport and getattr(transport, '_supports_recall', None) is False:
            # Only retry a capability latch caused by this plugin's own send.
            # A connection already unsupported before our attempt stays untouched.
            transport._supports_recall = None
            transport._recall_timeout_streak = 0
    if eligible and napcat:
        if getattr(transport, '_supports_recall', None) is False:
            eligible, skip_reason = False, 'supports_recall_false'
        elif not isinstance(getattr(transport, '_recall_waiters', None), dict):
            eligible, skip_reason = False, 'no_recall_waiters'
        elif getattr(event, 'task_event', None) is not None:
            eligible, skip_reason = False, 'task_event'

    if skip_reason and logger is not None:
        logger.info(f'[AliceUID] 转发跳过 kind={kind} bucket={bucket} route={route} has_images={has_images} reason={skip_reason}')

    if eligible:
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
                _log_structure(kind, route, 'plain_fallback', message, at_sender=at_sender, skip_reason='prepare_failed')
                return await bot.send(message, at_sender=at_sender)
        node = MessageSegment.node(content)
        logger.info(f'[AliceUID] 转发发送 kind={kind} nodes={len(content)} '
                    f'images={sum(getattr(item, "type", None) == "image" for item in content)} '
                    f'strategy={"login_original" if kind == "login" else "classic_node"}')
        _log_structure(kind, route, 'forward', node, at_sender=False)
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
                if previous_support is not False and getattr(transport, '_supports_recall', None) is False:
                    _retry_receipts[(bucket, connection)] = transport
                _log_structure(kind, route, 'plain_fallback', message, at_sender=at_sender, skip_reason='timeout_or_conn')
                return await _pending(bot, at_sender, connection, message, bucket=bucket)
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
                    _retry_receipts[(bucket, connection)] = transport
                # Empty results near the Core wait deadline do NOT prove API
                # failure: NapCat may still be uploading minutes later.
                if monotonic() - started >= receipt_seconds * .9:
                    _log_structure(kind, route, 'plain_fallback', message, at_sender=at_sender, skip_reason='deadline_empty')
                    return await _pending(bot, at_sender, connection, message, bucket=bucket)
                logger.warning('[AliceUID] NapCat转发未返回消息ID且未到等待上限，回退普通消息一次')
                _pause(connection, bucket=bucket)
            elif result is not False:
                return result  # Other adapters' None / [] is not a failure.
            else:
                logger.warning('[AliceUID] 转发返回失败，回退普通消息')
    _log_structure(kind, route, 'plain_fallback' if skip_reason is None else 'plain', message, at_sender=at_sender, skip_reason=skip_reason)
    return await bot.send(message, at_sender=at_sender)
