"""用户绑定表：一个 QQ 用户对应一个 NIKKE 账号。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, update
from sqlmodel import Field

from gsuid_core.utils.database.base_models import Bind, with_session


class AliceBind(Bind, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    intl_open_id: Optional[str] = Field(default=None, title="国际服 openid")
    area_id: int = Field(default=81, title="区服编号")
    game_id: str = Field(default="29080", title="游戏 ID")
    cookie_enc: str = Field(default="", title="加密后的 Cookie")
    nickname: str = Field(default="", title="游戏昵称")
    uid: str = Field(default="", title="游戏 UID")
    cookie_expire: int = Field(default=0, title="Cookie 过期时间")
    is_public: bool = Field(default=False, title="是否参与群排行")
    is_master: bool = Field(default=False, title="是否 Bot 主账号")

    @classmethod
    async def get_bind(cls, user_id: str, bot_id: str) -> Optional["AliceBind"]:
        return await cls.select_data(user_id, bot_id)

    @classmethod
    async def save_bind(
        cls,
        user_id: str,
        bot_id: str,
        group_id: Optional[str],
        *,
        openid: str,
        area_id: int,
        game_id: str,
        cookie_enc: str,
        nickname: str,
        uid: str,
        cookie_expire: int,
        is_master: bool = False,
    ) -> int:
        data = {
            "intl_open_id": openid,
            "area_id": area_id,
            "game_id": game_id,
            "cookie_enc": cookie_enc,
            "nickname": nickname,
            "uid": uid,
            "cookie_expire": cookie_expire,
            "is_master": is_master,
        }
        exists = await cls.select_data(user_id, bot_id)
        if exists:
            return await cls.update_data(user_id, bot_id, **data)
        return await cls.insert_data(
            user_id=user_id, bot_id=bot_id, group_id=group_id, **data
        )

    @classmethod
    async def delete_bind(cls, user_id: str, bot_id: str, *, expected_revision: str = '') -> int:
        from ..nikke_community.runtime import revoke_binding
        from .service import binding_lock
        # Acquire only here: the session helper must never acquire binding_lock.
        async with binding_lock(user_id, bot_id):
            bind = await cls.get_bind(user_id, bot_id)
            if expected_revision:
                import hashlib
                if bind is None or hashlib.sha256(bind.cookie_enc.encode()).hexdigest() != expected_revision:
                    raise ValueError('绑定已变化，请刷新管理页后重新确认')
            revoke_binding(bind)
            from ..nikke_harvest.runtime import revoke_binding as revoke_harvest
            revoke_harvest(bind)
            result = await cls._delete_binding_rows(user_id, bot_id)
            if result != 0 or await cls.get_bind(user_id, bot_id) is not None:
                raise RuntimeError("绑定删除未完成")
            return result

    @classmethod
    @with_session
    async def admin_record(cls, session: AsyncSession, record_id: int):
        result = await session.scalars(select(cls).where(cls.id == record_id))
        return result.first()

    @classmethod
    @with_session
    async def replace_cookie(cls, session: AsyncSession, user_id: str, bot_id: str, *,
                             expected_cookie: str, openid: str, area_id: int, game_id: str,
                             cookie_enc: str, nickname: str, uid: str, cookie_expire: int) -> int:
        # An owner-scoped compare-and-swap; never delete/insert or switch account.
        result=await session.execute(update(cls).where(
            cls.user_id==user_id,cls.bot_id==bot_id,cls.cookie_enc==expected_cookie,
            cls.intl_open_id==openid,cls.area_id==area_id,cls.game_id==game_id,
        ).values(cookie_enc=cookie_enc,nickname=nickname,uid=uid,cookie_expire=cookie_expire))
        return 0 if result.rowcount==1 else 1

    @classmethod
    @with_session
    async def _delete_binding_rows(
        cls: Type["AliceBind"], session: AsyncSession, user_id: str, bot_id: str
    ) -> int:
        # Core BaseModel.delete_data constructs a transient object then calls
        # session.delete(), which SQLAlchemy rejects. Use an explicit predicate
        # to delete all rows for this owner, including historical duplicates.
        await session.execute(
            delete(cls).where(cls.user_id == user_id, cls.bot_id == bot_id)
        )
        return 0

    @classmethod
    @with_session
    async def get_public_binds(cls: Type["AliceBind"], session: AsyncSession) -> List["AliceBind"]:
        result = await session.scalars(select(cls).where(cls.is_public == True))  # noqa: E712
        return list(result.all())

    @classmethod
    @with_session
    async def get_all_binds(cls: Type["AliceBind"], session: AsyncSession) -> List["AliceBind"]:
        result = await session.scalars(select(cls))
        return list(result.all())
