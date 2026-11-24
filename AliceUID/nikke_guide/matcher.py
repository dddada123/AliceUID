"""Cross-language character alias & keyword matching for Blablalink guides."""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

from ..nikke_character.aliases import AliasStore
from ..nikke_character.builder import CharacterLookupError, resolve_character
from .registry import GUIDE_CATEGORIES, GuideAuthor
from .store import IndexedPost

# Supplemental EN <-> name_code fallback for EN-only guides when EN static table is absent.
EN_CHARACTER_FALLBACK: dict[int, tuple[str, ...]] = {
    5161: ('Snow White: Heavy Arms',),
    5166: ('E.H.',),
    5167: ('Arcana: Fortune Mate',),
    5184: ('Belorta: Pumpkin Witch',),
    5185: ('Marian: Queen',),
    5186: ('Scarlet: Goddeath',),
    5187: ('Rapunzel: Sanctuary',),
}


@lru_cache(maxsize=1)
def _t2s():
    try:
        from opencc import OpenCC
        return OpenCC('t2s').convert
    except ImportError:
        return lambda s: s


def norm_key(text: str) -> str:
    convert = _t2s()
    normalized = unicodedata.normalize('NFKC', convert(str(text or ''))).casefold()
    return ''.join(c for c in normalized if not c.isspace() and not unicodedata.category(c).startswith('P'))


def _is_chinese_lang(lang: str) -> bool:
    return str(lang or '').lower().startswith('zh')


def build_name_code_resolver(static, aliases: dict[str, int] | None = None):
    """Build a fast (subject, tags, title) -> name_code | None resolver for indexing."""
    by_norm: dict[str, int] = {}
    for code in static.characters:
        cid = int(code)
        k = norm_key(static.name(cid))
        if k:
            by_norm[k] = cid
        for en_name in EN_CHARACTER_FALLBACK.get(cid, ()):
            ek = norm_key(en_name)
            if ek:
                by_norm[ek] = cid
    if aliases:
        for alias, cid in aliases.items():
            ak = norm_key(alias)
            if ak and ak not in by_norm:
                by_norm[ak] = int(cid)

    def resolve(subject: str, tags: list[str], title: str) -> int | None:
        sk = norm_key(subject)
        if sk in by_norm:
            return by_norm[sk]
        for tag in tags:
            tk = norm_key(tag)
            if tk in by_norm:
                return by_norm[tk]
        # Fallback: substring match against official names (longest first to prefer alter variants)
        tk_title = norm_key(title)
        for k, cid in sorted(by_norm.items(), key=lambda kv: len(kv[0]), reverse=True):
            if len(k) >= 2 and k in tk_title:
                return cid
        return None

    return resolve


def rank_posts(posts: list[IndexedPost], authors_by_id: dict[str, GuideAuthor]) -> list[IndexedPost]:
    def key(p: IndexedPost):
        author = authors_by_id.get(p.author_id)
        prio = author.priority if author else 999
        lang_rank = 0 if _is_chinese_lang(p.original_language or p.language) else 1
        return (prio, lang_rank, -int(p.created_on))

    return sorted(posts, key=key)


def dedupe_recent_guides(posts: list[IndexedPost], *, limit: int = 10) -> list[IndexedPost]:
    """Deduplicate bilingual pairs (same character name_code or same day+category), preferring Chinese."""
    seen_keys: set[tuple] = set()
    out: list[IndexedPost] = []
    # Sort by created_on desc, Chinese first on ties
    ordered = sorted(
        posts,
        key=lambda p: (-int(p.created_on), 0 if _is_chinese_lang(p.original_language or p.language) else 1),
    )
    for p in ordered:
        if p.category == 'character' and p.name_code is not None:
            dkey = ('char', p.author_id, p.name_code)
        elif p.category in ('solo_raid', 'union_raid'):
            day_bucket = int(p.created_on) // 86400
            dkey = (p.category, p.author_id, day_bucket)
        else:
            dkey = ('uuid', p.post_uuid)
        if dkey in seen_keys:
            continue
        seen_keys.add(dkey)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def match_guides(
    query: str,
    *,
    store,
    static,
    alias_store: AliasStore | None,
    authors: list[GuideAuthor],
) -> tuple[str, list[IndexedPost]]:
    """Return ('single'|'multiple'|'none', matched_posts) for a user query."""
    clean = str(query or '').strip()
    if not clean:
        return 'none', []

    authors_by_id = {a.author_id: a for a in authors if a.include_in_keyword_search}
    enabled_ids = set(authors_by_id)
    aliases = alias_store.read(static=static) if alias_store is not None else {}

    # 1. Try character resolution via AliasStore + OpenCC + StaticData
    resolved_code: int | None = None
    try:
        resolved_code = resolve_character(clean, static, convert=_t2s(), aliases=aliases)
    except CharacterLookupError:
        resolved_code = None

    if resolved_code is not None:
        hits = [p for p in store.find_by_name_code(resolved_code) if p.author_id in enabled_ids]
        if hits:
            ranked = rank_posts(hits, authors_by_id)
            return 'single', [ranked[0]]
        # Fallback: check EN fallback names against tags/title in guide posts
        en_keys = [norm_key(n) for n in EN_CHARACTER_FALLBACK.get(resolved_code, ())]
        if en_keys:
            all_char_posts = [
                p for p in store.list_posts(categories=('character',), limit=500)
                if p.author_id in enabled_ids
            ]
            tag_hits = [
                p for p in all_char_posts
                if any(ek in norm_key(p.title) or any(ek == norm_key(t) for t in p.tags) for ek in en_keys)
            ]
            if tag_hits:
                ranked = rank_posts(tag_hits, authors_by_id)
                return 'single', [ranked[0]]

    # 2. General keyword / topic / raid guide search across guide categories
    qk = norm_key(clean)
    if not qk:
        return 'none', []
    candidates = [
        p for p in store.list_posts(categories=tuple(GUIDE_CATEGORIES), limit=500)
        if p.author_id in enabled_ids
    ]
    scored: list[tuple[int, IndexedPost]] = []
    for p in candidates:
        title_k = p.title_norm or norm_key(p.title)
        subj_k = norm_key(p.subject)
        tags_k = [norm_key(t) for t in p.tags]
        score = 0
        if qk == subj_k or qk == title_k:
            score = 100
        elif qk in subj_k:
            score = 80
        elif qk in title_k:
            score = 65
        elif any(qk in tk for tk in tags_k):
            score = 45
        if score > 0:
            if _is_chinese_lang(p.original_language or p.language):
                score += 10
            scored.append((score, p))

    if not scored:
        return 'none', []
    scored.sort(key=lambda item: (-item[0], -int(item[1].created_on)))
    top_score = scored[0][0]
    top_posts = [p for s, p in scored if s >= max(60, top_score - 15)]
    if len(top_posts) == 1:
        return 'single', top_posts
    # If all top posts are same topic/bilingual pair, pick best single; otherwise offer selection list
    deduped = dedupe_recent_guides(top_posts, limit=10)
    if len(deduped) == 1:
        return 'single', deduped
    return 'multiple', deduped
