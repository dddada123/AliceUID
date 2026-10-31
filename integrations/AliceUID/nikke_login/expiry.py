"""Explain official expiry without inventing a local token renewal."""
from ..nikke_commands import command_prefix
from datetime import datetime,timezone,timedelta
import time


def expiry_notice(expire_at=0, *, now=None):
    now=time.time() if now is None else now
    if type(expire_at) is int and expire_at>0:
        seconds=expire_at-now
        if seconds<=0:
            return f'Cookie已到期，请发送 {command_prefix()}重新登录（或 {command_prefix()}重新登陆）更新。'
        days=max(1,int((seconds+86399)//86400))
        from ..nikke_time import beijing_text
        stamp=beijing_text(expire_at)
        return f'Cookie预计约{days}天后到期（{stamp}）；官方可能提前使会话失效。需要更新时发送 {command_prefix()}重新登录（或 {command_prefix()}重新登陆）。'
    return f'官方未提供确切有效期；Cookie通常约30天，实际以官方会话为准。失效或需要更新时发送 {command_prefix()}重新登录（或 {command_prefix()}重新登陆）。'
