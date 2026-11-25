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

SELECTION_TTL_SECONDS = 120
_BJ_TZ = timezone(timedelta(hours=8))
_RAID_RESERVED = ('会战', '联盟战', '工会战', '公会战')


def _parse_list_args(raw: str) -> tuple[str, int]:
    text = str(raw or '').strip()
    if not text:
        return '', 1
    m = re.match(r'^(.*?)(?:\s+|第)?([1-9]\d{0,2})页?$', text)
    if m:
        prefix_part = m.group(1).strip()
        if prefix_part or re.fullmatch(r'(?:第?\s*[1-9]\d{0,2}\s*页?|[1-9]\d{0,2})', text):
            return prefix_part, max(1, int(m.group(2)))
    m_p = re.match(r'^(.*?)\s*[pP]([1-9]\d{0,2})$', text)
    if m_p:
        return m_p.group(1).strip(), max(1, int(m_p.group(2)))
    return text, 1


def _format_list_chunks(
    posts,
    authors_by_id,
    *,
    filter_text: str = '',
    page: int = 1,
    total_pages: int = 1,
    total_count: int | None = None,
    dual_bubble: bool = False,
) -> list[str]:
    header_author = SYUEN_AUTHOR.display_name
    header_url = SYUEN_AUTHOR.homepage_url
    if posts:
        a = authors_by_id.get(posts[0].author_id)
        if a is not None:
            header_author = a.display_name
            header_url = a.homepage_url
    count_info = f'（共 {total_count} 篇，第 {page}/{total_pages} 页）' if total_count is not None and total_pages > 1 else ''
    filter_info = f'（筛选：{filter_text}）' if filter_text else ''
    prefix = command_prefix()
    lines_head = [
        f'[AliceUID·攻略列表] 本页 {len(posts)} 篇攻略{filter_info}{count_info}',
        f'作者：{header_author}',
        f'作者主页：{header_url}',
        EXPERIMENTAL_NOTICE,
        '',
    ]

    def _entry_line(idx: int, p) -> str:
        cat = CATEGORY_LABELS.get(p.category, '攻略')
        dt = datetime.fromtimestamp(p.created_on, _BJ_TZ).strftime('%Y-%m-%d') if p.created_on else ''
        lang_tag = '' if str(p.original_language or '').lower().startswith('zh') else f' [{str(p.original_language).upper()}·可自动翻译]'
        return f'{idx}. [{cat}] {p.title}{lang_tag}（{dt}）'

    footer_lines = [
        '',
        f'请在 {SELECTION_TTL_SECONDS} 秒内回复 {prefix}查询1 ～ {prefix}查询{len(posts)} 获取对应攻略。',
    ]
    if total_pages > 1:
        next_hint = f'{prefix}攻略查询 {filter_text} {page + 1}'.replace('  ', ' ').strip() if page < total_pages else f'{prefix}攻略查询 {filter_text} 1'.replace('  ', ' ').strip()
        footer_lines.append(f'翻页查看：发送 {next_hint}')

    if dual_bubble and len(posts) > 10:
        b1 = lines_head + [_entry_line(idx, p) for idx, p in enumerate(posts[:10], 1)]
        b2 = [f'[AliceUID·攻略列表（续）] 第 {page}/{total_pages} 页', ''] + [_entry_line(idx, p) for idx, p in enumerate(posts[10:], 11)] + footer_lines
        return ['\n'.join(b1), '\n'.join(b2)]

    body = lines_head + [_entry_line(idx, p) for idx, p in enumerate(posts, 1)] + footer_lines
    return ['\n'.join(body)]


def _format_list_message(posts, authors_by_id, *, filter_text: str = '') -> str:
    return _format_list_chunks(posts, authors_by_id, filter_text=filter_text)[0]


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


