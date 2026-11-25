"""Guide index orchestration, auto-translation, 30-day media cache, and delivery formatting."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

from ..nikke_character.aliases import AliasStore
from ..nikke_render.language import get_card_language
from ..nikke_render.theme import get_card_theme
from .draw import render_post_long_image, render_post_long_image_with_meta
from .matcher import (
    GuideMatchResult,
    build_name_code_resolver,
    dedupe_recent_guides,
    match_guides,
    match_guides_rich,
    norm_key,
)
from .registry import CATEGORY_LABELS, GUIDE_CATEGORIES, GuideAuthor, load_authors
from .source import (
    GuideError,
    PostNotFoundError,
    download_image_bytes,
    fetch_author_posts,
    fetch_post_detail,
    html_to_plain_text,
    split_text_chunks,
)
from .store import GuideStore, INDEX_RULES_VERSION, IndexedPost

_SYNC_LOCK = asyncio.Lock()
_POST_LOCKS: dict[str, asyncio.Lock] = {}
_BJ_TZ = timezone(timedelta(hours=8))

SYNC_COOLDOWN_SECONDS = 1800
LIST_CHECK_COOLDOWN_SECONDS = 60
ERROR_COOLDOWN_SECONDS = 300
MISSING_DELETE_SECONDS = 86400
EXPERIMENTAL_NOTICE = '※ 实验性功能：目前仅适配作者【在舒恩裡面卍解【Syuen】】的攻略特征'


def _log_event(stage: str, result: str, **metrics):
    try:
        from ..nikke_logs.store import event
        event('攻略查询', stage, result, **metrics)
    except Exception:
        pass


def _log_failure(stage: str, exc: BaseException):
    try:
        from ..nikke_logs.store import record_failure
        record_failure('攻略查询', stage, exc)
    except Exception:
        pass


@dataclass(frozen=True)
class GuideResult:
    post: IndexedPost
    author: GuideAuthor
    display_title: str
    lead_image: bytes | None
    long_image: bytes | None
    plain_text: str
    translated_from: str | None = None
    missing_count: int = 0

    def header_text(self) -> str:
        cat_label = CATEGORY_LABELS.get(self.post.category, '攻略')
        subject = self.post.subject or self.display_title
        tag = f'{subject}攻略' if self.post.category == 'character' else cat_label
        pub = datetime.fromtimestamp(self.post.created_on, _BJ_TZ).strftime('%Y-%m-%d') if self.post.created_on else '未知'
        lines = [
            f'[AliceUID·{tag}] 作者：{self.author.display_name} - {self.display_title}',
            f'分类：{cat_label} | 发布时间：{pub}',
        ]
        if self.translated_from:
            lines.append(f'语言说明：原文为 {self.translated_from.upper()}，已通过 Blablalink 官方自动翻译为中文')
        elif not str(self.post.original_language or '').lower().startswith('zh'):
            lines.append(f'语言说明：当前仅收录 {str(self.post.original_language or "外语").upper()} 原文版本')
        lines.append(f'原帖链接：{self.post.post_url}')
        lines.append(f'作者主页：{self.author.homepage_url}')
        lines.append(EXPERIMENTAL_NOTICE)
        if self.long_image is None:
            lines.append('※ 攻略长图生成超时，已降级发送原帖链接与纯文字版攻略')
        elif self.missing_count > 0:
            lines.append(f'※ 本次有 {self.missing_count} 张配图暂未加载成功，下次查询将自动尝试补全')
        return '\n'.join(lines)

    def plain_text_chunks(self) -> list[str]:
        footer = f'—— 攻略来源：{self.author.display_name}（{self.post.post_url}）'
        return split_text_chunks(self.plain_text, footer=footer, limit=2800)

    def forward_messages(self) -> list[str | bytes]:
        # Long image already embeds the lead image; send 3 parts: header -> long image -> plain text.
        msgs: list[str | bytes] = [self.header_text()]
        if self.long_image is not None:
            msgs.append(self.long_image)
        msgs.extend(self.plain_text_chunks())
        return msgs


def _post_lock(post_uuid: str) -> asyncio.Lock:
    lock = _POST_LOCKS.get(post_uuid)
    if lock is None:
        lock = asyncio.Lock()
        _POST_LOCKS[post_uuid] = lock
    return lock


class GuideService:
    def __init__(
        self,
        root: Path,
        *,
        static_loader=None,
        alias_store: AliasStore | None = None,
        authors_path: Path | None = None,
        post_fetcher=fetch_author_posts,
        detail_fetcher=fetch_post_detail,
        image_downloader=download_image_bytes,
        post_renderer=render_post_long_image,
        clock=time.time,
        quality: int = 95,
    ):
        self.store = GuideStore(root, clock=clock)
        self.static_loader = static_loader
        self.alias_store = alias_store
        self.authors_path = authors_path
        self.post_fetcher = post_fetcher
        self.detail_fetcher = detail_fetcher
        self.image_downloader = image_downloader
        self.post_renderer = post_renderer
        self.clock = clock
        self.quality = quality

    def _static(self):
        if self.static_loader is not None:
            return self.static_loader()
        from ..nikke_resource.service import get_resources
        return get_resources().load_static()

    def _aliases(self) -> AliasStore | None:
        if self.alias_store is not None:
            return self.alias_store
        try:
            from ..nikke_character.aliases import get_alias_store
            return get_alias_store()
        except Exception as exc:
            _log_failure('ALIAS_STORE', exc)
            return None

    def authors(self) -> list[GuideAuthor]:
        return load_authors(self.authors_path)

    def is_initialized(self) -> bool:
        authors = self.authors()
        if not authors:
            return True
        for author in authors:
            state = self.store.get_author_state(author.author_id)
            if not bool(state.get('full_backfill_done')):
                return False
        return True

    async def ensure_indexed(
        self,
        *,
        force: bool = False,
        on_first_index=None,
        cooldown_seconds: int = SYNC_COOLDOWN_SECONDS,
        allow_stale_on_error: bool = False,
    ) -> list[GuideAuthor]:
        """Ensure all enabled authors are indexed in SQLite; runs full backfill on first use."""
        authors = self.authors()
        async with _SYNC_LOCK:
            now = int(self.clock())
            static = self._static()
            aliases = self._aliases()
            alias_map = {}
            if aliases is not None:
                try:
                    alias_map = aliases.read(static=static)
                except Exception as exc:
                    _log_failure('ALIAS_READ', exc)
                    alias_map = {}
            resolver = build_name_code_resolver(static, alias_map)

            # One-time 0-network local reindex when matching rules upgrade (preserves all 30d media caches).
            if self.store.rules_version() != INDEX_RULES_VERSION:
                if self.store.count_posts() > 0:
                    authors_map = {a.author_id: a for a in authors}
                    stats = self.store.reindex_local(
                        norm_fn=norm_key,
                        name_code_resolver=resolver,
                        authors_by_id=authors_map,
                    )
                    _log_event(
                        'LOCAL_REINDEX',
                        'OK',
                        count=stats['total'],
                        reason=f"rules={INDEX_RULES_VERSION},updated={stats['updated']}",
                    )
                self.store.set_rules_version(INDEX_RULES_VERSION)

            first_run_notified = False
            for author in authors:
                state = self.store.get_author_state(author.author_id)
                backfill_done = bool(state.get('full_backfill_done'))
                last_sync = int(state.get('last_sync_at') or 0)
                retry_after = int(state.get('retry_after') or 0)
                if not force and backfill_done and (now - last_sync) < cooldown_seconds:
                    continue
                if not force and now < retry_after:
                    continue
                if not backfill_done and on_first_index is not None and not first_run_notified:
                    first_run_notified = True
                    await on_first_index(author)
                try:
                    known = self.store.known_modified_map(author.author_id)
                    raw_posts, reached_end = await self.post_fetcher(
                        author,
                        known_modified=known,
                        full_backfill=not backfill_done,
                    )
                    latest_name = author.display_name
                    for p in raw_posts:
                        uname = str((p.get('user') or {}).get('username') or '').strip()
                        if uname:
                            latest_name = uname
                            break
                    changed = self.store.upsert_posts(
                        author,
                        raw_posts,
                        norm_fn=norm_key,
                        name_code_resolver=resolver,
                    )
                    self.store.save_author_state(
                        author,
                        display_name=latest_name,
                        last_sync_at=now,
                        full_backfill_done=backfill_done or reached_end or bool(raw_posts),
                        retry_after=0,
                    )
                    _log_event(
                        'INDEX_SYNC',
                        'OK',
                        count=len(raw_posts),
                        reason=f'author={author.author_id},backfill={int(not backfill_done)},changed={len(changed)}',
                    )
                except Exception as exc:
                    _log_failure('INDEX_SYNC', exc)
                    self.store.save_author_state(
                        author,
                        retry_after=now + ERROR_COOLDOWN_SECONDS,
                    )
                    if not backfill_done and self.store.count_posts(author.author_id) == 0:
                        raise GuideError('首次拉取作者攻略索引失败，请稍后重试。') from None
                    if not allow_stale_on_error:
                        _log_event('INDEX_SYNC', 'DEGRADED', reason=f'author={author.author_id},keep_local=1')
        return authors

    async def recent_posts(
        self,
        *,
        filter_text: str = '',
        limit: int = 10,
        on_first_index=None,
    ) -> tuple[list[IndexedPost], dict[str, GuideAuthor]]:
        posts, _, _, authors_by_id = await self.recent_posts_paged(
            filter_text=filter_text,
            page=1,
            page_size=limit,
            on_first_index=on_first_index,
        )
        return posts, authors_by_id

    async def recent_posts_paged(
        self,
        *,
        filter_text: str = '',
        page: int = 1,
        page_size: int = 10,
        on_first_index=None,
    ) -> tuple[list[IndexedPost], int, int, dict[str, GuideAuthor]]:
        # `nk攻略查询` always performs a lightweight incremental check for newly published posts.
        authors = await self.ensure_indexed(
            on_first_index=on_first_index,
            cooldown_seconds=LIST_CHECK_COOLDOWN_SECONDS,
            allow_stale_on_error=True,
        )
        authors_by_id = {a.author_id: a for a in authors}
        clean = str(filter_text or '').strip()
        include_all = clean in ('全部', 'all', 'ALL')

        cat_filter = None
        if clean in ('角色', '角色攻略'):
            cat_filter = ('character',)
        elif clean in ('单突', '单人突袭'):
            cat_filter = ('solo_raid',)
        elif clean in ('会战', '联盟战', '联盟突袭'):
            cat_filter = ('union_raid',)
        elif clean in ('专题', '机制', '养成'):
            cat_filter = ('topic',)
        elif not include_all:
            cat_filter = tuple(GUIDE_CATEGORIES)

        # Optional author filter
        author_id = None
        for a in authors:
            if clean and clean.casefold() in {a.author_id.casefold(), *(al.casefold() for al in a.aliases)}:
                author_id = a.author_id
                cat_filter = tuple(GUIDE_CATEGORIES)
                break

        rows = self.store.list_posts(author_id=author_id, categories=cat_filter, limit=200)
        ordered = rows if include_all else dedupe_recent_guides(rows, limit=200)
        total_count = len(ordered)
        size = max(1, int(page_size))
        total_pages = max(1, (total_count + size - 1) // size)
        cur_page = max(1, int(page))
        start = (cur_page - 1) * size
        return ordered[start:start + size], total_count, total_pages, authors_by_id

    async def search(
        self,
        query: str,
        *,
        on_first_index=None,
    ) -> tuple[str, list[IndexedPost], dict[str, GuideAuthor]]:
        match_res, authors_by_id, _, _ = await self.search_rich(query, on_first_index=on_first_index)
        return match_res.status, match_res.posts, authors_by_id

    async def search_rich(
        self,
        query: str,
        *,
        on_first_index=None,
    ) -> tuple[GuideMatchResult, dict[str, GuideAuthor], dict[int, list[str]]]:
        authors = await self.ensure_indexed(on_first_index=on_first_index)
        authors_by_id = {a.author_id: a for a in authors}
        static = self._static()
        aliases_store = self._aliases()
        alias_by_code: dict[int, list[str]] = {}
        if aliases_store is not None:
            try:
                raw_aliases = aliases_store.read(static=static)
                for al, cid in raw_aliases.items():
                    alias_by_code.setdefault(int(cid), []).append(str(al))
            except Exception:
                alias_by_code = {}
        names_by_code = {int(c): static.name(c) for c in static.characters} if static is not None else {}
        res = match_guides_rich(
            query,
            store=self.store,
            static=static,
            alias_store=aliases_store,
            authors=authors,
        )
        return res, authors_by_id, alias_by_code, names_by_code

    def is_sync_running(self) -> bool:
        return _SYNC_LOCK.locked()

    async def reindex(self, *, clear: bool = False) -> dict[str, int]:
        """Bot-owner fallback: force full re-crawl across authors (optionally clearing local SQLite/media first)."""
        t0 = time.monotonic()
        cleared = 0
        async with _SYNC_LOCK:
            if clear:
                cleared = self.store.clear_all()
            else:
                self.store.reset_sync_state()

        await self.ensure_indexed(force=True)
        total = self.store.count_posts()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        _log_event('OWNER_REINDEX', 'OK', count=total, elapsed_ms=elapsed_ms, reason=f'clear={int(clear)},cleared={cleared}')
        return {'total': total, 'cleared': cleared, 'elapsed_ms': elapsed_ms}

    def _handle_post_unavailable(self, post: IndexedPost, *, now: int | None = None, exc: BaseException | None = None) -> GuideError:
        stamp = int(self.clock() if now is None else now)
        first_missing = self.store.mark_post_missing(post.post_uuid, now=stamp)
        elapsed = stamp - first_missing
        if elapsed >= MISSING_DELETE_SECONDS:
            self.store.delete_post(post.post_uuid)
            _log_event('DEAD_LINK', 'DELETED', elapsed_ms=elapsed * 1000, reason=f'uuid={post.post_uuid}')
            return GuideError('该攻略原帖已连续超过24小时无法访问，已从本地索引移除。')
        if exc is not None:
            _log_failure('DEAD_LINK_GRACE', exc)
        _log_event('DEAD_LINK', 'GRACE', elapsed_ms=max(0, elapsed) * 1000, reason=f'uuid={post.post_uuid}')
        return GuideError('该攻略暂时无法读取（可能是网络波动），已保留索引，请稍后再试。')

    async def render_or_get(
        self,
        post: IndexedPost,
        author: GuideAuthor,
        *,
        language: str | None = None,
        theme: str | None = None,
        on_rendering=None,
    ) -> GuideResult:
        lang = language or get_card_language()
        resolved_theme = get_card_theme(theme, default='random')

        async with _post_lock(post.post_uuid):
            now = int(self.clock())
            # If previously marked missing, re-verify live post before trusting cached media.
            if post.missing_since > 0:
                try:
                    probe = await self.detail_fetcher(
                        post.post_uuid,
                        target_lang=lang,
                        referer=post.post_url,
                    )
                except Exception as exc:
                    raise self._handle_post_unavailable(post, now=now, exc=exc) from None
                if not probe:
                    raise self._handle_post_unavailable(post, now=now)
                self.store.clear_post_missing(post.post_uuid)

            cached = self.store.read_media(post.post_uuid, post.modified_on, lang, resolved_theme)
            if cached is not None:
                return GuideResult(
                    post=post,
                    author=author,
                    display_title=cached['display_title'] or post.title,
                    lead_image=cached['lead'],
                    long_image=cached['long_image'],
                    plain_text=cached['plain_text'],
                    translated_from=cached['translated_from'],
                    missing_count=int(cached.get('missing_count') or 0),
                )

            if on_rendering is not None:
                await on_rendering(post)

            display_title = post.title
            content_html = post.content_html
            translated_from: str | None = None

            # Auto-translate non-Chinese original posts via Blablalink anonymous GetPost
            if not str(post.original_language or '').lower().startswith('zh'):
                try:
                    detail = await self.detail_fetcher(
                        post.post_uuid,
                        target_lang=lang,
                        referer=post.post_url,
                    )
                except PostNotFoundError as exc:
                    raise self._handle_post_unavailable(post, now=now, exc=exc) from None
                except GuideError as exc:
                    raise self._handle_post_unavailable(post, now=now, exc=exc) from None
                except Exception as exc:
                    raise self._handle_post_unavailable(post, now=now, exc=exc) from None
                if detail and str(detail.get('language') or '').lower().startswith('zh'):
                    display_title = str(detail.get('title') or display_title).strip()
                    content_html = str(detail.get('content') or content_html)
                    translated_from = post.original_language or 'en'

            render_payload = {
                'post_uuid': post.post_uuid,
                'title': display_title,
                'content': content_html,
                'created_on': post.created_on,
            }
            cat_label = CATEGORY_LABELS.get(post.category, '攻略')
            plain_text = html_to_plain_text(content_html, has_lead_image=bool(post.lead_image_url))

            failed_urls: list[str] = []
            try:
                if self.post_renderer is render_post_long_image:
                    long_image, failed_urls = await render_post_long_image_with_meta(
                        render_payload,
                        author_name=author.display_name,
                        category_label=cat_label,
                        post_url=post.post_url,
                        quality=self.quality,
                        theme=resolved_theme,
                        language=lang,
                        translated_from=translated_from,
                        image_cache_dir=self.store.image_cache_dir(post.post_uuid),
                    )
                else:
                    rendered = await self.post_renderer(
                        render_payload,
                        author_name=author.display_name,
                        category_label=cat_label,
                        post_url=post.post_url,
                        quality=self.quality,
                        theme=resolved_theme,
                        language=lang,
                        translated_from=translated_from,
                    )
                    if isinstance(rendered, tuple):
                        long_image, failed_urls = rendered[0], list(rendered[1] or ())
                    else:
                        long_image = rendered
            except TimeoutError as exc:
                _log_failure('RENDER_TIMEOUT', exc)
                _log_event('TAKUMI_RENDER', 'TIMEOUT', reason=f'uuid={post.post_uuid}')
                return GuideResult(
                    post=post,
                    author=author,
                    display_title=display_title,
                    lead_image=None,
                    long_image=None,
                    plain_text=plain_text,
                    translated_from=translated_from,
                )

            self.store.write_media(
                post.post_uuid,
                post.modified_on,
                lang,
                resolved_theme,
                lead_bytes=None,
                long_image=long_image,
                plain_text=plain_text,
                display_title=display_title,
                translated_from=translated_from,
                failed_urls=failed_urls,
            )
            return GuideResult(
                post=post,
                author=author,
                display_title=display_title,
                lead_image=None,
                long_image=long_image,
                plain_text=plain_text,
                translated_from=translated_from,
                missing_count=len(failed_urls),
            )


def get_guide_service() -> GuideService:
    from ..nikke_config.config import AliceUIDConfig, CACHE_PATH, DATA_PATH
    try:
        quality = int(AliceUIDConfig.get_config('AliceUID_ForwardJpegQuality').data or 95)
    except Exception:
        quality = 95
    extra_authors = DATA_PATH / 'guide_authors.json'
    return GuideService(
        CACHE_PATH / 'guide_hub',
        authors_path=extra_authors,
        quality=quality,
    )
