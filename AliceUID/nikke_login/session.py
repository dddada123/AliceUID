"""一次性登录会话（内存）。"""
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from .browser import LoginResult


@dataclass
class LoginSession:
    token: str
    user_id: str
    bot_id: str
    group_id: Optional[str]
    area_id: int = 0
    ttl: int = 600
    success_at: float = 0
    operation_started_at: float = 0
    captcha_id: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "created"  # created | sending_code | awaiting_code | logging_in | captcha | success | failed
    error: str = ""
    nickname: str = ""
    uid: str = ""
    area_label: str = ""
    captcha_png: Optional[bytes] = None
    captcha_piece: Optional[dict] = None
    captcha_hole: Optional[dict] = None
    captcha_slider: Optional[dict] = None
    captcha_size: Optional[dict] = None
    captcha_dx: Optional[float] = None
    captcha_event: asyncio.Event = field(default_factory=asyncio.Event)
    result: Optional[LoginResult] = None
    generation: int = 0
    task: Optional[asyncio.Task] = field(default=None, repr=False)
    mode: str = "password"
    replace_revision: str = ""
    cookie_expire: int = 0
    email_code: str = field(default="", repr=False)
    code_event: asyncio.Event = field(default_factory=asyncio.Event)
    code_deadline: float = 0
    resend_at: float = 0
    heartbeat_at: float = field(default_factory=time.time)

    def cancel(self):
        self.generation += 1
        self.email_code = ""
        self.code_event.set()
        self.captcha_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
        self.captcha_png = None
        self.captcha_piece = self.captcha_hole = self.captcha_size = self.captcha_slider = None
        self.captcha_dx = None
        self.captcha_id = ""


    @property
    def expired(self) -> bool:
        if self.status == "success" and self.success_at:
            return time.time() - self.success_at > 300
        if self.status in ('logging_in', 'captcha', 'sending_code', 'awaiting_code') and self.operation_started_at:
            return time.time() - self.operation_started_at > 360
        return time.time() - self.created_at > self.ttl


class SessionStore:
    def __init__(self):
        self._data: Dict[str, LoginSession] = {}

    def create(self, user_id: str, bot_id: str, group_id: Optional[str], *, area_id: int, ttl: int = 600) -> LoginSession:
        self.cleanup()
        if self.active(user_id, bot_id) is not None:
            raise ValueError('已有登录正在处理，请完成当前验证后再选择区服')
        # 同一用户只保留最新一个未开始会话
        for token in [k for k, v in self._data.items() if v.user_id == user_id and v.bot_id == bot_id]:
            self.delete(token)
        token = secrets.token_urlsafe(18)
        session = LoginSession(token=token, user_id=user_id, bot_id=bot_id, group_id=group_id, area_id=area_id, ttl=max(60, int(ttl)))
        self._data[token] = session
        return session

    def active(self, user_id: str, bot_id: str) -> Optional[LoginSession]:
        self.cleanup()
        return next((session for session in self._data.values()
                     if session.user_id == user_id and session.bot_id == bot_id
                     and session.status in ('logging_in', 'captcha', 'sending_code', 'awaiting_code')), None)

    def get(self, token: str) -> Optional[LoginSession]:
        session = self._data.get(token)
        if session and session.expired:
            self.delete(token)
            return None
        return session

    def clear_owner(self, user_id: str, bot_id: str):
        for token in [key for key, value in self._data.items()
                      if value.user_id == user_id and value.bot_id == bot_id]:
            self.delete(token)

    def delete(self, token: str):
        session = self._data.pop(token, None)
        if session:
            session.cancel()

    def cleanup(self):
        for token in [k for k, v in self._data.items() if v.expired]:
            self.delete(token)


sessions = SessionStore()
