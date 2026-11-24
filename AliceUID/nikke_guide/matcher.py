"""Cross-language character alias & keyword matching for Blablalink guides."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import unicodedata

from ..nikke_character.aliases import AliasStore
from ..nikke_character.builder import CharacterAmbiguous, CharacterLookupError, CharacterNotFound, resolve_character
from .registry import GUIDE_CATEGORIES, GuideAuthor
from .store import IndexedPost

# Supplemental EN <-> name_code fallback for EN-only guides when EN static table is absent.
EN_CHARACTER_FALLBACK: dict[int, tuple[str, ...]] = {
    5105: ('Scarlet: Black Shadow',),
    5124: ('Cinderella',),
    5161: ('Snow White: Heavy Arms',),
    5166: ('E.H.',),
    5167: ('Arcana: Fortune Mate',),
    5175: ('Cinderella: Glass Gleam',),
    5184: ('Belorta: Pumpkin Witch',),
    5185: ('Marian: Queen',),
    5186: ('Scarlet: Goddeath',),
    5187: ('Rapunzel: Sanctuary',),
}


@dataclass(frozen=True)
class GuideMatchResult:
    status: str  # 'single' | 'multiple' | 'suggest' | 'none'
    posts: list[IndexedPost] = field(default_factory=list)
    resolved_code: int | None = None
    resolved_name: str = ''
    resolved_label: str = ''
    missing_reason: str = ''


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


def split_character_name(name: str) -> tuple[str, str]:
    """Split `灰姑娘：琉璃波光` or `Red Hood: Nonsense` on full/half-width colon."""
    text = str(name or '').strip()
    for sep in ('：', ':'):
        if sep in text:
            base, sub = text.split(sep, 1)
            return base.strip(), sub.strip()
    return text, ''


def _has_colon_subtitle(text: str) -> bool:
    base, sub = split_character_name(text)
    return bool(base and sub)


def _is_chinese_lang(lang: str) -> bool:
    return str(lang or '').lower().startswith('zh')


def _char_aliases_map(static, aliases: dict[str, int] | None) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    if not aliases:
        return grouped
    for alias, cid in aliases.items():
        code = int(cid)
        grouped.setdefault(code, []).append(str(alias))
    return grouped


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
        # Prevent unknown alter characters with colon subtitles (e.g. `灰姑娘：未录入形态`)
        # from being misbound to base character `灰姑娘` via substring fallback.
        if _has_colon_subtitle(subject):
            return None
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


def _post_exact_text_matches_character(
    post: IndexedPost,
    *,
    official_name: str,
    static,
    resolved_code: int,
) -> bool:
    """Check if a post (even one tagged as `topic`) refers to this exact character (colon/space/word-order agnostic)."""
    off_k = norm_key(official_name)
    if not off_k:
        return False
    base_name, sub_name = split_character_name(official_name)
    base_k = norm_key(base_name)
    sub_k = norm_key(sub_name)

    subj_k = norm_key(post.subject)
    title_k = post.title_norm or norm_key(post.title)
    tags_k = [norm_key(t) for t in post.tags]

    # Collect longer alter variants sharing the same base name so base character `灰姑娘`
    # does NOT match a `灰姑娘琉璃波光` text string via prefix overlap.
    longer_alter_keys: list[str] = []
    if not sub_k and static is not None:
        for cid in static.characters:
            if int(cid) == int(resolved_code):
                continue
            cname = static.name(cid)
            cb, cs = split_character_name(cname)
            if norm_key(cb) == base_k and cs:
                ck = norm_key(cname)
                if ck and ck != off_k:
                    longer_alter_keys.append(ck)

    def _matches_text(tk: str) -> bool:
        if not tk:
            return False
        if not sub_k:
            # Base character: exact subject/tag match or substring NOT inside a longer alter name
            if tk == off_k:
                return True
            stripped = tk
            for alt in longer_alter_keys:
                stripped = stripped.replace(alt, ' ')
            return off_k in stripped and not _has_colon_subtitle(post.subject)
        # Alter character (`灰姑娘：琉璃波光` or `紅蓮：暗影`):
        # 1) colon/space agnostic (`灰姑娘琉璃波光` or `红莲暗影`)
        if off_k in tk:
            return True
        # 2) word-order tolerant (`暗影红莲`, `琉璃波光灰姑娘`) when both base & sub appear
        if base_k and sub_k and len(base_k) >= 2 and len(sub_k) >= 2:
            if base_k in tk and sub_k in tk:
                return True
        return False

    return _matches_text(subj_k) or _matches_text(title_k) or any(_matches_text(t) for t in tags_k)


def _find_related_base_posts(
    *,
    base_name: str,
    exclude_code: int | None,
    candidates: list[IndexedPost],
    static,
    authors_by_id: dict[str, GuideAuthor],
) -> list[IndexedPost]:
    """Find guides sharing the same base character name (e.g. `灰姑娘` -> `灰姑娘：琉璃波光`)."""
    base_k = norm_key(base_name)
    if not base_k or len(base_k) < 2:
        return []
    matched: list[IndexedPost] = []
    for p in candidates:
        if exclude_code is not None and p.name_code == exclude_code:
            continue
        matched_code = False
        if p.name_code is not None and static is not None and p.name_code in static.characters:
            c_base, _ = split_character_name(static.name(p.name_code))
            if norm_key(c_base) == base_k:
                matched_code = True
        if not matched_code and p.category in ('character', 'topic'):
            subj_k = norm_key(p.subject)
            title_k = p.title_norm or norm_key(p.title)
            tags_k = [norm_key(t) for t in p.tags]
            if base_k in subj_k or base_k in title_k or any(base_k in tk for tk in tags_k):
                matched_code = True
        if matched_code:
            matched.append(p)
    return dedupe_recent_guides(rank_posts(matched, authors_by_id), limit=10)


def match_guides_rich(
    query: str,
    *,
    store,
    static,
    alias_store: AliasStore | None,
    authors: list[GuideAuthor],
) -> GuideMatchResult:
    """Resolve query using AliasStore + StaticData + fuzzy colon/word-order matching without mis-sending alters."""
    clean = str(query or '').strip()
    if not clean:
        return GuideMatchResult('none')

    authors_by_id = {a.author_id: a for a in authors if a.include_in_keyword_search}
    enabled_ids = set(authors_by_id)
    aliases = alias_store.read(static=static) if alias_store is not None else {}
    all_guides = [
        p for p in store.list_posts(categories=tuple(GUIDE_CATEGORIES), limit=500)
        if p.author_id in enabled_ids
    ]

    # 1. Try exact/alias character resolution via AliasStore + OpenCC + StaticData
    resolved_code: int | None = None
    ambiguous_candidates: list[str] = []
    try:
        resolved_code = resolve_character(clean, static, convert=_t2s(), aliases=aliases)
    except CharacterAmbiguous as exc:
        ambiguous_candidates = list(exc.candidates or ())
    except CharacterLookupError:
        resolved_code = None

    if resolved_code is not None:
        official_name = static.name(resolved_code)
        qk = norm_key(clean)
        off_k = norm_key(official_name)
        is_alias_input = bool(qk and off_k and qk != off_k)
        resolved_label = f'{official_name}（别名：{clean}）' if is_alias_input else official_name

        # 1a. Exact name_code index match
        hits = [p for p in store.find_by_name_code(resolved_code) if p.author_id in enabled_ids]
        if hits:
            return GuideMatchResult(
                'single', [rank_posts(hits, authors_by_id)[0]],
                resolved_code=resolved_code, resolved_name=official_name, resolved_label=resolved_label,
            )

        # 1b. EN fallback exact name match against tags/title
        en_keys = [norm_key(n) for n in EN_CHARACTER_FALLBACK.get(resolved_code, ())]
        if en_keys:
            tag_hits = [
                p for p in all_guides
                if any(ek in norm_key(p.title) or any(ek == norm_key(t) for t in p.tags) for ek in en_keys)
            ]
            if tag_hits:
                return GuideMatchResult(
                    'single', [rank_posts(tag_hits, authors_by_id)[0]],
                    resolved_code=resolved_code, resolved_name=official_name, resolved_label=resolved_label,
                )

        # 1c. Text-level match using resolved official name (colon/space/word-order tolerant, covering topic guides)
        text_hits = [
            p for p in all_guides
            if _post_exact_text_matches_character(
                p, official_name=official_name, static=static, resolved_code=resolved_code
            )
        ]
        if text_hits:
            return GuideMatchResult(
                'single', [rank_posts(text_hits, authors_by_id)[0]],
                resolved_code=resolved_code, resolved_name=official_name, resolved_label=resolved_label,
            )

        # 1d. Exact character has NO guide -> search related characters sharing base name for 'suggest' (NEVER auto-send wrong alter)
        base_name, _ = split_character_name(official_name)
        related = _find_related_base_posts(
            base_name=base_name,
            exclude_code=resolved_code,
            candidates=all_guides,
            static=static,
            authors_by_id=authors_by_id,
        )
        if related:
            return GuideMatchResult(
                'suggest', related,
                resolved_code=resolved_code, resolved_name=official_name, resolved_label=resolved_label,
                missing_reason='exact_character_missing',
            )
        return GuideMatchResult(
            'none', [],
            resolved_code=resolved_code, resolved_name=official_name, resolved_label=resolved_label,
            missing_reason='exact_character_missing',
        )

    # 2. Handle CharacterAmbiguous (multiple characters match a partial query like `灰姑娘` / `红莲`)
    if ambiguous_candidates:
        cand_codes: set[int] = set()
        for label in ambiguous_candidates:
            # Format: `{name}（{code}）`
            if label.endswith('）') and '（' in label:
                raw_code = label.rsplit('（', 1)[1][:-1]
                if raw_code.isdigit():
                    cand_codes.add(int(raw_code))
        matched_ambig = [p for p in all_guides if p.name_code in cand_codes]
        if matched_ambig:
            deduped = dedupe_recent_guides(rank_posts(matched_ambig, authors_by_id), limit=10)
            return GuideMatchResult('suggest', deduped, resolved_label=clean, missing_reason='ambiguous')
        return GuideMatchResult('none', [], resolved_label=clean)

    # 3. Non-character / topic / raid / partial keyword search
    qk = norm_key(clean)
    if not qk:
        return GuideMatchResult('none')

    # Prefer non-character topic/raid guides first for keyword queries like `魔方` or `奥图露亚`
    non_char_scored: list[tuple[int, IndexedPost]] = []
    char_partial_scored: list[tuple[int, IndexedPost]] = []
    for p in all_guides:
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
            if p.category == 'character':
                char_partial_scored.append((score, p))
            else:
                non_char_scored.append((score, p))

    if non_char_scored:
        non_char_scored.sort(key=lambda item: (-item[0], -int(item[1].created_on)))
        top_score = non_char_scored[0][0]
        top_posts = [p for s, p in non_char_scored if s >= max(60, top_score - 15)]
        deduped = dedupe_recent_guides(top_posts, limit=10)
        if len(deduped) == 1:
            return GuideMatchResult('single', deduped)
        return GuideMatchResult('multiple', deduped)

    if char_partial_scored:
        char_partial_scored.sort(key=lambda item: (-item[0], -int(item[1].created_on)))
        deduped = dedupe_recent_guides([p for _, p in char_partial_scored], limit=10)
        return GuideMatchResult('suggest', deduped, resolved_label=clean, missing_reason='partial_keyword')

    return GuideMatchResult('none', [], resolved_label=clean)


def match_guides(
    query: str,
    *,
    store,
    static,
    alias_store: AliasStore | None,
    authors: list[GuideAuthor],
) -> tuple[str, list[IndexedPost]]:
    """Backwards-compatible wrapper returning (status, matched_posts)."""
    res = match_guides_rich(query, store=store, static=static, alias_store=alias_store, authors=authors)
    return res.status, res.posts
