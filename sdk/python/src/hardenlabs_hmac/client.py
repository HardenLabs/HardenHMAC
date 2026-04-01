"""Client-side request signing and HTTP client factory for HardenHMAC."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from hardenlabs_hmac.canonical import build_canonical_string, build_signed_headers
from hardenlabs_hmac.config import (
    CLIENT_ID_HEADER,
    SIGNATURE_HEADER,
    SIGNED_HEADERS_HEADER,
    TIMESTAMP_HEADER,
    HmacConfig,
)
from hardenlabs_hmac.signing import sign

try:
    import httpx as _httpx

    _BaseTransport = _httpx.BaseTransport
    _AsyncBaseTransport = _httpx.AsyncBaseTransport
except ImportError:  # httpx is an optional dependency
    _httpx = None  # type: ignore[assignment]
    _BaseTransport = object  # type: ignore[assignment,misc]
    _AsyncBaseTransport = object  # type: ignore[assignment,misc]

try:
    import requests as _requests_lib
    from requests.auth import AuthBase as _AuthBase

    _HAS_REQUESTS = True
except ImportError:
    _requests_lib = None  # type: ignore[assignment]
    _AuthBase = object  # type: ignore[assignment,misc]
    _HAS_REQUESTS = False

if TYPE_CHECKING:
    import httpx
    import requests as requests_mod


def sign_request_headers(
    config: HmacConfig,
    method: str,
    path: str,
    body: str = "",
    request_headers: dict[str, str] | None = None,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Compute HMAC signing headers for an outgoing request.

    Args:
        config: HMAC configuration with shared secret.
        method: HTTP method.
        path: Request path including query string.
        body: Request body (empty string if none).
        request_headers: Existing request headers for signed header selection.
        timestamp: Unix timestamp (if None, uses current time).

    Returns:
        Dictionary of headers to add to the request
        (X-Harden-Signature, X-Harden-Timestamp, optionally X-Harden-Signed-Headers).
    """
    ts = timestamp if timestamp is not None else int(time.time())
    headers = request_headers or {}

    _, header_names = build_signed_headers(config.signed_headers, headers)

    canonical_string = build_canonical_string(
        method, path, body, ts, config.signed_headers, headers
    )

    signature = sign(config.shared_secret_base64, canonical_string)

    result: dict[str, str] = {
        SIGNATURE_HEADER: signature,
        TIMESTAMP_HEADER: str(ts),
    }

    if header_names:
        result[SIGNED_HEADERS_HEADER] = ";".join(header_names)

    return result


