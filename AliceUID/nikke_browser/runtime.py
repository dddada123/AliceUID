"""Reuse the host driver and repair only its missing browser binaries."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.metadata import version
from typing import TYPE_CHECKING, AsyncIterator, Awaitable, Callable, TypedDict

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

log = logging.getLogger(__name__)
WAIT_SECONDS = 120
INSTALL_SECONDS = 900
COOLDOWN_SECONDS = 300
_OFF = {"0", "false", "no", "off"}


class BrowserUnavailable(RuntimeError):
    """A credential-free message suitable for the user-facing entry points."""


class LaunchOptions(TypedDict, total=False):
    headless: bool
    channel: str
    proxy: dict[str, str]


@asynccontextmanager
async def playwright(*, error_type: type[Exception] = BrowserUnavailable) -> AsyncIterator[Playwright]:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        if exc.name not in {"playwright", "playwright.async_api"}:
            raise
        raise error_type("Core运行环境缺少Playwright，请管理员安装插件依赖后重启Core。") from None
    from playwright.async_api import Error
    try:
        async with async_playwright() as driver:
            yield driver
    except BrowserUnavailable as exc:
        raise error_type(str(exc)) from None
    except Error as exc:
        raise error_type(failure_message(str(exc))) from None


def missing_binary(message: str) -> bool:
    return "Executable doesn't exist at" in message


def failure_message(message: str) -> str:
    text = message.lower()
    if "no space left" in text or "enospc" in text:
        return "浏览器安装失败：磁盘空间不足，请管理员清理空间后重试。"
    if any(word in text for word in ("permission denied", "eacces", "read-only", "erofs")):
        return "浏览器目录不可写，请管理员检查容器挂载和运行用户权限。"
    if any(word in text for word in ("missing dependencies", "error while loading shared libraries", "host system is missing")):
        return "浏览器缺少系统依赖，请管理员在Core容器内安装Chromium系统依赖。"
    if "lock" in text and any(word in text for word in ("held", "locked", "eexist")):
        return "其他任务正在安装浏览器，请稍后重试。"
    return "浏览器组件下载或启动失败，请管理员检查容器网络、下载源和浏览器安装。"


@dataclass(frozen=True)
class InstallResult:
    success: bool
    message: str = ""


async def _stop_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/PID", str(proc.pid), "/T", "/F",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        await killer.wait()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await proc.wait()


async def install_chromium() -> InstallResult:
    """Do not log installer output: proxy/download URLs can contain credentials."""
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt"
               else {"start_new_session": True})
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "playwright", "install", "chromium",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **options,
        )
    except OSError as exc:
        return InstallResult(False, failure_message(str(exc)))
    tail = bytearray()

    async def collect() -> int:
        assert proc.stdout is not None
        while chunk := await proc.stdout.read(4096):
            tail.extend(chunk)
            del tail[:-16384]
        return await proc.wait()

    reader = asyncio.create_task(collect())
    try:
        code = await asyncio.wait_for(asyncio.shield(reader), INSTALL_SECONDS)
        return InstallResult(code == 0, "" if code == 0 else failure_message(tail.decode("utf-8", "replace")))
    except asyncio.TimeoutError:
        return InstallResult(False, "浏览器组件下载超时，请管理员检查网络后稍后重试。")
    finally:
        await _stop_tree(proc)
        await asyncio.gather(reader, return_exceptions=True)


class BrowserManager:
    def __init__(self, *, enabled: Callable[[], bool] = lambda: False,
                 installer: Callable[[], Awaitable[InstallResult]] = install_chromium,
                 clock: Callable[[], float] = time.monotonic):
        self.enabled = enabled
        self.installer = installer
        self.clock = clock
        self.task: asyncio.Task[InstallResult] | None = None
        self.task_key: tuple[str, str, str] | None = None
        self.failure = ""
        self.retry_at = 0.0
        self.stopping = False
        self.warmup: asyncio.Task | None = None

    def allowed(self) -> bool:
        return self.enabled() and os.environ.get("GSUID_PLAYWRIGHT_AUTOINSTALL", "").lower().strip() not in _OFF

    async def _install(self) -> InstallResult:
        result = await self.installer()
        if not result.success:
            self.failure = result.message
            self.retry_at = self.clock() + COOLDOWN_SECONDS
            log.warning("[AliceUID] %s", result.message)
        return result

    async def repair(self, observed: asyncio.Task[InstallResult] | None = None) -> None:
        if self.stopping:
            raise BrowserUnavailable("Core正在关闭，请稍后重试。")
        if not self.allowed():
            raise BrowserUnavailable("缺少配套Chromium，自动补装已关闭，请管理员手动安装浏览器。")
        key = (sys.executable, version("playwright"), os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
        if self.task_key != key and self.task is not None and not self.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.task), WAIT_SECONDS)
            except asyncio.TimeoutError:
                raise BrowserUnavailable("浏览器组件仍在准备，请稍后在原页面重试。") from None
        if key != self.task_key:
            self.retry_at = 0
            self.failure = ""
            self.task = None
            self.task_key = key
        if self.clock() < self.retry_at:
            raise BrowserUnavailable(self.failure + "请等待5分钟后重试。")
        if self.task is None or (self.task.done() and self.task is observed):
            # A successful installer alone is not readiness. The caller relaunches.
            self.task = asyncio.create_task(self._install())
        try:
            result = await asyncio.wait_for(asyncio.shield(self.task), WAIT_SECONDS)
        except asyncio.TimeoutError:
            raise BrowserUnavailable("浏览器组件仍在准备，请稍后在原页面重试。") from None
        if not result.success:
            raise BrowserUnavailable(result.message) from None

    async def launch(self, driver: Playwright, *, channel: str = "auto", headless: bool = True,
                     proxy: str = "") -> Browser:
        from playwright.async_api import Error

        choices = (None, "msedge") if channel == "auto" else ((None,) if channel == "chromium" else ("msedge",))
        last_message = "浏览器启动失败，请管理员检查浏览器安装。"
        for candidate in choices:
            observed = self.task if self.task is not None and self.task.done() else None
            kwargs: LaunchOptions = {"headless": headless}
            if candidate is not None:
                kwargs["channel"] = candidate
            if proxy:
                kwargs["proxy"] = {"server": proxy}
            try:
                return await driver.chromium.launch(**kwargs)
            except Error as exc:
                if candidate == "msedge" and "Chromium distribution 'msedge' is not found" in str(exc):
                    if channel == "msedge":
                        last_message = "所选Edge浏览器未安装，请管理员安装Edge或将浏览器通道改为auto。"
                    continue
                if candidate is None and missing_binary(str(exc)):
                    try:
                        await self.repair(observed)
                        return await driver.chromium.launch(**kwargs)
                    except BrowserUnavailable as repair_error:
                        last_message = str(repair_error)
                    except Error as retry_error:
                        last_message = failure_message(str(retry_error))
                        self.failure = last_message
                        self.retry_at = self.clock() + COOLDOWN_SECONDS
                elif candidate is not None and missing_binary(str(exc)):
                    if channel == "msedge":
                        last_message = "所选Edge浏览器未安装，请管理员安装Edge或将浏览器通道改为auto。"
                else:
                    last_message = failure_message(str(exc))
        raise BrowserUnavailable(last_message) from None

    async def prepare(self, *, channel: str = "auto", headless: bool = True) -> None:
        async def probe() -> None:
            async with playwright() as driver:
                browser = await self.launch(driver, channel=channel, headless=headless)
                await browser.close()
        try:
            await asyncio.wait_for(probe(), WAIT_SECONDS)
        except asyncio.TimeoutError:
            raise BrowserUnavailable("浏览器组件仍在准备，请稍后在原页面重试。") from None

    async def shutdown(self) -> None:
        self.stopping = True
        tasks = [task for task in (self.warmup, self.task) if task is not None and not task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


manager = BrowserManager()


def setup(config_getter: Callable[[str], object]) -> None:
    from gsuid_core.server import on_core_shutdown, on_core_start

    manager.enabled = lambda: bool(config_getter("AliceUID_BrowserAutoInstall"))

    async def warmup() -> None:
        try:
            await manager.prepare(channel=str(config_getter("AliceUID_BrowserChannel") or "auto"),
                                  headless=bool(config_getter("AliceUID_Headless")))
        except BrowserUnavailable as exc:
            log.warning("[AliceUID] %s", exc)

    @on_core_start
    async def prepare_browser() -> None:
        manager.warmup = asyncio.create_task(warmup())

    @on_core_shutdown
    async def close_browser_installer() -> None:
        await manager.shutdown()
