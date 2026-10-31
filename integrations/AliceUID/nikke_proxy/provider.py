"""Inactive egress-provider contracts: direct or one administrator-supplied proxy.

No HTTP calls, proxy discovery, automatic rotation, config reads or registration.
Existing login/client transports do not import this module.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Protocol, runtime_checkable
from urllib.parse import unquote, urlsplit


class Purpose(str, Enum):
    LOGIN = 'login'
    ACCOUNT_API = 'account_api'
    COMMUNITY = 'community'
    ANONYMOUS_RESOURCE = 'anonymous_resource'
    PUBLIC_CALENDAR = 'public_calendar'


_ACCOUNT_PURPOSES = frozenset({Purpose.LOGIN, Purpose.ACCOUNT_API, Purpose.COMMUNITY})
_OPAQUE_KEY = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')


@dataclass(frozen=True)
class ProxyRequest:
    purpose: Purpose
    # Caller supplies a stable opaque identity, never a login name/Cookie/token.
    account_key: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if not isinstance(self.purpose, Purpose):
            raise ValueError('unsupported egress purpose')
        if self.purpose in _ACCOUNT_PURPOSES:
            if not isinstance(self.account_key, str) or not _OPAQUE_KEY.fullmatch(self.account_key):
                raise ValueError('account traffic requires an opaque sticky account key')
        elif self.account_key is not None:
            raise ValueError('anonymous traffic must not carry an account key')


@dataclass(frozen=True)
class ProxyEndpoint:
    """Sensitive transport material, deliberately excluded from repr/str.

    Adapter-returned URL/dicts contain secrets; never log or serialize them.
    """
    url: str = field(repr=False)

    def __post_init__(self):
        try:
            if not isinstance(self.url, str) or any(char.isspace() or ord(char) < 32 for char in self.url):
                raise ValueError
            parts = urlsplit(self.url)
            if (parts.scheme not in {'http', 'https', 'socks5'} or not parts.hostname
                    or (parts.port is not None and not 1 <= parts.port <= 65535)
                    or parts.path not in {'', '/'} or parts.query or parts.fragment):
                raise ValueError
            if parts.scheme == 'socks5' and (parts.username is not None or parts.password is not None):
                # Playwright does not support authenticated SOCKS5 consistently.
                raise ValueError
        except (ValueError, TypeError, UnicodeError):
            raise ValueError('invalid configured proxy endpoint') from None

    def httpx_proxy(self) -> str:
        """Sensitive return value for future AsyncClient(proxy=...), not for logs."""
        return self.url

    def playwright_proxy(self) -> dict[str, str]:
        """Sensitive return value; split HTTP proxy credentials from server URL."""
        parts = urlsplit(self.url)
        result = {'server': f'{parts.scheme}://{parts.netloc.rsplit("@", 1)[-1]}'}
        if parts.username is not None:
            result['username'] = unquote(parts.username)
        if parts.password is not None:
            result['password'] = unquote(parts.password)
        return result


@dataclass(frozen=True)
class ProxyLease:
    node_id: str
    purpose: Purpose
    account_key: str | None = field(repr=False)
    endpoint: ProxyEndpoint | None = field(repr=False)
    lease_id: str = field(default_factory=lambda: uuid.uuid4().hex, repr=False)


class FeedbackKind(str, Enum):
    SUCCESS = 'success'
    NETWORK_ERROR = 'network_error'
    RATE_LIMITED = 'rate_limited'
    AUTHENTICATION = 'authentication'
    CAPTCHA = 'captcha'


class FeedbackAction(str, Enum):
    CONTINUE = 'continue'
    STOP_AND_REPORT = 'stop_and_report'


@dataclass(frozen=True)
class ProxyFeedback:
    # No arbitrary exception/response text: it may contain cookies or proxy secrets.
    kind: FeedbackKind
    status_code: int | None = None

    def __post_init__(self):
        if not isinstance(self.kind, FeedbackKind):
            raise ValueError('unsupported proxy feedback')
        if self.status_code is not None and (type(self.status_code) is not int or not 100 <= self.status_code <= 599):
            raise ValueError('invalid feedback status')


class ProxyStopped(RuntimeError):
    pass


@runtime_checkable
class ProxyProvider(Protocol):
    """Future pool implementations must preserve account -> node session affinity.

    acquire/release control a lease, not node reassignment. Login, validation and
    subsequent account requests must share a stable account mapping and exit IP.
    A failed/risk lease must stop/report, never rotate and replay automatically.
    """
    async def acquire(self, request: ProxyRequest) -> ProxyLease: ...
    async def release(self, lease: ProxyLease) -> None: ...
    async def report(self, lease: ProxyLease, feedback: ProxyFeedback) -> FeedbackAction: ...


class _FixedProvider:
    def __init__(self, endpoint: ProxyEndpoint | None, *, max_concurrency: int):
        if type(max_concurrency) is not int or not 1 <= max_concurrency <= 100:
            raise ValueError('invalid node concurrency limit')
        self._endpoint = endpoint
        self._account_node = 'legacy' if endpoint else 'direct'
        self._slots = {node: asyncio.Semaphore(max_concurrency) for node in {'direct', self._account_node}}
        self._active: dict[str, ProxyLease] = {}
        self._stopped_accounts: set[str] = set()
        self._feedback_counts: dict[str, int] = {}
        self.max_concurrency = max_concurrency

    def _check_stopped(self, request: ProxyRequest):
        if request.account_key in self._stopped_accounts:
            raise ProxyStopped('account egress stopped; explicit review required')

    async def acquire(self, request: ProxyRequest) -> ProxyLease:
        if not isinstance(request, ProxyRequest):
            raise ValueError('invalid egress request')
        self._check_stopped(request)
        account_traffic = request.purpose in _ACCOUNT_PURPOSES
        node_id = self._account_node if account_traffic else 'direct'
        endpoint = self._endpoint if account_traffic else None
        slots = self._slots[node_id]
        await slots.acquire()
        try:
            # A risk report may have arrived while this account waited for capacity.
            self._check_stopped(request)
            lease = ProxyLease(node_id, request.purpose, request.account_key, endpoint)
            self._active[lease.lease_id] = lease
            return lease
        except BaseException:
            slots.release()
            raise

    def _require_owned(self, lease: ProxyLease):
        if not isinstance(lease, ProxyLease) or self._active.get(lease.lease_id) is not lease:
            raise ValueError('unknown or released proxy lease')

    async def release(self, lease: ProxyLease) -> None:
        self._require_owned(lease)
        self._active.pop(lease.lease_id)
        self._slots[lease.node_id].release()

    async def report(self, lease: ProxyLease, feedback: ProxyFeedback) -> FeedbackAction:
        self._require_owned(lease)
        if not isinstance(feedback, ProxyFeedback):
            raise ValueError('invalid proxy feedback')
        self._feedback_counts[feedback.kind.value] = self._feedback_counts.get(feedback.kind.value, 0) + 1
        if feedback.kind is FeedbackKind.SUCCESS and (feedback.status_code is None or feedback.status_code < 400):
            return FeedbackAction.CONTINUE
        if lease.account_key is not None:
            # Process-local stop latch. No fallback to direct, no new proxy, no retry.
            self._stopped_accounts.add(lease.account_key)
        return FeedbackAction.STOP_AND_REPORT

    def diagnostics(self) -> dict:
        """Only non-sensitive counters, never endpoint URLs or account mappings."""
        return {
            'account_node_id': self._account_node,
            'max_concurrency_per_node': self.max_concurrency,
            'active_leases': len(self._active),
            'stopped_accounts': len(self._stopped_accounts),
            'feedback_counts': dict(self._feedback_counts),
        }


class DirectProvider(_FixedProvider):
    def __init__(self, *, max_concurrency: int = 2):
        super().__init__(None, max_concurrency=max_concurrency)


class LegacyProxyProvider(_FixedProvider):
    """One fixed administrator endpoint for account traffic; public assets stay direct.

    This adapter is NOT wired to AliceUID_Proxy or existing callers. Adoption must
    first cover the entire login -> validation -> account API session consistently.
    """
    def __init__(self, proxy_url: str, *, max_concurrency: int = 2):
        super().__init__(ProxyEndpoint(proxy_url), max_concurrency=max_concurrency)


def provider_from_legacy_proxy(proxy_url: str | None = None, *, max_concurrency: int = 2) -> ProxyProvider:
    """Explicit opt-in construction only; no global provider, config read or I/O."""
    if proxy_url is None or proxy_url == '':
        return DirectProvider(max_concurrency=max_concurrency)
    return LegacyProxyProvider(proxy_url, max_concurrency=max_concurrency)


@asynccontextmanager
async def leased(provider: ProxyProvider, request: ProxyRequest) -> AsyncIterator[ProxyLease]:
    lease = await provider.acquire(request)
    try:
        yield lease
    finally:
        await provider.release(lease)
