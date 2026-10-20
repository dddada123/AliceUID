"""Confirmed public NKAS endpoints; no retry and no credential persistence."""
from __future__ import annotations
from ..nikke_commands import command_prefix

import re
from typing import Any

BASE = "https://api.blablalink.com"
POINTS = "/api/lip/proxy/lipass/Points/"
DYNAMICS = "/api/ugc/direct/standalonesite/Dynamics/"
STAR = "/api/ugc/proxy/standalonesite/Dynamics/PostStar"


class CommunityError(Exception):
    """Only a sanitized reason may be persisted or shown to the user."""


class CommunityAPI:
    def __init__(self, client):
        self.client = client

    def _auth_failed(self, code):
        callback = getattr(self.client, 'on_auth_failure', None)
        if callable(callback):
            try:
                callback(code)
            except Exception:
                pass

    async def request(self, method: str, path: str, *, body=None, params=None) -> dict:
        # Keep a separate write boundary: never retry an uncertain interaction.
        try:
            response = await self.client._http.request(
                method, BASE + path, headers=self.client.headers(),
                json=body, params=params, follow_redirects=False,
            )
            if response.status_code == 401:
                self._auth_failed(401)
                raise CommunityError(f"登录已失效，请发送{command_prefix()}重新登录后手动开启")
            if response.status_code == 403:
                raise CommunityError("社区拒绝访问，请检查资料权限或访问限制后手动开启")
            if response.status_code == 429:
                raise CommunityError("平台限流，请稍后人工检查并手动开启")
            if response.status_code != 200:
                raise CommunityError("HTTP 异常，任务已暂停")
            payload = response.json()
            if not isinstance(payload, dict) or type(payload.get("code")) is not int:
                raise CommunityError("社区响应格式变化，任务已暂停")
            if payload["code"] in (401,300001):
                self._auth_failed(payload["code"])
                raise CommunityError(f"登录已失效，请发送{command_prefix()}重新登录后手动开启")
            if payload["code"] != 0:
                raise CommunityError("社区返回业务异常，任务已暂停")
            data = payload.get("data")
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise CommunityError("社区数据格式变化，任务已暂停")
            return data
        except CommunityError:
            raise
        except Exception:
            # Transport errors may contain request headers, cookies or response text.
            raise CommunityError("网络或响应异常，结果未确认，任务已暂停") from None


def task_kind(name: str) -> str | None:
    """Pinned NKAS labels plus conservative numeric post-count variants.

    NKAS uses arbitrary substring matching. Here a full match avoids treating
    unrelated campaigns containing 'Like' or 'Browse' as supported tasks.
    Japanese labels are not supplied by the reference and remain unknown.
    """
    patterns = {
        "signin": r"(?:每日簽到|每日签到|(?:Daily )?Sign-in)",
        "browse": r"(?:(?:瀏覽|浏览)(?:\s*\d+\s*(?:篇|個|个)?\s*)?(?:帖子|貼文|文章)?|Browse(?:\s+\d+)?(?:\s+Posts?)?)",
        "like": r"(?:(?:按讚|点赞)(?:\s*\d+\s*(?:篇|個|个)?\s*)?(?:帖子|貼文|文章)?|Like(?:\s+\d+)?(?:\s+Posts?)?)",
    }
    return next((kind for kind, pattern in patterns.items()
                 if re.fullmatch(pattern, name.strip(), re.IGNORECASE)), None)


def parse_tasks(data: dict) -> list[dict[str, Any]]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise CommunityError("任务列表格式变化，任务已暂停")
    parsed = []
    for task in tasks:
        if not isinstance(task, dict):
            raise CommunityError("任务结构变化，任务已暂停")
        rewards = task.get("reward_infos")
        # Missing/ambiguous completion status must never trigger an interaction.
        complete = None
        if isinstance(rewards, list) and rewards and all(
            isinstance(r, dict) and type(r.get("is_completed")) is bool for r in rewards
        ):
            complete = all(r["is_completed"] for r in rewards)
        name = task.get("task_name", "")
        if not isinstance(name, str):
            raise CommunityError("任务名称格式变化，任务已暂停")
        task_id = task.get("task_id")
        parsed.append({"id": str(task_id) if isinstance(task_id, (str, int)) else "",
                       "name": name, "kind": task_kind(name), "completed": complete})
    return parsed
