"""HTML → PNG：优先外置渲染，失败回退 GsCore 原生渲染接口。"""
from __future__ import annotations

import httpx
import asyncio
from weakref import WeakKeyDictionary

_render_slots = WeakKeyDictionary()

from gsuid_core.logger import logger

from ..nikke_config.config import AliceUIDConfig


async def _remote_render(html: str, url: str, token: str, timeout: int) -> bytes | None:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json={"html": html}, headers=headers)
        if resp.status_code == 200 and resp.content.startswith(b'\x89PNG\r\n\x1a\n'):
            from ..nikke_resource.cache import validate_image
            validate_image(resp.content)
            logger.info(f"[AliceUID] 外置渲染成功: {len(resp.content)} bytes")
            return resp.content
        logger.warning(f"[AliceUID] 外置渲染未返回有效PNG: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[AliceUID] 外置渲染异常，回退本地: {type(exc).__name__}")
    return None


async def _render_html(
    html: str,
    *,
    root_width: int = 1000,
    dpi: int | None = None,
) -> bytes:
    """把 HTML 渲染成 PNG。

    root_width 是模板的 CSS 设计宽度；dpi=144 表示 1.5 倍输出。
    """
    dpi = int(dpi or AliceUIDConfig.get_config("AliceUID_RenderDpi").data or 144)
    max_width = int(root_width * dpi / 96)

    from .fonts import resolve_font, apply_font_html, register_native_font, FALLBACK
    selected = resolve_font()
    if selected.reason:
        logger.warning('[AliceUID] 卡片字体不可读，自动使用黑体兜底')

    if bool(AliceUIDConfig.get_config("AliceUID_RemoteRenderEnable").data):
        url = str(AliceUIDConfig.get_config("AliceUID_RemoteRenderUrl").data or "").strip()
        token = str(AliceUIDConfig.get_config("AliceUID_RemoteRenderToken").data or "").strip()
        timeout = int(AliceUIDConfig.get_config("AliceUID_RenderTimeout").data or 60)
        if url:
            result = await _remote_render(apply_font_html(html, selected), url, token, timeout)
            if result is not None:
                return result
            logger.info("[AliceUID] 外置渲染不可用，使用本地渲染")

    from gsuid_core.utils import html_render as core_render
    if selected.custom:
        try:
            renderer = core_render._ensure_renderer()
            registered = register_native_font(renderer, selected)
        except Exception:
            registered = False
        if not registered:
            logger.warning('[AliceUID] 原生字体注册失败，自动使用黑体兜底')
            selected = resolve_font(FALLBACK)

    return await core_render.render_html_to_bytes(
        apply_font_html(html, selected, embed=False),
        font_name=selected.family,
        max_width=max_width,
        dpi=dpi,
        root_max_width=root_width,
        image_format="png",
        allow_refit=True,
    )


async def render_html(html: str, *, root_width: int = 1000, dpi: int | None = None) -> bytes:
    """Cache hits never enter this bounded paint queue."""
    loop = asyncio.get_running_loop()
    gate = _render_slots.setdefault(loop, asyncio.Semaphore(2))
    async with gate:
        return await _render_html(html, root_width=root_width, dpi=dpi)