def _infer_display_and_code(p, alias_by_code: dict[int, list[str]], names_by_code: dict[int, str]) -> tuple[str, int | None]:
    code = p.name_code
    if code is not None and code in names_by_code:
        return names_by_code[code], code
    if names_by_code:
        from .matcher import norm_key
        blob = norm_key(' '.join([p.subject or '', p.title or '', *(p.tags or ())]))
        for cid, cname in sorted(names_by_code.items(), key=lambda kv: len(norm_key(kv[1])), reverse=True):
            ck = norm_key(cname)
            if ck and ck in blob:
                return cname, cid
    return (p.subject or p.title), code


def _format_suggest_message(
    match_res,
    posts,
    alias_by_code: dict[int, list[str]],
    names_by_code: dict[int, str] | None = None,
) -> str:
    prefix = command_prefix()
    target = match_res.resolved_label or '目标内容'
    lines: list[str] = [f'暂未找到「{target}」的攻略，但找到了相关攻略：']
    name_map = names_by_code or {}
    if len(posts) == 1:
        p = posts[0]
        display, code = _infer_display_and_code(p, alias_by_code, name_map)
        aliases = sorted(set(alias_by_code.get(code, ())), key=len)[:3] if code is not None else []
        alias_suffix = f'（别名：{"、".join(aliases)}）' if aliases else ''
        lines.append(f'• {display}{alias_suffix}')
        lines.append(f'是否需要「{display}」攻略？')
        hint = f'{prefix}{display}攻略'
        if aliases:
            hint += f'（或 {prefix}{aliases[0]}攻略）'
        lines.append(f'如果是，请发送：{hint}（也可在 {SELECTION_TTL_SECONDS} 秒内回复 {prefix}查询1）')
    else:
        for idx, p in enumerate(posts, 1):
            display, code = _infer_display_and_code(p, alias_by_code, name_map)
            aliases = sorted(set(alias_by_code.get(code, ())), key=len)[:2] if code is not None else []
            alt = f' / {prefix}{aliases[0]}攻略' if aliases else ''
            lines.append(f'{idx}. {display}（可发 {prefix}{display}攻略{alt}）')
        lines.append(f'请发送对应指令，或在 {SELECTION_TTL_SECONDS} 秒内回复 {prefix}查询1 ～ {prefix}查询{len(posts)} 获取。')
    return '\n'.join(lines)


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
        try:
            from ..nikke_commands.selection import register_selection
            register_selection(ev, lambda b, e, idx: self.handle_pick(b, e, idx), ttl=SELECTION_TTL_SECONDS, clock=self.clock)
        except Exception:
            pass

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
        payload: list = [result.header_text()]
        if result.long_image is not None:
            payload.append(image(result.long_image))
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
        if not query or query in ('查询', '重索引') or any(k in query for k in _RAID_RESERVED):
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
                try:
                    from ..nikke_message.persona import guide_init_wait_text
                    msg = guide_init_wait_text()
                except ImportError:
                    msg = '攻略索引正在初始化，请稍候…'
                await self._send_text(bot, ev, msg)

        if not service.is_initialized():
            await _notify_init()

        async def on_first(_author):
            await _notify_init()

        try:
            match_res, authors_by_id, alias_by_code, names_by_code = await service.search_rich(query, on_first_index=on_first)
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('KEYWORD_SEARCH', exc)
            await self._send_text(bot, ev, '攻略索引暂不可用，请稍后再试。')
            return

        if not await self.allowed(ev):
            return

        status, posts = match_res.status, match_res.posts
        if status == 'none' or not posts:
            _log_cmd_event('KEYWORD_MATCH', 'NONE')
            target_label = match_res.resolved_label or query
            try:
                from ..nikke_message.persona import guide_not_found_text
                msg = guide_not_found_text(SYUEN_AUTHOR.display_name, target_label, command_prefix())
            except ImportError:
                msg = (
                    f'暂未在已收录作者（{SYUEN_AUTHOR.display_name}）的攻略中找到「{target_label}」相关文章。\n'
                    f'可发送 {command_prefix()}攻略查询 查看最近攻略，或尝试更换角色名/关键词。'
                )
            await self._send_text(bot, ev, msg)
            return

        if status == 'suggest':
            _log_cmd_event('KEYWORD_MATCH', 'SUGGEST', count=len(posts))
            self._save_session(ev, posts[:10])
            await self._send_text(bot, ev, _format_suggest_message(match_res, posts[:10], alias_by_code, names_by_code))
            return

        if status == 'multiple' and len(posts) > 1:
            _log_cmd_event('KEYWORD_MATCH', 'MULTIPLE', count=len(posts))
            self._save_session(ev, posts[:20])
            msg = _format_list_message(posts[:20], authors_by_id, filter_text=query)
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
            try:
                from ..nikke_message.persona import guide_render_wait_text
                msg = guide_render_wait_text(p.title)
            except ImportError:
                msg = f'正在获取并生成《{p.title}》攻略长图，请稍候…'
            await self._send_text(bot, ev, msg)

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

    def _use_forward_list(self, ev) -> bool:
        try:
            from ..nikke_config.config import AliceUIDConfig
            if bool(AliceUIDConfig.get_config('AliceUID_GuideForward').data) is False:
                return False
        except Exception:
            pass
        if getattr(ev, 'bot_id', '') == 'onebot' and not getattr(ev, 'group_id', None):
            return False
        return True

    async def handle_list(self, bot, ev):
        if not await self.allowed(ev):
            await self._send_text(bot, ev, '本群或当前用户未开放妮姬查询，请联系管理员。')
            return
        raw_text = str(getattr(ev, 'text', '') or '').strip()
        filter_text, page = _parse_list_args(raw_text)
        forward_mode = self._use_forward_list(ev)
        page_size = 20 if forward_mode else 10
        service: GuideService = self.service_factory()
        notified = False

        async def _notify_init():
            nonlocal notified
            if not notified:
                notified = True
                try:
                    from ..nikke_message.persona import guide_init_wait_text
                    msg = guide_init_wait_text()
                except ImportError:
                    msg = '攻略索引正在初始化，请稍候…'
                await self._send_text(bot, ev, msg)

        if not service.is_initialized():
            await _notify_init()

        async def on_first(_author):
            await _notify_init()

        try:
            if hasattr(service, 'recent_posts_paged'):
                posts, total_count, total_pages, authors_by_id = await service.recent_posts_paged(
                    filter_text=filter_text,
                    page=page,
                    page_size=page_size,
                    on_first_index=on_first,
                )
            else:
                posts, authors_by_id = await service.recent_posts(
                    filter_text=filter_text,
                    limit=page_size,
                    on_first_index=on_first,
                )
                total_count, total_pages = len(posts), 1
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
            if page > 1 and total_count > 0:
                await self._send_text(bot, ev, f'第 {page} 页暂无内容，当前共 {total_pages} 页（{total_count} 篇）。')
            else:
                await self._send_text(bot, ev, '暂未找到符合条件的攻略帖子，请尝试不带筛选发送。')
            return

        self._save_session(ev, posts)
        chunks = _format_list_chunks(
            posts,
            authors_by_id,
            filter_text=filter_text,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            dual_bubble=forward_mode,
        )
        sender = self.forward_sender
        if sender is None:
            from ..nikke_message import send_with_forward
            sender = send_with_forward
        await sender(bot, ev, chunks, config_key='AliceUID_GuideForward', at_sender=False, preserve_order=True)

    async def handle_pick(self, bot, ev, index: int):
        if not await self.allowed(ev):
            return
        posts = self._pop_or_get_session(ev)
        if posts is None:
            try:
                from ..nikke_message.persona import guide_timeout_text
                msg = guide_timeout_text(SELECTION_TTL_SECONDS, command_prefix())
            except ImportError:
                msg = f'当前没有有效的新攻略列表或已超过 {SELECTION_TTL_SECONDS} 秒，请先发送 {command_prefix()}攻略查询。'
            await self._send_text(bot, ev, msg)
            return
        if not 1 <= index <= len(posts):
            await self._send_text(bot, ev, f'编号超出范围，请回复 {command_prefix()}查询1 ～ {command_prefix()}查询{len(posts)}。')
            return

        post = posts[index - 1]
        service: GuideService = self.service_factory()
        authors_by_id = {a.author_id: a for a in service.authors()}
        author = authors_by_id.get(post.author_id, SYUEN_AUTHOR)

        async def on_render(p):
            try:
                from ..nikke_message.persona import guide_render_wait_text
                msg = guide_render_wait_text(p.title)
            except ImportError:
                msg = f'正在获取并生成《{p.title}》攻略长图，请稍候…'
            await self._send_text(bot, ev, msg)

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

    async def handle_reindex(self, bot, ev, *, clear: bool = False):
        is_owner = getattr(ev, 'user_pm', 6) == 0
        if not is_owner:
            try:
                from ..nikke_user.service import is_master
                is_owner = is_master(getattr(ev, 'user_id', ''))
            except Exception:
                is_owner = False
        if not is_owner:
            await self._send_text(bot, ev, '仅 Bot 主可执行攻略重索引。')
            return
        service: GuideService = self.service_factory()
        if service.is_sync_running():
            await self._send_text(bot, ev, '攻略索引正在重建或同步中，请稍后再试。')
            return
        mode_label = '清空并全量重建' if clear else '全量刷新重索引'
        await self._send_text(bot, ev, f'正在执行攻略数据库{mode_label}，请稍候…')
        try:
            stats = await service.reindex(clear=clear)
        except GuideError as exc:
            await self._send_text(bot, ev, str(exc))
            return
        except Exception as exc:
            _log_cmd_failure('OWNER_REINDEX', exc)
            await self._send_text(bot, ev, f'攻略重索引失败：{type(exc).__name__}，请查看日志。')
            return
        await self._send_text(
            bot,
            ev,
            f'攻略索引已{mode_label}完成：当前共收录 {stats["total"]} 篇攻略，耗时 {stats["elapsed_ms"] / 1000:.1f} 秒。',
        )


