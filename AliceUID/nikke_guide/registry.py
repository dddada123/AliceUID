"""Extensible Blablalink guide author registry and post classification rules."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

CATEGORY_LABELS: dict[str, str] = {
    'character': '角色攻略',
    'solo_raid': '单人突袭',
    'union_raid': '联盟突袭',
    'topic': '机制/专题攻略',
    'recruit': '联盟招募',
    'misc': '日常动态',
}

GUIDE_CATEGORIES = frozenset({'character', 'solo_raid', 'union_raid', 'topic'})


@dataclass(frozen=True)
class CategoryRule:
    category: str
    patterns: tuple[str, ...] = ()
    tag_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuideAuthor:
    author_id: str
    intl_openid: str
    display_name: str
    homepage_url: str
    aliases: tuple[str, ...] = ()
    priority: int = 100
    enabled: bool = True
    language_preference: tuple[str, ...] = ('zh-TW', 'zh-CN', 'en')
    category_rules: tuple[CategoryRule, ...] = ()
    lead_image_mode: str = 'first_static'
    include_in_keyword_search: bool = True


DEFAULT_CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        category='character',
        patterns=(r'袖珍指南', r'pocket\s+guide'),
    ),
    CategoryRule(
        category='union_raid',
        patterns=(r'(?:聯|联)盟(?:戰|战|突襲|突袭)', r'[公工](?:會|会)(?:戰|战)', r'union\s+raid'),
        tag_patterns=(r'^union\s+raid$',),
    ),
    CategoryRule(
        category='solo_raid',
        patterns=(r'(?:單|单)人突(?:襲|袭)', r'(?:單|单)突', r'solo\s*raid', r'\bsolo\s*#?\d+'),
        tag_patterns=(r'^solo\s+raid$',),
    ),
    CategoryRule(
        category='recruit',
        patterns=(r'招\s*\d+\s*人', r'(?:聯|联)盟招(?:募|人)', r'union\s+recruitment'),
        tag_patterns=(r'union\s+recruitment',),
    ),
    CategoryRule(
        category='topic',
        patterns=(
            r'魔方', r'攻略', r'(?:機|机)制', r'\bpvp\b', r'超(?:頻|频)',
            r'overclock', r'\bguide\b', r'推(?:薦|荐)', r'母(?:鯨|鲸)', r'排球',
        ),
    ),
)

SYUEN_AUTHOR = GuideAuthor(
    author_id='syuen',
    intl_openid='29080-6355534029721844438',
    display_name='在舒恩裡面卍解【Syuen】',
    homepage_url='https://www.blablalink.com/user?openid=MjkwODAtNjM1NTUzNDAyOTcyMTg0NDQzOA==',
    aliases=('syuen', '舒恩', '卍解', '在舒恩裡面卍解', '在舒恩里面卍解'),
    priority=10,
    enabled=True,
    language_preference=('zh-TW', 'zh-CN', 'en'),
    category_rules=(),
    lead_image_mode='first_static',
    include_in_keyword_search=True,
)

BUILTIN_AUTHORS: tuple[GuideAuthor, ...] = (SYUEN_AUTHOR,)


def decode_openid_from_url(homepage_url: str) -> str:
    """Decode base64 `openid=` query parameter from a Blablalink user URL."""
    qs = parse_qs(urlsplit(str(homepage_url or '')).query)
    raw = (qs.get('openid') or [''])[0].strip()
    if not raw:
        return ''
    padded = raw + '=' * (-len(raw) % 4)
    try:
        return base64.b64decode(padded.encode('ascii')).decode('utf-8').strip()
    except Exception:
        return ''


def _coerce_author(raw: dict) -> GuideAuthor | None:
    if not isinstance(raw, dict):
        return None
    author_id = str(raw.get('author_id') or '').strip().lower()
    homepage_url = str(raw.get('homepage_url') or '').strip()
    intl_openid = str(raw.get('intl_openid') or '').strip() or decode_openid_from_url(homepage_url)
    display_name = str(raw.get('display_name') or author_id).strip()
    if not author_id or not intl_openid:
        return None
    if not homepage_url:
        encoded = base64.b64encode(intl_openid.encode('utf-8')).decode('ascii')
        homepage_url = f'https://www.blablalink.com/user?openid={encoded}'
    rules = tuple(
        CategoryRule(
            category=str(r.get('category') or 'topic'),
            patterns=tuple(str(p) for p in (r.get('patterns') or ()) if p),
            tag_patterns=tuple(str(p) for p in (r.get('tag_patterns') or ()) if p),
        )
        for r in (raw.get('category_rules') or ())
        if isinstance(r, dict)
    )
    return GuideAuthor(
        author_id=author_id,
        intl_openid=intl_openid,
        display_name=display_name,
        homepage_url=homepage_url,
        aliases=tuple(str(a).strip() for a in (raw.get('aliases') or ()) if str(a).strip()),
        priority=int(raw.get('priority', 100)),
        enabled=bool(raw.get('enabled', True)),
        language_preference=tuple(raw.get('language_preference') or ('zh-TW', 'zh-CN', 'en')),
        category_rules=rules,
        lead_image_mode=str(raw.get('lead_image_mode') or 'first_static'),
        include_in_keyword_search=bool(raw.get('include_in_keyword_search', True)),
    )


def load_authors(extra_path: Path | None = None) -> list[GuideAuthor]:
    """Return enabled authors ordered by priority; merges optional JSON extensions."""
    merged: dict[str, GuideAuthor] = {a.author_id: a for a in BUILTIN_AUTHORS}
    if extra_path is not None and Path(extra_path).is_file():
        try:
            payload = json.loads(Path(extra_path).read_text('utf-8'))
            rows = payload.get('authors') if isinstance(payload, dict) else payload
            if isinstance(rows, list):
                for row in rows:
                    parsed = _coerce_author(row)
                    if parsed is not None:
                        merged[parsed.author_id] = parsed
        except (OSError, ValueError, TypeError):
            pass
    return sorted((a for a in merged.values() if a.enabled), key=lambda a: (a.priority, a.author_id))


def extract_character_subject(title: str) -> str:
    """Extract character name from titles like `【紅蓮：弒神】袖珍指南` or `伊萊格：BOOM與驚嚇 袖珍指南`."""
    text = str(title or '').strip()
    m = re.search(r'【([^】]+)】', text)
    if m:
        return m.group(1).strip()
    cleaned = re.sub(r'\((?:updated|更新)[^)]*\)|（[^）]*更新[^）]*）', '', text, flags=re.I).strip()
    cleaned = re.sub(r'(?:袖珍指南|pocket\s+guide).*$', '', cleaned, flags=re.I).strip()
    return cleaned.strip(' -—:：')


def extract_post_tags(post: dict) -> list[str]:
    tags = post.get('tags') or post.get('topic_list') or []
    out: list[str] = []
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict):
                name = str(item.get('name') or item.get('topic_name') or '').strip()
            else:
                name = str(item or '').strip()
            if name and name not in out:
                out.append(name)
    return out


def classify_post(post: dict, author: GuideAuthor | None = None) -> tuple[str, str]:
    """Classify a Blablalink post into (category, subject)."""
    title = str(post.get('title') or '').strip()
    tags = extract_post_tags(post)
    rules = tuple(author.category_rules if author else ()) + DEFAULT_CATEGORY_RULES

    matched_cat = 'misc'
    for rule in rules:
        if any(re.search(pat, title, re.I) for pat in rule.patterns):
            matched_cat = rule.category
            break
        if rule.tag_patterns and any(
            re.search(pat, tag, re.I) for pat in rule.tag_patterns for tag in tags
        ):
            matched_cat = rule.category
            break

    if matched_cat == 'character':
        return matched_cat, extract_character_subject(title)
    return matched_cat, title
