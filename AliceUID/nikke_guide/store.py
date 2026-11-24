"""Persistent SQLite post index + 30-day TTL local media cache."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

from ..nikke_resource.cache import atomic_write
from .registry import GuideAuthor, classify_post, extract_post_tags
from .source import POST_URL, extract_lead_image_url, validate_image_bytes

MEDIA_TTL_SECONDS = 30 * 86400
GUIDE_STYLE_VERSION = 'v1307-header-concentric'
INDEX_RULES_VERSION = 'v1308-exact-alias'
INCOMPLETE_RETRY_SECONDS = 60


@dataclass(frozen=True)
class IndexedPost:
    post_uuid: str
    author_id: str
    title: str
    title_norm: str
    language: str
    original_language: str
    plate_id: int
    tags: tuple[str, ...]
    category: str
    subject: str
    name_code: int | None
    post_url: str
    lead_image_url: str | None
    created_on: int
    modified_on: int
    content_html: str
    indexed_at: int
    missing_since: int = 0


class GuideStore:
    def __init__(self, root: Path, *, clock=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'index.sqlite3'
        self.meta_path = self.root / 'index_meta.json'
        self.media_root = self.root / 'media'
        self.clock = clock
        self._init_db()

    def rules_version(self) -> str:
        try:
            data = json.loads(self.meta_path.read_text('utf-8'))
            return str(data.get('rules_version') or '') if isinstance(data, dict) else ''
        except Exception:
            return ''

    def set_rules_version(self, ver: str):
        payload = {'rules_version': str(ver), 'updated_at': int(self.clock())}
        atomic_write(self.meta_path, json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    def reindex_local(self, *, norm_fn, name_code_resolver, authors_by_id: dict[str, GuideAuthor]) -> dict[str, int]:
        """Recompute title_norm/category/subject/name_code across all cached posts with 0 network I/O."""
        total = 0
        updated = 0
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM posts').fetchall()
            for r in rows:
                total += 1
                uid = str(r['post_uuid'])
                aid = str(r['author_id'])
                author = authors_by_id.get(aid)
                if author is None:
                    continue
                tags = json.loads(r['tags_json'] or '[]')
                raw_post = {
                    'post_uuid': uid,
                    'title': str(r['title'] or ''),
                    'tags': tags,
                }
                category, subject = classify_post(raw_post, author)
                name_code = name_code_resolver(subject, tags, raw_post['title']) if category == 'character' else None
                title_norm = norm_fn(raw_post['title'])
                if (
                    category != str(r['category'])
                    or subject != str(r['subject'])
                    or name_code != (int(r['name_code']) if r['name_code'] is not None else None)
                    or title_norm != str(r['title_norm'])
                ):
                    conn.execute(
                        'UPDATE posts SET title_norm = ?, category = ?, subject = ?, name_code = ? WHERE post_uuid = ?',
                        (title_norm, category, subject, name_code, uid),
                    )
                    updated += 1
        return {'total': total, 'updated': updated}

    def reset_sync_state(self):
        with self._connect() as conn:
            conn.execute('UPDATE authors SET full_backfill_done = 0, last_sync_at = 0, retry_after = 0')

    def clear_all(self) -> int:
        with self._connect() as conn:
            cur = conn.execute('SELECT COUNT(*) AS c FROM posts').fetchone()
            removed = int(cur['c']) if cur else 0
            conn.executescript('DELETE FROM posts; DELETE FROM authors; DELETE FROM media_cache;')
        shutil.rmtree(self.media_root, ignore_errors=True)
        self.meta_path.unlink(missing_ok=True)
        return removed

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS authors (
                    author_id TEXT PRIMARY KEY,
                    intl_openid TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    homepage_url TEXT NOT NULL,
                    last_sync_at INTEGER NOT NULL DEFAULT 0,
                    full_backfill_done INTEGER NOT NULL DEFAULT 0,
                    retry_after INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS posts (
                    post_uuid TEXT PRIMARY KEY,
                    author_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    title_norm TEXT NOT NULL,
                    language TEXT NOT NULL,
                    original_language TEXT NOT NULL,
                    plate_id INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    name_code INTEGER,
                    post_url TEXT NOT NULL,
                    lead_image_url TEXT,
                    created_on INTEGER NOT NULL,
                    modified_on INTEGER NOT NULL,
                    content_html TEXT NOT NULL,
                    indexed_at INTEGER NOT NULL,
                    missing_since INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_posts_author_created
                    ON posts(author_id, created_on DESC);
                CREATE INDEX IF NOT EXISTS idx_posts_name_code
                    ON posts(name_code);
                CREATE INDEX IF NOT EXISTS idx_posts_category
                    ON posts(category, created_on DESC);
                CREATE TABLE IF NOT EXISTS media_cache (
                    cache_key TEXT PRIMARY KEY,
                    post_uuid TEXT NOT NULL,
                    modified_on INTEGER NOT NULL,
                    lang TEXT NOT NULL,
                    cached_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                """
            )
            cols = {str(r['name']) for r in conn.execute('PRAGMA table_info(posts)').fetchall()}
            if 'missing_since' not in cols:
                conn.execute('ALTER TABLE posts ADD COLUMN missing_since INTEGER NOT NULL DEFAULT 0')

    def get_author_state(self, author_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM authors WHERE author_id = ?', (author_id,)).fetchone()
            return dict(row) if row else {}

    def save_author_state(
        self,
        author: GuideAuthor,
        *,
        display_name: str | None = None,
        last_sync_at: int | None = None,
        full_backfill_done: bool | None = None,
        retry_after: int | None = None,
    ):
        existing = self.get_author_state(author.author_id)
        name = display_name or existing.get('display_name') or author.display_name
        sync_at = int(last_sync_at if last_sync_at is not None else existing.get('last_sync_at', 0))
        backfill = int(full_backfill_done if full_backfill_done is not None else existing.get('full_backfill_done', 0))
        retry = int(retry_after if retry_after is not None else existing.get('retry_after', 0))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO authors(author_id, intl_openid, display_name, homepage_url, last_sync_at, full_backfill_done, retry_after)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(author_id) DO UPDATE SET
                    intl_openid = excluded.intl_openid,
                    display_name = excluded.display_name,
                    homepage_url = excluded.homepage_url,
                    last_sync_at = excluded.last_sync_at,
                    full_backfill_done = excluded.full_backfill_done,
                    retry_after = excluded.retry_after
                """,
                (author.author_id, author.intl_openid, name, author.homepage_url, sync_at, backfill, retry),
            )

    def known_modified_map(self, author_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT post_uuid, modified_on FROM posts WHERE author_id = ?',
                (author_id,),
            ).fetchall()
            return {str(r['post_uuid']): int(r['modified_on']) for r in rows}

    def upsert_posts(
        self,
        author: GuideAuthor,
        raw_posts: list[dict],
        *,
        norm_fn,
        name_code_resolver,
    ) -> list[str]:
        """Insert or update posts in persistent SQLite; returns list of post_uuids whose content changed."""
        now = int(self.clock())
        existing_mods = self.known_modified_map(author.author_id)
        changed_uuids: list[str] = []
        with self._connect() as conn:
            for p in raw_posts:
                uid = str(p.get('post_uuid') or '').strip()
                if not uid:
                    continue
                created_on = int(p.get('created_on') or 0)
                modified_on = int(p.get('modified_on') or created_on or 0)
                if uid in existing_mods and existing_mods[uid] == modified_on:
                    # Skip unchanged existing posts without re-parsing; clear transient missing flag if re-listed.
                    conn.execute(
                        'UPDATE posts SET missing_since = 0 WHERE post_uuid = ? AND missing_since != 0',
                        (uid,),
                    )
                    continue
                title = str(p.get('title') or '').strip()
                content = str(p.get('content') or '')
                lang = str(p.get('language') or 'zh-TW').strip()
                orig_lang = str(p.get('original_language') or lang).strip()
                plate_id = int(p.get('plate_id') or 0)
                tags = extract_post_tags(p)
                category, subject = classify_post(p, author)
                name_code = name_code_resolver(subject, tags, title) if category == 'character' else None
                lead_url = extract_lead_image_url(content, category=category)
                title_norm = norm_fn(title)
                if uid in existing_mods and existing_mods[uid] != modified_on:
                    changed_uuids.append(uid)
                conn.execute(
                    """
                    INSERT INTO posts(
                        post_uuid, author_id, title, title_norm, language, original_language,
                        plate_id, tags_json, category, subject, name_code, post_url,
                        lead_image_url, created_on, modified_on, content_html, indexed_at, missing_since
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(post_uuid) DO UPDATE SET
                        author_id = excluded.author_id,
                        title = excluded.title,
                        title_norm = excluded.title_norm,
                        language = excluded.language,
                        original_language = excluded.original_language,
                        plate_id = excluded.plate_id,
                        tags_json = excluded.tags_json,
                        category = excluded.category,
                        subject = excluded.subject,
                        name_code = excluded.name_code,
                        post_url = excluded.post_url,
                        lead_image_url = excluded.lead_image_url,
                        created_on = excluded.created_on,
                        modified_on = excluded.modified_on,
                        content_html = excluded.content_html,
                        indexed_at = excluded.indexed_at,
                        missing_since = 0
                    """,
                    (
                        uid, author.author_id, title, title_norm, lang, orig_lang,
                        plate_id, json.dumps(tags, ensure_ascii=False), category, subject,
                        name_code, f'{POST_URL}{uid}', lead_url, created_on, modified_on,
                        content, now,
                    ),
                )
        for uid in changed_uuids:
            self.invalidate_post_media(uid)
        return changed_uuids

    def _row_to_post(self, row: sqlite3.Row) -> IndexedPost:
        return IndexedPost(
            post_uuid=str(row['post_uuid']),
            author_id=str(row['author_id']),
            title=str(row['title']),
            title_norm=str(row['title_norm']),
            language=str(row['language']),
            original_language=str(row['original_language']),
            plate_id=int(row['plate_id']),
            tags=tuple(json.loads(row['tags_json'] or '[]')),
            category=str(row['category']),
            subject=str(row['subject']),
            name_code=int(row['name_code']) if row['name_code'] is not None else None,
            post_url=str(row['post_url']),
            lead_image_url=row['lead_image_url'],
            created_on=int(row['created_on']),
            modified_on=int(row['modified_on']),
            content_html=str(row['content_html']),
            indexed_at=int(row['indexed_at']),
            missing_since=int(row['missing_since']) if 'missing_since' in row.keys() and row['missing_since'] is not None else 0,
        )

    def list_posts(
        self,
        *,
        author_id: str | None = None,
        categories: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[IndexedPost]:
        clauses: list[str] = []
        params: list = []
        if author_id:
            clauses.append('author_id = ?')
            params.append(author_id)
        if categories:
            placeholders = ','.join('?' for _ in categories)
            clauses.append(f'category IN ({placeholders})')
            params.extend(categories)
        where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        sql = f'SELECT * FROM posts {where} ORDER BY created_on DESC LIMIT ?'
        params.append(int(limit))
        with self._connect() as conn:
            return [self._row_to_post(r) for r in conn.execute(sql, params).fetchall()]

    def find_by_name_code(self, name_code: int) -> list[IndexedPost]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM posts WHERE name_code = ? ORDER BY created_on DESC',
                (int(name_code),),
            ).fetchall()
            return [self._row_to_post(r) for r in rows]

    def get_post(self, post_uuid: str) -> IndexedPost | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM posts WHERE post_uuid = ?', (str(post_uuid),)).fetchone()
            return self._row_to_post(row) if row else None

    def count_posts(self, author_id: str | None = None) -> int:
        with self._connect() as conn:
            if author_id:
                row = conn.execute('SELECT COUNT(*) AS c FROM posts WHERE author_id = ?', (author_id,)).fetchone()
            else:
                row = conn.execute('SELECT COUNT(*) AS c FROM posts').fetchone()
            return int(row['c']) if row else 0

    def mark_post_missing(self, post_uuid: str, *, now: int | None = None) -> int:
        """Record first failure timestamp for a dead/unreachable post without deleting immediately."""
        stamp = int(self.clock() if now is None else now)
        uid = str(post_uuid)
        with self._connect() as conn:
            row = conn.execute('SELECT missing_since FROM posts WHERE post_uuid = ?', (uid,)).fetchone()
            if not row:
                return stamp
            existing = int(row['missing_since'] or 0)
            if existing > 0:
                return existing
            conn.execute('UPDATE posts SET missing_since = ? WHERE post_uuid = ?', (stamp, uid))
            return stamp

    def clear_post_missing(self, post_uuid: str):
        with self._connect() as conn:
            conn.execute('UPDATE posts SET missing_since = 0 WHERE post_uuid = ? AND missing_since != 0', (str(post_uuid),))

    def delete_post(self, post_uuid: str) -> bool:
        uid = str(post_uuid)
        self.invalidate_post_media(uid)
        with self._connect() as conn:
            cur = conn.execute('DELETE FROM posts WHERE post_uuid = ?', (uid,))
            return cur.rowcount > 0

    def _cache_dir(self, cache_key: str) -> Path:
        return self.media_root / cache_key

    def image_cache_dir(self, post_uuid: str) -> Path:
        return self.media_root / f'{post_uuid}_imgs'

    def invalidate_post_media(self, post_uuid: str):
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT cache_key FROM media_cache WHERE post_uuid = ?',
                (str(post_uuid),),
            ).fetchall()
            conn.execute('DELETE FROM media_cache WHERE post_uuid = ?', (str(post_uuid),))
        for r in rows:
            shutil.rmtree(self._cache_dir(str(r['cache_key'])), ignore_errors=True)
        shutil.rmtree(self.image_cache_dir(str(post_uuid)), ignore_errors=True)

    def cleanup_expired_media(self) -> int:
        """Delete media files older than 30 days while keeping the SQLite post index intact."""
        now = int(self.clock())
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT cache_key FROM media_cache WHERE expires_at <= ?',
                (now,),
            ).fetchall()
            conn.execute('DELETE FROM media_cache WHERE expires_at <= ?', (now,))
        removed = 0
        for r in rows:
            d = self._cache_dir(str(r['cache_key']))
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        return removed

    def read_media(self, post_uuid: str, modified_on: int, lang: str, theme: str) -> dict | None:
        self.cleanup_expired_media()
        cache_key = f'{post_uuid}_{lang}_{theme}'
        cdir = self._cache_dir(cache_key)
        meta_path = cdir / 'meta.json'
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text('utf-8'))
            now = int(self.clock())
            if meta.get('modified_on') != modified_on or meta.get('expires_at', 0) <= now:
                return None
            if meta.get('style_version') != GUIDE_STYLE_VERSION:
                return None
            complete = bool(meta.get('complete', True))
            retry_after = int(meta.get('retry_after') or 0)
            if not complete and now >= retry_after:
                # Incomplete render cooldown expired: force incremental re-fetch of missing images.
                return None
            long_bytes = (cdir / 'long.jpg').read_bytes()
            validate_image_bytes(long_bytes)
            if hashlib.sha256(long_bytes).hexdigest() != meta.get('long_sha256'):
                return None
            lead_bytes = None
            if meta.get('has_lead'):
                lead_bytes = (cdir / 'lead.img').read_bytes()
                validate_image_bytes(lead_bytes)
                if hashlib.sha256(lead_bytes).hexdigest() != meta.get('lead_sha256'):
                    return None
            plain_text = (cdir / 'plain.txt').read_text('utf-8')
            return {
                'lead': lead_bytes,
                'long_image': long_bytes,
                'plain_text': plain_text,
                'display_title': str(meta.get('display_title') or ''),
                'translated_from': meta.get('translated_from'),
                'complete': complete,
                'missing_count': int(meta.get('missing_count') or 0),
                'failed_urls': list(meta.get('failed_urls') or []),
            }
        except (OSError, ValueError, TypeError, Exception):
            return None

    def write_media(
        self,
        post_uuid: str,
        modified_on: int,
        lang: str,
        theme: str,
        *,
        lead_bytes: bytes | None,
        long_image: bytes,
        plain_text: str,
        display_title: str,
        translated_from: str | None = None,
        failed_urls: list[str] | tuple[str, ...] = (),
    ):
        now = int(self.clock())
        expires_at = now + MEDIA_TTL_SECONDS
        cache_key = f'{post_uuid}_{lang}_{theme}'
        cdir = self._cache_dir(cache_key)
        cdir.mkdir(parents=True, exist_ok=True)
        atomic_write(cdir / 'long.jpg', long_image)
        if lead_bytes is not None:
            atomic_write(cdir / 'lead.img', lead_bytes)
        atomic_write(cdir / 'plain.txt', plain_text.encode('utf-8'))
        failed_list = list(failed_urls or ())
        complete = len(failed_list) == 0
        meta = {
            'style_version': GUIDE_STYLE_VERSION,
            'post_uuid': str(post_uuid),
            'modified_on': int(modified_on),
            'lang': lang,
            'theme': theme,
            'display_title': display_title,
            'translated_from': translated_from,
            'complete': complete,
            'missing_count': len(failed_list),
            'failed_urls': failed_list,
            'retry_after': 0 if complete else (now + INCOMPLETE_RETRY_SECONDS),
            'has_lead': lead_bytes is not None,
            'lead_sha256': hashlib.sha256(lead_bytes).hexdigest() if lead_bytes is not None else None,
            'long_sha256': hashlib.sha256(long_image).hexdigest(),
            'cached_at': now,
            'expires_at': expires_at,
        }
        atomic_write(cdir / 'meta.json', json.dumps(meta, ensure_ascii=False).encode('utf-8'))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO media_cache(cache_key, post_uuid, modified_on, lang, cached_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    modified_on = excluded.modified_on,
                    lang = excluded.lang,
                    cached_at = excluded.cached_at,
                    expires_at = excluded.expires_at
                """,
                (cache_key, str(post_uuid), int(modified_on), lang, now, expires_at),
            )