_sv = None
_sv_owner = None


def setup(policy=None):
    global _sv, _sv_owner
    if _sv is not None:
        return _sv
    from gsuid_core.sv import SV
    from ..nikke_permissions.runtime import get_policy

    commands = GuideCommands(policy if policy is not None else get_policy())
    _sv = SV('妮姬攻略查询', pm=6, priority=3)
    _sv_owner = SV('妮姬攻略管理', pm=0, priority=3)

    @_sv_owner.on_command('攻略重索引', block=True)
    async def guide_reindex_cmd(bot, ev):
        arg = str(getattr(ev, 'text', '') or '').strip()
        clear = arg in ('清空', '重置', 'clear', 'reset')
        await commands.handle_reindex(bot, ev, clear=clear)

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
                f'查看最近攻略：{command_prefix()}攻略查询 [筛选/页码]（{SELECTION_TTL_SECONDS}秒内回复 {command_prefix()}查询1~20 获取）',
            )
            return
        if text.startswith(('查询', '重索引')):
            return
        await commands.handle_keyword(bot, ev, text)

    @_sv.on_suffix('攻略')
    async def guide_suffix_cmd(bot, ev):
        text = (getattr(ev, 'text', '') or '').strip()
        if not text or '攻略' in text:
            return
        await commands.handle_keyword(bot, ev, text)

    @_sv.on_regex(r'^查询\s*([1-9]|1\d|20)$')
    async def guide_pick_cmd(bot, ev):
        raw = str(getattr(ev, 'raw_text', '') or getattr(ev, 'text', '') or '').strip()
        m = re.search(r'([1-9]|1\d|20)$', raw)
        if m:
            idx = int(m.group(1))
            from ..nikke_commands.selection import dispatch_selection
            if await dispatch_selection(bot, ev, idx, clock=commands.clock):
                return
            await commands.handle_pick(bot, ev, idx)

    return _sv
