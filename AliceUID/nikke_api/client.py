"""blablalink Game/* 接口客户端。

只依赖 httpx，不依赖 gsuid_core，方便单独测试与在登录服务里复用。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import httpx

from .auth import Credentials, GAME_ID_HMT, GAME_ID_INTL

BASE = "https://api.blablalink.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
)


@dataclass(frozen=True)
class Region:
    area_id: int
    name: str
    label: str
    game_id: str = GAME_ID_INTL


REGIONS: dict[int, Region] = {
    81: Region(81, "japan", "日服"),
    82: Region(82, "na", "北美服"),
    83: Region(83, "korea", "韩服"),
    84: Region(84, "global", "国际服"),
    85: Region(85, "sea", "东南亚服"),
}

HMT_REGION = Region(91, "hmt", "港澳台服", GAME_ID_HMT)


class NikkeApiError(Exception):
    def __init__(self, code: int, msg: str, endpoint: str = ""):
        self.code = code
        self.msg = msg
        self.endpoint = endpoint
        super().__init__(f"[{code}] {msg} ({endpoint})")


class NikkeLoginRequired(NikkeApiError):
    pass


class NikkeClient:
    def __init__(
        self,
        credentials: Credentials,
        region: Region,
        *,
        language: str = "zh-TW",
        user_agent: str = DEFAULT_UA,
        http: Optional[httpx.AsyncClient] = None,
        on_auth_failure=None,
    ):
        self.credentials = credentials
        self.region = region
        self.language = language
        self.user_agent = user_agent
        self._own_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=8.0),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=4,max_keepalive_connections=2),
        )
        self._lock = asyncio.Lock()
        self.on_auth_failure = on_auth_failure

    async def close(self):
        if self._own_http:
            await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ---------- 基础请求 ----------

    def headers(self) -> dict[str, str]:
        common = {
            "game_id": self.region.game_id,
            "area_id": self.region.name,
            "source": "pc_web",
            "intl_game_id": self.region.game_id,
            "language": self.language,
            "env": "prod",
        }
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
            "content-type": "application/json",
            "origin": "https://www.blablalink.com",
            "referer": "https://www.blablalink.com/",
            "x-channel-type": "2",
            "x-common-params": json.dumps(common, ensure_ascii=False, separators=(",", ":")),
            "x-language": self.language,
            "user-agent": self.user_agent,
            "cookie": self.credentials.cookie,
        }

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        # Account services own spacing, cache and single-flight. A failed or
        # ambiguous private request must never silently multiply into retries.
        try:
            if getattr(self.credentials,'expired',False):
                raise NikkeLoginRequired(300001,'登录凭据已过期，请重新登录',path)
            async with self._lock:
                resp = await self._http.request(
                    method,BASE+path,headers=self.headers(),
                    json=body if body is not None else {},follow_redirects=False,
                )
            if resp.status_code == 401:
                raise NikkeLoginRequired(401,'登录凭据被拒绝，请重新登录',path)
            if resp.status_code in (403,429):
                raise NikkeApiError(resp.status_code,'社区拒绝请求或请求过于频繁，请稍后检查账号状态',path)
            if resp.is_redirect:
                raise NikkeApiError(resp.status_code,'社区返回跳转，已停止请求，请检查登录状态',path)
            resp.raise_for_status()
            data=resp.json()
            if not isinstance(data,dict) or type(data.get('code')) not in (int,str):
                raise ValueError('invalid API envelope')
            code=int(data['code'])
            if code==0:
                return data
            if code in (401,300001):
                raise NikkeLoginRequired(code,'登录已失效，请重新登录',path)
            raise NikkeApiError(code,'社区未能完成请求，请稍后重试',path)
        except NikkeLoginRequired as exc:
            if self.on_auth_failure is not None:
                try:
                    self.on_auth_failure(exc.code)
                except Exception:
                    pass
            raise
        except NikkeApiError:
            raise
        except Exception as exc:
            # Transport exception strings and response bodies can contain
            # headers/account data. Expose only the error category.
            raise NikkeApiError(-1,f'请求失败（{type(exc).__name__}），未自动重试',path) from None

    # ---------- 账号 ----------

    async def check_login(self) -> bool:
        async with self._lock:
            resp = await self._http.get(
                BASE + "/api/user/CheckLogin", headers=self.headers(),follow_redirects=False
            )
        if resp.status_code!=200:
            return False
        data = resp.json()
        return data.get("code") == 0 and data.get("msg") == "ok"

    # ---------- 角色 ----------

    async def get_characters(self) -> list[dict]:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUserCharacters",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        payload = data.get("data") or {}
        return payload.get("characters") or []

    async def get_character_details(self, name_codes: Iterable[int]) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUserCharacterDetails",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
                "name_codes": list(name_codes),
            },
        )
        return data.get("data") or {}

    # ---------- 个人资料 ----------

    async def get_basic_info(self) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUserProfileBasicInfo",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        return (data.get("data") or {}).get("basic_info") or {}

    async def get_outpost_info(self) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUserProfileOutpostInfo",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        return (data.get("data") or {}).get("outpost_info") or {}

    async def get_daily_progress(self) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUserDailyContentsProgress",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        return data.get("data") or {}

    async def get_saved_role_info(self) -> dict:
        """个人主页显示的 UID（role_id）来自这里，不是 basic_info.gsn。"""
        data = await self._request(
            "POST", "/api/game/proxy/Game/GetSavedRoleInfo", {}
        )
        payload = data.get("data") or {}
        return payload.get("role_info") or {}

    async def get_game_player_info(self) -> dict:
        """社区侧的游戏概览：角色数、战力、塔、主线、公会名。"""
        data = await self._request(
            "POST",
            "/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo",
            {},
        )
        return data.get("data") or {}

    # ---------- 工会 ----------

    async def get_union_raid_level(self) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUnionRaidLevelInfo",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        return data.get("data") or {}

    async def get_union_raid_data(self) -> dict:
        data = await self._request(
            "POST",
            "/api/game/proxy/Game/GetUnionRaidData",
            {
                "intl_open_id": self.credentials.openid,
                "nikke_area_id": self.region.area_id,
            },
        )
        return data.get("data") or {}

    # ---------- 区服探测 ----------

    @classmethod
    async def detect_region(
        cls,
        credentials: Credentials,
        *,
        candidates: Iterable[Region] = tuple(REGIONS.values()),
        language: str = "zh-TW",
    ) -> tuple[Region, list[dict]]:
        """依次试区服，返回第一个有角色的。实测日服=81。"""
        last: Exception | None = None
        for region in candidates:
            client = cls(credentials, region, language=language)
            try:
                chars = await client.get_characters()
                if chars:
                    return region, chars
            except NikkeLoginRequired:
                raise
            except Exception as exc:  # noqa: BLE001
                last = exc
            finally:
                await client.close()
        if last:
            raise last
        raise NikkeApiError(-1, "no region matched")
