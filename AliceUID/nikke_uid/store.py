"""UID identity registration only. No credentials, ownership proof or network IO."""
from __future__ import annotations
from ..nikke_commands import command_prefix

import base64
import binascii
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

# Identity registration follows currently supported login regions, but never logs in.
GAME_REGIONS = {
    "日服": ("29080", 81),
    "北美服": ("29080", 82),
    "韩服": ("29080", 83),
    "国际服": ("29080", 84),
    "东南亚服": ("29080", 85),
}
_OFFICIAL_HOSTS = frozenset({"www.blablalink.com", "blablalink.com"})
_FULL_ID = re.compile(r"(29080|29157)-([0-9]{9,30})\Z")
_FIELDS = frozenset({
    "community_uid", "game_uid", "game_region", "game_area_id", "game_game_id",
    "share_intl_openid", "share_game_id", "share_openid_suffix",
})
_store: UIDStore | None = None


def _numeric_identifier(value: str, label: str) -> str:
    # Do not coerce numbers: a JS Number may have lost precision before arrival.
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,30}", value):
        raise ValueError(f"{label}须为1至30位半角数字，请按字符串输入；不会按位数猜测类型。")
    return value


def _owner(user_id: str, bot_id: str) -> tuple[str, str]:
    values = (user_id, bot_id)
    if any(not isinstance(v, str) or not v or len(v) > 128
           or any(c.isspace() or ord(c) < 32 for c in v) for v in values):
        raise ValueError("无法确认当前用户与Bot，UID登记未执行。")
    return values


