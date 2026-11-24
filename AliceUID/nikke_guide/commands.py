"""Commands for general Blablalink guide query: nk<关键词>攻略, nk攻略查询, nk查询1~10."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import re
import time

from ..nikke_commands import command_prefix
from .registry import CATEGORY_LABELS, SYUEN_AUTHOR
from .service import EXPERIMENTAL_NOTICE, GuideService, get_guide_service
from .source import GuideError

SELECTION_TTL_SECONDS = 60
_BJ_TZ = timezone(timedelta(hours=8))
_RAID_RESERVED = ('会战', '联盟战', '工会战', '公会战')


def _format_list_message(posts, authors_by_id, *, filter_text: str = '') -> str:
    header_author = SYUEN_AUTHOR.display_name
    header_url = SYUEN_AUTHOR.homepage_url
    if posts:
        a = authors_by_id.get(posts[0].author_id)
        if a is not None:
            header_author = a.display_name
            header_url = a.homepage_url
    lines = [
        f'[AliceUID·攻略列表] 最近 {len(posts)} 篇攻略' + (f'（筛选：{filter_text}）' if filter_text else ''),
        f'作者：{header_author}',
        f'作者主页：{header_url}',
        EXPERIMENTAL_NOTICE,
        '',
    ]
    for idx, p in enumerate(posts, 1):
        cat = CATEGORY_LABELS.get(p.category, '攻略')
        dt = datetime.fromtimestamp(p.created_on, _BJ_TZ).strftime('%Y-%m-%d') if p.created_on else ''
        lang_tag = '' if str(p.original_language or '').lower().startswith('zh') else f' [{str(p.original_language).upper()}·可自动翻译]'
        lines.append(f'{idx}. [{cat}] {p.title}{lang_tag}（{dt}）')
    lines.append('')
    lines.append(f'请在 {SELECTION_TTL_SECONDS} 秒内回复 {command_prefix()}查询1 ～ {command_prefix()}查询{len(posts)} 获取对应攻略。')
    return '\n'.join(lines)


def _log_cmd_failure(stage: str, exc: BaseException):
    try:
        from ..nikke_logs.store import record_failure
        record_failure('攻略查询', stage, exc)
    except Exception:
        pass


def _log_cmd_event(stage: str, result: str, **metrics):
    try:
        from ..nikke_logs.store import event
        event('攻略查询', stage, result, **metrics)
    except Exception:
        pass


class GuideCommands:
    def __init__(
        self,
        policy,
        *,
        service_factory=get_guide_service,
        forward_sender=None,
        image_factory=None,
        clock=time.monotonic,
    ):
        self.policy = policy
        self.service_factory = service_factory
        self.forward_sender = forward_sender
        self.image_factory = image_factory
        self.clock = clock
        self._sessions: OrderedDict[tuple[str, str, str], tuple[float, list]] = OrderedDict()

    def _session_key(self, ev) -> tuple[str, str, str]:
        bot_id = str(getattr(ev, 'bot_id', '') or '')
        group_id = str(getattr(ev, 'group_id', '') or 'dm')
        user_id = str(getattr(ev, 'user_id', '') or '')
        return (bot_id, group_id, user_id)

    def _save_session(self, ev, posts: list):
        key = self._session_key(ev)
        now = self.clock()
        self._sessions[key] = (now + SELECTION_TTL_SECONDS, list(posts))
        self._sessions.move_to_end(key)
        while len(self._sessions) > 256:
            self._sessions.popitem(last=False)

    def _pop_or_get_session(self, ev) -> list | None:
        key = self._session_key(ev)
        entry = self._sessions.get(key)
        if not entry:
            return None
        expires_at, posts = entry
        if self.clock() > expires_at:
            self._sessions.pop(key, None)
            return None
        return posts

    async def allowed(self, ev) -> bool:
        return (
            self.policy.user_allowed(getattr(ev, 'user_id', None))
            and await self.policy.query_allowed(getattr(ev, 'group_id', None))
        )

    async def _send_text(self, bot, ev, text: str):
        try:
            from ..nikke_message.persona import send_reply
            return await send_reply(bot, ev, text, at_sender=True)
        except ImportError:
            return await bot.send(text, at_sender=True)

    async def _deliver_guide(self, bot, ev, result):
        image = self.image_factory
        sender = self.forward_sender
        if image is None:
            from gsuid_core.segment import MessageSegment
            image = MessageSegment.image
        if sender is None:
            from ..nikke_message import send_with_forward
            sender = send_with_forward

        # Long image already embeds the lead image, so forward 3 parts: header -> long image -> plain text.
        payload: list = [result.header_text(), image(result.long_image)]
        payload.extend(result.plain_text_chunks())

        await sender(
            bot,
            ev,
            payload,
            config_key='AliceUID_GuideForward',
            at_sender=False,
            preserve_order=True,
        )

    async def handle_keyword(self, bot, ev, raw_query: str):
        query = str(raw_query or '').strip()
        if not query or query == '查询' or any(k in query for k in _RAID_RESERVED):
            return
        if not await self.allowed(ev):
            await self._send_text(bot, ev, '本群或当前用户未开放妮姬查询，请联系管理员。')
            return

        service: GuideService = self.service_factory()
        notified = False

        async def _notify_init():
            nonlocal notified
            if not notified:
                notified = True
                await self._send_text(bot, ev, '攻略索引正在初始化，请稍候…')

        if not service.is_initialized():
            await _notify_init()

        async def on_first(_author):
            await _notify_init()

        try:
            status, posts, authors_by_id = await service.search(query, on_first_index=on_first)
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('KEYWORD_SEARCH', exc)
            await self._send_text(bot, ev, '攻略索引暂不可用，请稍后再试。')
            return

        if not await self.allowed(ev):
            return

        if status == 'none' or not posts:
            _log_cmd_event('KEYWORD_MATCH', 'NONE')
            await self._send_text(
                bot,
                ev,
                f'暂未在已收录作者（{SYUEN_AUTHOR.display_name}）的攻略中找到「{query}」相关文章。\n'
                f'可发送 {command_prefix()}攻略查询 查看最近 10 篇攻略，或尝试更换角色名/关键词。',
            )
            return

        if status == 'multiple' and len(posts) > 1:
            _log_cmd_event('KEYWORD_MATCH', 'MULTIPLE', count=len(posts))
            self._save_session(ev, posts[:10])
            msg = _format_list_message(posts[:10], authors_by_id, filter_text=query)
            sender = self.forward_sender
            if sender is None:
                from ..nikke_message import send_with_forward
                sender = send_with_forward
            await sender(bot, ev, [msg], config_key='AliceUID_GuideForward', at_sender=False, preserve_order=True)
            return

        post = posts[0]
        _log_cmd_event('KEYWORD_MATCH', 'HIT', reason=f'uuid={post.post_uuid}')
        author = authors_by_id.get(post.author_id, SYUEN_AUTHOR)

        async def on_render(p):
            await self._send_text(bot, ev, f'正在获取并生成《{p.title}》攻略长图，请稍候…')

        try:
            result = await service.render_or_get(post, author, on_rendering=on_render)
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('KEYWORD_RENDER', exc)
            await self._send_text(bot, ev, '攻略内容抓取或生成失败，请稍后再试。')
            return

        if await self.allowed(ev):
            await self._deliver_guide(bot, ev, result)

    async def handle_list(self, bot, ev):
        if not await self.allowed(ev):
            await self._send_text(bot, ev, '本群或当前用户未开放妮姬查询，请联系管理员。')
            return
        filter_text = str(getattr(ev, 'text', '') or '').strip()
        service: GuideService = self.service_factory()
        notified = False

        async def _notify_init():
            nonlocal notified
            if not notified:
                notified = True
                await self._send_text(bot, ev, '攻略索引正在初始化，请稍候…')

        if not service.is_initialized():
            await _notify_init()

        async def on_first(_author):
            await _notify_init()

        try:
            posts, authors_by_id = await service.recent_posts(
                filter_text=filter_text,
                limit=10,
                on_first_index=on_first,
            )
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('LIST_QUERY', exc)
            await self._send_text(bot, ev, '攻略列表暂不可用，请稍后再试。')
            return

        if not await self.allowed(ev):
            return
        if not posts:
            await self._send_text(bot, ev, '暂未找到符合条件的攻略帖子，请尝试不带筛选发送。')
            return

        self._save_session(ev, posts)
        msg = _format_list_message(posts, authors_by_id, filter_text=filter_text)
        sender = self.forward_sender
        if sender is None:
            from ..nikke_message import send_with_forward
            sender = send_with_forward
        await sender(bot, ev, [msg], config_key='AliceUID_GuideForward', at_sender=False, preserve_order=True)

    async def handle_pick(self, bot, ev, index: int):
        if not await self.allowed(ev):
            return
        posts = self._pop_or_get_session(ev)
        if posts is None:
            await self._send_text(
                bot,
                ev,
                f'当前没有有效的新攻略列表或已超过 {SELECTION_TTL_SECONDS} 秒，请先发送 {command_prefix()}攻略查询。',
            )
            return
        if not 1 <= index <= len(posts):
            await self._send_text(bot, ev, f'编号超出范围，请回复 {command_prefix()}查询1 ～ {command_prefix()}查询{len(posts)}。')
            return

        post = posts[index - 1]
        service: GuideService = self.service_factory()
        authors_by_id = {a.author_id: a for a in service.authors()}
        author = authors_by_id.get(post.author_id, SYUEN_AUTHOR)

        async def on_render(p):
            await self._send_text(bot, ev, f'正在获取并生成《{p.title}》攻略长图，请稍候…')

        try:
            result = await service.render_or_get(post, author, on_rendering=on_render)
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('PICK_RENDER', exc)
            await self._send_text(bot, ev, '攻略内容抓取或生成失败，请稍后再试。')
            return

        if await self.allowed(ev):
            await self._deliver_guide(bot, ev, result)


_sv = None


def setup(policy=None):
    global _sv
    if _sv is not None:
        return _sv
    from gsuid_core.sv import SV
    from ..nikke_permissions.runtime import get_policy

    commands = GuideCommands(policy if policy is not None else get_policy())
    _sv = SV('妮姬攻略查询', pm=6, priority=3)

    @_sv.on_command('攻略查询')
    async def guide_list_cmd(bot, ev):
        await commands.handle_list(bot, ev)

    @_sv.on_command('攻略')
    async def guide_prefix_cmd(bot, ev):
        text = (getattr(ev, 'text', '') or '').strip()
        if not text:
            await commands._send_text(
                bot,
                ev,
                f'用法：{command_prefix()}重白攻略 / {command_prefix()}神莲攻略 / {command_prefix()}魔方攻略\n'
                f'查看最近10篇攻略：{command_prefix()}攻略查询（60秒内回复 {command_prefix()}查询1~10 获取）',
            )
            return
        if text.startswith('查询'):
            return
        await commands.handle_keyword(bot, ev, text)

    @_sv.on_suffix('攻略')
    async def guide_suffix_cmd(bot, ev):
        text = (getattr(ev, 'text', '') or '').strip()
        if not text or '攻略' in text:
            return
        await commands.handle_keyword(bot, ev, text)

    @_sv.on_regex(r'^查询\s*([1-9]|10)$')
    async def guide_pick_cmd(bot, ev):
        raw = str(getattr(ev, 'raw_text', '') or getattr(ev, 'text', '') or '').strip()
        m = re.search(r'([1-9]|10)$', raw)
        if m:
            await commands.handle_pick(bot, ev, int(m.group(1)))

    return _sv
