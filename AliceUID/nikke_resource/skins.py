"""Resolve API-reported costumes, never infer ownership from the public catalog.

Reviewed community nikke expanded L392-395 chooses roster costume_id by costume
ID (URL NikkeSkin is a browsing override, not player evidence). The detail API's
costume_tid is only a secondary report when the roster omits a valid value.
There is no reviewed owned-skins list: reported does not mean purchased.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..nikke_api.parser import StaticData


@dataclass(frozen=True)
class SkinSelection:
    skin_index: int
    costume_id: int | None
    source: str
    reported: bool
    mapped: bool
    notice: str


def _integer(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return None


def resolve_skin(roster: dict, static: StaticData, *, detail: dict | None = None) -> SkinSelection:
    """Map only this character's API costume ID to its public costume index.

    Roster wins conflicts, matching the community character page's initial
    selection. Missing/invalid reports and unmapped/ambiguous IDs use base art
    with an explanation. Static skins enumerate availability, not ownership.
    """
    detail = detail or {}
    code = _integer(roster.get('name_code'))
    detail_code = _integer(detail.get('name_code'))
    if code is None:
        code = detail_code
    # A mismatched detail must never supply another character's costume.
    detail_matches = detail_code is None or detail_code == code
    primary = _integer(roster.get('costume_id'))
    secondary = _integer(detail.get('costume_tid')) if detail_matches else None
    costume_id = primary if primary is not None else secondary
    source = 'roster.costume_id' if primary is not None else 'detail.costume_tid' if secondary is not None else 'default'
    conflict = primary is not None and secondary is not None and primary != secondary
    prefix = '接口皮肤报告冲突，采用角色列表 costume_id；' if conflict else ''
    if not detail_matches:
        prefix += '详情角色不匹配，已忽略详情皮肤；'
    if costume_id is None:
        return SkinSelection(0, None, source, False, False, prefix + '接口未报告有效皮肤，展示基础外观')
    if costume_id == 0:
        return SkinSelection(0, 0, source, True, True, prefix + '接口报告基础外观')
    rows = (static.character(code).get('costumes') or []) if code is not None else []
    matches = [row for row in rows if isinstance(row, dict) and _integer(row.get('id')) == costume_id]
    index = _integer(matches[0].get('costume_index')) if len(matches) == 1 else None
    if index is None or index > 999:
        return SkinSelection(0, costume_id, source, True, False, prefix + '接口报告皮肤未匹配静态映射，展示基础外观')
    return SkinSelection(index, costume_id, source, True, True, prefix + f'接口报告皮肤 {index}')
