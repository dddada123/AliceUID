"""Confirmed public NKAS endpoints; no retry and no credential persistence."""
from __future__ import annotations
from ..nikke_commands import command_prefix

import re
import httpx
from typing import Any

BASE = "https://api.blablalink.com"
POINTS = "/api/lip/proxy/lipass/Points/"
DYNAMICS = "/api/ugc/direct/standalonesite/Dynamics/"
STAR = "/api/ugc/proxy/standalonesite/Dynamics/PostStar"


class CommunityError(Exception):
    """Only a sanitized reason may be persisted or shown to the user."""
    def __init__(self, reason, *, category='policy', retryable=False, not_sent=False):
        super().__init__(reason)
        self.category, self.retryable, self.not_sent = category, retryable, not_sent


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
                raise CommunityError(f"社区返回登录认证异常，请本人发送{command_prefix()}重新登录", category="auth")
            if response.status_code == 403:
                raise CommunityError("社区拒绝访问（HTTP 403），请检查资料权限或访问限制", category="forbidden")
            if response.status_code == 429:
                raise CommunityError("平台限流（HTTP 429），本轮未继续请求", category="rate_limit")
            if response.status_code != 200:
                raise CommunityError(f"社区HTTP异常（{response.status_code}）", category="server", retryable=response.status_code>=500)
            payload = response.json()
            if not isinstance(payload, dict) or type(payload.get("code")) is not int:
                raise CommunityError("社区响应格式变化，未提交不明确的任务", category="schema")
            if payload["code"] in (401,300001):
                raise CommunityError(f"社区返回登录认证异常，请本人发送{command_prefix()}重新登录", category="auth")
            if payload["code"] != 0:
                raise CommunityError(f'社区业务异常（错误码{payload["code"]}）', category="business")
            data = payload.get("data")
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise CommunityError("社区数据格式变化，未提交不明确的任务", category="schema")
            return data
        except CommunityError:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise CommunityError("连接未建立，签到请求未发出", category="network", retryable=True, not_sent=True) from None
        except Exception:
            # Transport errors may contain request headers, cookies or response text.
            raise CommunityError("网络或响应异常，签到结果未确认", category="network", retryable=True) from None


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
        raise CommunityError("任务列表格式变化，未提交不明确的任务", category="schema")
    parsed = []
    for task in tasks:
        if not isinstance(task, dict):
            raise CommunityError("任务结构变化，未提交不明确的任务", category="schema")
        rewards = task.get("reward_infos")
        # Missing/ambiguous completion status must never trigger an interaction.
        complete = None
        if isinstance(rewards, list) and rewards and all(
            isinstance(r, dict) and type(r.get("is_completed")) is bool for r in rewards
        ):
            complete = all(r["is_completed"] for r in rewards)
        name = task.get("task_name", "")
        if not isinstance(name, str):
            raise CommunityError("任务名称格式变化，未提交不明确的任务", category="schema")
        task_id = task.get("task_id")
        parsed.append({"id": str(task_id) if isinstance(task_id, (str, int)) else "",
                       "name": name, "kind": task_kind(name), "completed": complete})
    return parsed