def _decode_full_identity(encoded: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", encoded) or len(encoded) > 512:
        raise ValueError("分享标识不是有效的Base64完整标识。")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
    except (ValueError, UnicodeError, binascii.Error):
        raise ValueError("分享标识不是有效的Base64完整标识。") from None
    if not _FULL_ID.fullmatch(decoded):
        raise ValueError("分享内容须为完整NIKKE标识：29080或29157，加连字符和9至30位数字后缀。")
    return decoded


def parse_share(value: str) -> dict[str, str]:
    """Parse an official HTTPS URL or Base64 locally; never fetch its target."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("请输入官网分享URL或Base64完整标识。")
    if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("分享输入不能包含空白、控制字符或反斜线。")
    if "://" in value or value.startswith("//"):
        try:
            url = urlsplit(value)
            valid_origin = (url.scheme == "https" and url.hostname in _OFFICIAL_HOSTS
                            and url.port in (None, 443) and url.username is None
                            and url.password is None and not url.fragment)
        except ValueError:
            valid_origin = False
        if not valid_origin:
            raise ValueError("仅接受 blablalink.com 或 www.blablalink.com 的HTTPS分享URL。")
        if ("%" in url.path or any(part in (".", "..") for part in url.path.split("/"))
                or not any(url.path == p or url.path.startswith(p + "/")
                           for p in ("/shiftyspad", "/user"))):
            raise ValueError("请使用官网角色工具或用户页面的分享URL。")
        try:
            query = parse_qs(url.query, keep_blank_values=True, max_num_fields=30)
        except ValueError:
            raise ValueError("分享URL参数过多或格式不正确。") from None
        keys = [key for key in ("uid", "openid") if key in query]
        if len(keys) != 1 or len(query[keys[0]]) != 1 or not query[keys[0]][0]:
            raise ValueError("分享URL须包含唯一且非空的uid或openid参数。")
        encoded = query[keys[0]][0]
        # The community /user branch accepts an original full openid too.
        if keys[0] == "openid" and _FULL_ID.fullmatch(encoded):
            full = encoded
        else:
            full = _decode_full_identity(encoded)
    else:
        full = _decode_full_identity(value)
    match = _FULL_ID.fullmatch(full)
    if match is None:
        raise ValueError("未能解析完整NIKKE分享标识。")
    return {"share_intl_openid": full, "share_game_id": match.group(1),
            "share_openid_suffix": match.group(2)}


class UIDStore:
    """One independent row per (user_id, bot_id); namespace updates are atomic.

    Each method owns and closes its SQLite connection, so separate instances or
    threads share the DB transaction lock rather than a process-local RMW cache.
    Methods are synchronous, short local operations. Do not use this store as auth.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS uid_bindings (
                user_id TEXT NOT NULL, bot_id TEXT NOT NULL,
                community_uid TEXT,
                game_uid TEXT, game_region TEXT, game_area_id INTEGER, game_game_id TEXT,
                share_intl_openid TEXT, share_game_id TEXT, share_openid_suffix TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, bot_id)
            )""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def get(self, user_id: str, bot_id: str) -> dict | None:
        owner = _owner(user_id, bot_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM uid_bindings WHERE user_id=? AND bot_id=?", owner
            ).fetchone()
            return dict(row) if row else None

    def _upsert(self, user_id: str, bot_id: str, fields: dict) -> dict:
        owner = _owner(user_id, bot_id)
        if not fields or not fields.keys() <= _FIELDS:
            raise ValueError("不支持的UID登记字段。")
        # Columns come only from the internal allowlist; every value is bound.
        names = list(fields)
        columns = ",".join(["user_id", "bot_id", *names, "updated_at"])
        slots = ",".join("?" for _ in range(len(names) + 3))
        updates = ",".join(f"{name}=excluded.{name}" for name in [*names, "updated_at"])
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"INSERT INTO uid_bindings ({columns}) VALUES ({slots}) "
                f"ON CONFLICT(user_id,bot_id) DO UPDATE SET {updates}",
                (*owner, *fields.values(), int(time.time())),
            )
            row = connection.execute(
                "SELECT * FROM uid_bindings WHERE user_id=? AND bot_id=?", owner
            ).fetchone()
            result = dict(row)
        return result  # Context commits before reporting a successful update.

    def bind_community(self, user_id: str, bot_id: str, value: str) -> dict:
        return self._upsert(user_id, bot_id, {
            "community_uid": _numeric_identifier(value, "社区标识"),
        })

    def bind_game(self, user_id: str, bot_id: str, region: str, value: str) -> dict:
        if region not in GAME_REGIONS:
            raise ValueError("请明确选择区服：" + " / ".join(GAME_REGIONS))
        game_id, area_id = GAME_REGIONS[region]
        return self._upsert(user_id, bot_id, {
            "game_uid": _numeric_identifier(value, "游戏UID"),
            "game_region": region, "game_area_id": area_id, "game_game_id": game_id,
        })

    def bind_share(self, user_id: str, bot_id: str, value: str) -> dict:
        return self._upsert(user_id, bot_id, parse_share(value))

    def clear(self, user_id: str, bot_id: str) -> bool:
        owner = _owner(user_id, bot_id)
        with closing(self._connect()) as connection, connection:
            count = connection.execute(
                "DELETE FROM uid_bindings WHERE user_id=? AND bot_id=?", owner
            ).rowcount
        return count > 0


def get_uid_store() -> UIDStore:
    """Lazy config/DB initialization; importing the pure store never starts core."""
    global _store
    if _store is None:
        from ..nikke_config.config import MAIN_PATH
        _store = UIDStore(MAIN_PATH / "uid_bindings.sqlite3")
    return _store


def format_summary(record: dict | None) -> str:
    if not record:
        return f"你还没有登记UID。发送 {command_prefix()}绑定UID 查看用法。"
    lines = ["你的UID登记"]
    if record.get("community_uid"):
        lines.append(f"社区标识（本人输入）：{record['community_uid']}")
    if record.get("game_uid"):
        lines.append(f"游戏UID（{record.get('game_region') or '区服未知'}）：{record['game_uid']}")
    if record.get("share_intl_openid"):
        lines.extend([
            f"分享完整标识 intl_openid：{record['share_intl_openid']}",
            f"分享游戏ID：{record['share_game_id']}",
            f"分享 openid 后缀：{record['share_openid_suffix']}",
            "分享后缀与社区标识分别记录，不自动认定为同一种UID。",
        ])
    lines.extend(["仅登记标识，尚未验证账号归属；登记不等于登录或数据已公开。",
                  f"查询本人练度仍需通过 {command_prefix()}登录日服 等区服命令完成登录。"])
    return "\n".join(lines)
