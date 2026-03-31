"""Client-side request signing and HTTP client factory for HardenHMAC."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from hardenlabs_hmac.canonical import build_canonical_string, build_signed_headers
from hardenlabs_hmac.config import (
    CLIENT_ID_HEADER,
    SIGNATURE_HEADER,
    SIGNED_HEADERS_HEADER,
    TIMESTAMP_HEADER,
    HmacConfig,
)
from hardenlabs_hmac.signing import sign

if TYPE_CHECKING:
    import httpx


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


class HmacTransport:
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


class HmacAsyncTransport:
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


class HmacClientFactory:
    """Factory for creating pre-configured httpx clients that auto-sign requests.

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
