"""blablalink 凭证：Cookie 构造、解析、加密存储。

实测结论（2026-10-17，日服账号）：
- 业务接口只认 Cookie，openid 单独使用会返回 300001 game not login。
- 最小可用 Cookie 为 game_openid / game_channelid / game_token / game_gameid /
  game_login_game / game_adult_status，CheckLogin 返回 code=0 即有效。
- game_token 有效期约 30 天，token_expire_time 为秒级时间戳。
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

GAME_ID_INTL = "29080"  # 日/国际/北美/韩/东南亚
GAME_ID_HMT = "29157"  # 港澳台

COOKIE_KEYS = (
    "game_openid",
    "game_channelid",
    "game_token",
    "game_gameid",
    "game_login_game",
    "game_adult_status",
)


@dataclass
class Credentials:
    """一份可用的 blablalink 登录凭证。"""

    openid: str
    token: str
    channel_id: str = "131"
    game_id: str = GAME_ID_INTL
    expire_at: int = 0
    uid: str = ""
    user_name: str = ""

    @property
    def cookie(self) -> str:
        return build_cookie(
            openid=self.openid,
            token=self.token,
            channel_id=self.channel_id,
            game_id=self.game_id,
            uid=self.uid,
            user_name=self.user_name,
        )

    @property
    def expired(self) -> bool:
        return bool(self.expire_at and self.expire_at <= int(time.time()))

    @property
    def days_left(self) -> int:
        if not self.expire_at:
            return 0
        return max(0, (self.expire_at - int(time.time())) // 86400)


def build_cookie(
    openid: str,
    token: str,
    channel_id: str = "131",
    game_id: str = GAME_ID_INTL,
    uid: str = "",
    user_name: str = "",
) -> str:
    """按站点结构拼最小 Cookie。

    注意：不要直接拼接浏览器里取出的全部 Cookie。站点会在多个域下重复写同名
    Cookie，直接拼接会出现 29080 -> 29089080 这种重复值。
    """
    parts = [
        f"game_openid={openid}",
        f"game_channelid={channel_id}",
        f"game_token={token}",
        f"game_gameid={game_id}",
        "game_login_game=0",
        "game_adult_status=1",
    ]
    if uid:
        parts.append(f"game_uid={uid}")
    if user_name:
        parts.append(f"game_user_name={user_name}")
    return "; ".join(parts)


def parse_cookie(cookie: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for seg in (cookie or "").split(";"):
        seg = seg.strip()
        if not seg or "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def credentials_from_cookie(cookie: str, expire_at: int = 0) -> Optional[Credentials]:
    data = parse_cookie(cookie)
    openid = data.get("game_openid", "")
    token = data.get("game_token", "")
    if not openid or not token:
        return None
    return Credentials(
        openid=openid,
        token=token,
        channel_id=data.get("game_channelid", "131"),
        game_id=data.get("game_gameid", GAME_ID_INTL) or GAME_ID_INTL,
        expire_at=expire_at,
        uid=data.get("game_uid", ""),
        user_name=data.get("game_user_name", ""),
    )


def decode_openid_b64(value: str) -> tuple[str, str]:
    """解码 ShiftyPad 链接里的 openid。

    `MjkwODAtMTIzNDU2Nzg5MDEyMzQ1Njc4OQ==` -> ("29080", "1234567890123456789")
    """
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")
    except Exception:
        return "", ""
    if "-" in raw:
        game_id, openid = raw.split("-", 1)
        return game_id, openid
    return "", raw if raw.isdigit() else ""


def encode_openid_b64(game_id: str, openid: str) -> str:
    return base64.b64encode(f"{game_id}-{openid}".encode()).decode()


def parse_openid_input(text: str) -> tuple[str, str]:
    """从主页链接、base64 openid、纯 openid 中提取 (game_id, openid)。"""
    text = (text or "").strip()
    if "openid=" in text:
        text = text.split("openid=", 1)[1].split("&", 1)[0]
    if text.startswith("http"):
        return "", ""
    if "-" in text and text.replace("-", "").isdigit():
        game_id, openid = text.split("-", 1)
        return game_id, openid
    if text.isdigit():
        return "", text
    game_id, openid = decode_openid_b64(text)
    return game_id, openid


class CookieCipher:
    """Cookie 加密。密钥放在 data 目录，不进 config.json、不进仓库。"""

    def __init__(self, key_path: Path):
        from cryptography.fernet import Fernet

        self.key_path = Path(key_path)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:
                pass
        self._fernet = Fernet(self.key_path.read_bytes())

    def encrypt(self, text: str) -> str:
        return self._fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def decrypt(self, blob: str) -> str:
        return self._fernet.decrypt(blob.encode("ascii")).decode("utf-8")


def mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * (len(value) - keep * 2)}{value[-keep:]}"