class HmacTransport(_BaseTransport):
    """httpx transport that automatically signs outgoing requests with HMAC.

    Used internally by HmacClientFactory. Wraps an existing transport.
    Optionally adds an X-Harden-Client-Id header to identify the client to the server.
    """

    def __init__(
        self,
        config: HmacConfig,
        transport: httpx.BaseTransport,
        client_id: str | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._client_id = client_id

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Sign the request and delegate to the inner transport."""
        # Add X-Harden-Client-Id if configured
        if self._client_id:
            request.headers[CLIENT_ID_HEADER] = self._client_id

        path = request.url.raw_path.decode("ascii")
        method = request.method
        body = request.content.decode("utf-8") if request.content else ""

        existing_headers: dict[str, str] = {}
        for name, value in request.headers.items():
            existing_headers[name] = value

        sig_headers = sign_request_headers(
            self._config, method, path, body, existing_headers
        )

        for name, value in sig_headers.items():
            request.headers[name] = value

        return self._transport.handle_request(request)


class HmacAsyncTransport(_AsyncBaseTransport):
    """httpx async transport that automatically signs outgoing requests with HMAC.

    Used internally by HmacClientFactory. Wraps an existing async transport.
    Optionally adds an X-Harden-Client-Id header to identify the client to the server.
    """

    def __init__(
        self,
        config: HmacConfig,
        transport: httpx.AsyncBaseTransport,
        client_id: str | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._client_id = client_id

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Sign the request and delegate to the inner transport."""
        # Add X-Harden-Client-Id if configured
        if self._client_id:
            request.headers[CLIENT_ID_HEADER] = self._client_id

        path = request.url.raw_path.decode("ascii")
        method = request.method
        body = request.content.decode("utf-8") if request.content else ""

        existing_headers: dict[str, str] = {}
        for name, value in request.headers.items():
            existing_headers[name] = value

        sig_headers = sign_request_headers(
            self._config, method, path, body, existing_headers
        )

        for name, value in sig_headers.items():
            request.headers[name] = value

        return await self._transport.handle_async_request(request)


class HmacAuth(_AuthBase):
    """requests auth adapter that signs outgoing requests with HMAC.

    This is the standard ``requests`` extension point for authentication.
    Attach to a ``requests.Session`` via ``session.auth = HmacAuth(config)``,
    or pass per-request via ``session.get(url, auth=HmacAuth(config))``.

    Optionally sets an ``X-Harden-Client-Id`` header to identify the caller.
    """

    def __init__(self, config: HmacConfig, client_id: str | None = None) -> None:
        self.config = config
        self.client_id = client_id

    def __call__(self, r: requests_mod.PreparedRequest) -> requests_mod.PreparedRequest:
        """Sign the prepared request and return it."""
        if self.client_id:
            r.headers[CLIENT_ID_HEADER] = self.client_id  # type: ignore[index]

        # Parse path + query from the full URL
        parsed = urlparse(r.url or "")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        method = (r.method or "GET").upper()

        # Resolve body to a string
        body: str
        if r.body is None:
            body = ""
        elif isinstance(r.body, bytes):
            body = r.body.decode("utf-8")
        elif isinstance(r.body, str):
            body = r.body
        else:
            raise TypeError(
                f"Unsupported request body type: {type(r.body).__name__}. "
                "HmacAuth supports str, bytes, and None."
            )

        # Collect existing headers for signed-header selection
        existing_headers: dict[str, str] = {
            k: v for k, v in (r.headers or {}).items() if isinstance(v, str)
        }

        sig_headers = sign_request_headers(
            self.config, method, path, body, existing_headers
        )

        for name, value in sig_headers.items():
            r.headers[name] = value  # type: ignore[index]

        return r


class HmacRequestsClient:
    """Wrapper around ``requests.Session`` with base URL and HMAC signing.

    ``requests.Session`` does not natively support base URLs, so this wrapper
    prepends the target's base URL to every request path.
    """

    def __init__(self, session: requests_mod.Session, base_url: str) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed GET request."""
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed POST request."""
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed PUT request."""
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed PATCH request."""
        return self.session.patch(f"{self.base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed DELETE request."""
        return self.session.delete(f"{self.base_url}{path}", **kwargs)

    def head(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed HEAD request."""
        return self.session.head(f"{self.base_url}{path}", **kwargs)

    def options(self, path: str, **kwargs: Any) -> requests_mod.Response:
        """Send a signed OPTIONS request."""
        return self.session.options(f"{self.base_url}{path}", **kwargs)

    def close(self) -> None:
        """Close the underlying session."""
        self.session.close()

    def __enter__(self) -> HmacRequestsClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class HmacClientFactory:
    """Factory for creating pre-configured HTTP clients that auto-sign requests.

    Supports httpx (sync + async) and requests (sync via ``create_requests_session``).
    Each client is configured with the base URL and shared secret from the
    named target in the config.
    """

    def __init__(self, config: HmacConfig) -> None:
        self._config = config

    def create_client(self, target_name: str) -> httpx.AsyncClient:
        """Create an async HTTP client for the named target.

        Args:
            target_name: The target name as defined in config.targets.

        Returns:
            httpx.AsyncClient with base_url set and auto-signing transport.

        Raises:
            KeyError: If the target is not configured.
        """
        import httpx as httpx_mod

        target = self._get_target(target_name)
        effective_config = self._config.for_target(target_name)

        transport = HmacAsyncTransport(
            effective_config,
            httpx_mod.AsyncHTTPTransport(),
            client_id=target_name,
        )

        return httpx_mod.AsyncClient(
            base_url=target.base_url,
            transport=transport,
        )

    def create_sync_client(self, target_name: str) -> httpx.Client:
        """Create a sync HTTP client for the named target.

        Args:
            target_name: The target name as defined in config.targets.

        Returns:
            httpx.Client with base_url set and auto-signing transport.

        Raises:
            KeyError: If the target is not configured.
        """
        import httpx as httpx_mod

        target = self._get_target(target_name)
        effective_config = self._config.for_target(target_name)

        transport = HmacTransport(
            effective_config,
            httpx_mod.HTTPTransport(),
            client_id=target_name,
        )

        return httpx_mod.Client(
            base_url=target.base_url,
            transport=transport,
        )

    def create_requests_session(self, target_name: str) -> HmacRequestsClient:
        """Create a requests-based HTTP client for the named target.

        Returns an ``HmacRequestsClient`` that wraps a ``requests.Session``
        with base URL prepending and automatic HMAC signing.

        Args:
            target_name: The target name as defined in config.targets.

        Returns:
            HmacRequestsClient with base_url set and HmacAuth configured.

        Raises:
            ImportError: If the ``requests`` library is not installed.
            KeyError: If the target is not configured.
        """
        if not _HAS_REQUESTS:
            raise ImportError(
                "requests is required for create_requests_session. "
                "Install with: pip install 'hardenlabs-hmac[requests]'"
            )
        import requests as requests_mod

        target = self._get_target(target_name)
        effective_config = self._config.for_target(target_name)

        session = requests_mod.Session()
        session.auth = HmacAuth(effective_config, client_id=target_name)

        return HmacRequestsClient(session, target.base_url)

    def _get_target(self, target_name: str) -> "HmacTargetConfig":
        """Look up a target, raising KeyError if not found."""
        from hardenlabs_hmac.config import HmacTargetConfig

        if target_name not in self._config.targets:
            available = ", ".join(self._config.targets.keys())
            raise KeyError(
                f"Target '{target_name}' is not configured. "
                f"Available targets: [{available}]."
            )
        return self._config.targets[target_name]
