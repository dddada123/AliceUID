"""把接口原始 JSON 归一化成卡片可以直接使用的结构。

字段按社区繁体中文响应归一化；保留原值与缺失状态，不把未知数据当作零。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

# 装备词条的 function_type -> 中文名
STAT_NAMES: dict[str, str] = {
    "IncElementDmg": "优越代码伤害",
    "StatAtk": "攻击力",
    "StatAmmoLoad": "最大装弹数",
    "StatChargeTime": "蓄力速度",
    "StatChargeDamage": "蓄力伤害",
    "StatCritical": "暴击率",
    "StatCriticalDamage": "暴击伤害",
    "StatDef": "防御力",
    "StatHitRate": "命中率",
    "StatAccuracyCircle": "命中率",
    "OnHitRatio": "命中率",
}

# 卡片上优先展示的四条
STAT_PRIORITY = [
    "IncElementDmg",
    "StatAtk",
    "StatAmmoLoad",
    "StatChargeDamage",
    "StatCriticalDamage",
    "StatCritical",
    "StatChargeTime",
    "StatDef",
    "StatHitRate",
]

GRADE_LABEL = {0: "0", 1: "1", 2: "2", 3: "MAX"}
TZ = timezone(timedelta(hours=8))


def static_weapon_type(row: dict) -> str | None:
    """Read the reviewed shot_id.element.weapon_type, not a guessed top-level key."""
    if not isinstance(row, dict):
        return None
    shot = row.get('shot_id')
    element = shot.get('element') if isinstance(shot, dict) else None
    value = element.get('weapon_type') if isinstance(element, dict) else None
    if value is None:
        value = row.get('weapon_type')  # legacy normalized metadata
    return value if isinstance(value, str) and value else None


@dataclass
class StaticData:
    characters: dict[int, dict] = field(default_factory=dict)
    stages: dict[int, str] = field(default_factory=dict)
    options: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, data_dir: Path, locale: str = "zh-tw") -> "StaticData":
        data_dir = Path(data_dir)
        obj = cls()

        char_file = data_dir / f"nikke_list_{locale}_v2.json"
        if not char_file.exists():
            # 兼容 zh-TW 命名
            char_file = data_dir / "nikke_list_zh-TW_v2.json"
        if char_file.exists():
            rows = json.loads(char_file.read_text(encoding="utf-8-sig"))
            obj.characters = {int(x["name_code"]): x for x in rows if "name_code" in x}

        stage_file = data_dir / "stage_list.json"
        if stage_file.exists():
            rows = json.loads(stage_file.read_text(encoding="utf-8-sig"))
            obj.stages = {
                int(x["id"]): (x.get("name_localkey") or {}).get("name", "")
                for x in rows
            }

        option_file = data_dir / f"equip_option_table_v2-{locale}.json"
        if option_file.exists():
            obj.options = json.loads(option_file.read_text(encoding="utf-8-sig"))

        return obj

    def character(self, name_code: int) -> dict:
        return self.characters.get(int(name_code), {})

    def name(self, name_code: int) -> str:
        return ((self.character(name_code).get("name_localkey") or {}).get("name")) or str(name_code)

    def resource_id(self, name_code: int) -> int:
        return int(self.character(name_code).get("resource_id") or 0)

    def skin_index(self, name_code: int, costume_id: int) -> int:
        for costume in self.character(name_code).get("costumes") or []:
            if int(costume.get("id") or 0) == int(costume_id or 0):
                return int(costume.get("costume_index") or 0)
        return 0

    def stage_name(self, stage_id: int) -> str:
        if not stage_id:
            return ""
        name = self.stages.get(int(stage_id), "")
        for suffix in (" HARD STAGE", " BOSS", " STAGE"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name or str(stage_id)

    def element(self, name_code: int) -> str:
        raw = self.character(name_code).get("element_id") or {}
        return ((raw.get("element") or {}).get("element")) or ""

    def corporation(self, name_code: int) -> str:
        return self.character(name_code).get("corporation") or ""

    def burst(self, name_code: int) -> str:
        raw = self.character(name_code).get("use_burst_skill") or ""
        return raw.replace("Step", "") if raw.startswith("Step") else raw

    def char_class(self, name_code: int) -> str:
        return self.character(name_code).get("class") or ""

    def rarity(self, name_code: int) -> str:
        return self.character(name_code).get("original_rare") or ""


def _ts_date(ts: int | str | None) -> str:
    try:
        value = int(ts or 0)
    except (TypeError, ValueError):
        return ""
    if not value:
        return ""
    return datetime.fromtimestamp(value, TZ).strftime("%Y-%m-%d")


def _fmt_percent(raw: float) -> str:
    return f"{raw / 100:.2f}%"


def aggregate_stats(detail: dict, state_effects: Iterable[dict]) -> list[dict]:
    """把 12 个装备词条 id 聚合成 9 类属性。

    实测：同一 function_type 的多条词条要相加。第一条角色的
    IncElementDmg=2776+2636=5412 -> 54.12%，与页面一致。
    """
    effects = {str(x.get("id")): x for x in state_effects}
    totals: dict[str, dict] = {}

    slots = ("head", "torso", "arm", "leg")
    for slot in slots:
        for idx in (1, 2, 3):
            oid = detail.get(f"{slot}_equip_option{idx}_id")
            effect = effects.get(str(oid))
            if not effect:
                continue
            for fn in effect.get("function_details") or []:
                key = fn.get("function_type") or ""
                if not key:
                    continue
                item = totals.setdefault(
                    key,
                    {
                        "key": key,
                        "name": STAT_NAMES.get(key, key),
                        "value": 0.0,
                        "value_type": fn.get("function_value_type") or "Percent",
                        "levels": [],
                    },
                )
                item["value"] += float(fn.get("function_value") or 0)
                item["levels"].append(int(fn.get("level") or 0))

    out = []
    for item in totals.values():
        if item["value_type"] == "Percent":
            item["display"] = _fmt_percent(item["value"])
        else:
            item["display"] = f"{int(item['value'])}"
        item["sort"] = abs(item["value"])
        out.append(item)

    order = {k: i for i, k in enumerate(STAT_PRIORITY)}
    out.sort(key=lambda x: (order.get(x["key"], 99), -x["sort"]))
    return out


def parse_profile(
    basic: dict,
    outpost: dict,
    static: StaticData,
    saved_role: dict | None = None,
    player_info: dict | None = None,
) -> dict:
    saved_role = saved_role or {}
    player_info = player_info or {}
    team = []
    for item in basic.get("profile_team") or []:
        code = int(item.get("name_code") or 0)
        if not code:
            continue
        team.append(
            {
                "name_code": code,
                "slot": item.get("slot"),
                "name": static.name(code),
                "resource_id": static.resource_id(code),
            }
        )

    return {
        "nickname": basic.get("nickname") or saved_role.get("role_name") or "",
        "uid": str(saved_role.get("role_id") or ""),
        "zone_id": str(saved_role.get("zone_id") or ""),
        "guild_name": player_info.get("guild_name") or "",
        "level": int(basic.get("lv") or player_info.get("player_level") or 0),
        "area_id": int(basic.get("area_id") or 0),
        "created_at": _ts_date(basic.get("created_at")),
        "character_count": int(basic.get("character_count") or 0),
        "costume_count": int(basic.get("character_costume_count") or 0),
        "team_combat": int(basic.get("team_combat") or 0),
        "synchro_level": int(outpost.get("synchro_level") or 0),
        "outpost_battle_level": int(outpost.get("outpost_battle_level") or 0),
        "infra_core_level": int(outpost.get("infra_core_level") or 0),
        "overclock": int(basic.get("sim_room_overclock_current_sub_season_high_score") or 0),
        "tower": int(basic.get("progress_tribe_tower") or 0),
        "tower_elysion": int(basic.get("progress_elysion_tower") or 0),
        "tower_missilis": int(basic.get("progress_missilis_tower") or 0),
        "tower_tetra": int(basic.get("progress_tetra_tower") or 0),
        "tower_pilgrim": int(basic.get("progress_pilgrim_tower") or 0),
        "campaign_normal": static.stage_name(basic.get("progress_normal_campaign") or 0),
        "campaign_hard": static.stage_name(basic.get("progress_hard_campaign") or 0),
        "campaign_easy": static.stage_name(basic.get("progress_easy_campaign") or 0),
        "profile_team": team,
        "recycle_researches": outpost.get("recycle_room_researches") or [],
    }


def parse_character(
    roster: dict,
    detail: dict,
    state_effects: Iterable[dict],
    static: StaticData,
) -> dict:
    code = int(roster.get("name_code") or detail.get("name_code") or 0)

    gear = {}
    for slot in ("head", "torso", "arm", "leg"):
        gear[slot] = {
            "tier": int(detail.get(f"{slot}_equip_tier") or 0),
            "lv": int(detail.get(f"{slot}_equip_lv") or 0),
            "tid": int(detail.get(f"{slot}_equip_tid") or 0),
            "options": [
                int(detail.get(f"{slot}_equip_option{i}_id") or 0) for i in (1, 2, 3)
            ],
        }

    return {
        "name_code": code,
        "name": static.name(code),
        "resource_id": static.resource_id(code),
        "rarity": static.rarity(code),
        "char_class": static.char_class(code),
        "burst": static.burst(code),
        "element": static.element(code),
        "corporation": static.corporation(code),
        "combat": int(roster.get("combat") or detail.get("combat") or 0),
        "arena_combat": int(detail.get("arena_combat") or 0),
        "level": int(roster.get("lv") or 0),
        "grade": int(roster.get("grade") or detail.get("grade") or 0),
        "core": int(roster.get("core") or detail.get("core") or 0),
        "costume_id": int(roster.get("costume_id") or detail.get("costume_tid") or 0),
        "skills": [
            int(detail.get("skill1_lv") or 0),
            int(detail.get("skill2_lv") or 0),
            int(detail.get("ulti_skill_lv") or 0),
        ],
        "gear": gear,
        "cube": {
            "tid": int(detail.get("harmony_cube_tid") or 0),
            "lv": int(detail.get("harmony_cube_lv") or 0),
        },
        "favorite": {
            "tid": int(detail.get("favorite_item_tid") or 0),
            "lv": int(detail.get("favorite_item_lv") or 0),
        },
        "bond": int(detail.get("attractive_lv") or 0),
        "stats": aggregate_stats(detail, state_effects),
    }


def parse_roster(chars: Iterable[dict], static: StaticData) -> list[dict]:
    out = []
    for c in chars:
        code = int(c.get("name_code") or 0)
        out.append(
            {
                "name_code": code,
                "name": static.name(code),
                "resource_id": static.resource_id(code),
                "rarity": static.rarity(code),
                "char_class": static.char_class(code),
                "burst": static.burst(code),
                "element": static.element(code),
                "corporation": static.corporation(code),
                "combat": int(c.get("combat") or 0),
                "level": int(c.get("lv") or 0),
                "grade": int(c.get("grade") or 0),
                "core": int(c.get("core") or 0),
                "costume_id": int(c.get("costume_id") or 0),
            }
        )
    out.sort(key=lambda x: x["combat"], reverse=True)
    return out
