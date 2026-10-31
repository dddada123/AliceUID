"""Background source extension point. Only local card_bg is enabled today."""
from __future__ import annotations
from pathlib import Path
from typing import Protocol

LOCAL_ROOT=Path(__file__).resolve().parents[2]/'card_bg'


class BackgroundProvider(Protocol):
    source_name: str
    def candidates(self,theme: str)->tuple[Path,...]: ...
    async def prepare(self,theme: str)->tuple[Path,...]: ...


class LocalBackgroundProvider:
    source_name='local-card-bg'
    def __init__(self,root=None):self.root=Path(root) if root else LOCAL_ROOT
    def candidates(self,theme):
        if theme not in ('dark','light'):raise ValueError('unknown background theme')
        prefix='暗色背景' if theme=='dark' else '亮色背景'
        return tuple(sorted(path for path in self.root.glob(prefix+'*.jpg') if path.is_file()))
    async def prepare(self,theme):return self.candidates(theme)


class OnlineBackgroundProviderReserved:
    """Future implementation must cache reviewed downloads before rendering.

    No URL, credentials, network call, config activation or automatic fallback is
    implemented here. Reserved prepare() is the asynchronous download boundary.
    """
    source_name='online-reserved-disabled'
    def candidates(self,theme):return ()
    async def prepare(self,theme):
        raise NotImplementedError('在线背景仅预留接口，当前未启用')


_provider: BackgroundProvider=LocalBackgroundProvider()


def get_background_provider():return _provider


def register_background_provider(provider: BackgroundProvider):
    """Trusted code extension, not a public arbitrary-URL API."""
    global _provider
    if not callable(getattr(provider,'candidates',None)) or not callable(getattr(provider,'prepare',None)):
        raise TypeError('background provider contract incomplete')
    _provider=provider
