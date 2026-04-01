"""FastAPI/Starlette middleware for HardenHMAC request validation."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from hardenlabs_hmac.config import CLIENT_ID_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER, HmacConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.validation import validate_request

logger = logging.getLogger("hardenlabs_hmac.middleware")

# Type alias for the optional secret resolver callback.
# Given a Starlette Request, returns the Base64-encoded shared secret or None.
SecretResolver = Callable[[Request], Awaitable[str | None]]


class HardenHmacMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that validates incoming HMAC-signed requests.

    Supports a static shared secret from config and/or a dynamic secret resolver
    callback for multi-tenant scenarios.

    Args:
        app: The ASGI application.
        config: HMAC configuration with shared secret and tolerance.
        secret_resolver: Optional async callback that resolves the shared secret
            per-request. If it returns None, falls back to config.shared_secret_base64.
    """

    def __init__(
        self,
        app: ASGIApp,
        config: HmacConfig,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        super().__init__(app)
        self.config = config
        self.secret_resolver = secret_resolver

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        body_bytes = await request.body()
        try:
            body = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_body_encoding",
                    "message": "Request body is not valid UTF-8.",
                },
            )

        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"

        # Extract headers as dict, comma-joining duplicate header names
        # per RFC 9110 Section 5.2
        request_headers: dict[str, str] = {}
        for name, value in request.headers.items():
            if name in request_headers:
                request_headers[name] = request_headers[name] + ", " + value
            else:
                request_headers[name] = value

        signature_header = request.headers.get(SIGNATURE_HEADER.lower())
        timestamp_header = request.headers.get(TIMESTAMP_HEADER.lower())

        # Resolve secret: try resolver, then Clients dict, then config fallback
        effective_secret, resolve_error = await self._resolve_secret(request)

        if resolve_error is not None:
            error_type, error_message = resolve_error
            logger.warning(
                "HMAC validation failed: %s for %s %s",
                error_type,
                request.method,
                path,
            )
            return JSONResponse(
                status_code=401,
                content={"error": error_type, "message": error_message},
            )

        if not effective_secret:
            logger.warning(
                "HMAC validation failed: no shared secret configured or resolved for %s %s",
                request.method,
                path,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "no_secret",
                    "message": "No shared secret configured for this request.",
                },
            )

        # Build a config with the resolved secret
        validation_config = HmacConfig(
            shared_secret_base64=effective_secret,
            signed_headers=self.config.signed_headers,
            timestamp_tolerance_seconds=self.config.timestamp_tolerance_seconds,
        )

        try:
            validate_request(
                config=validation_config,
                method=request.method,
                path=path,
                body=body,
                signature_header=signature_header,
                timestamp_header=timestamp_header,
                request_headers=request_headers,
            )
        except HmacValidationError as e:
            logger.warning(
                "HMAC validation failed: %s - %s", e.error_type, e.message
            )
            status_code = 400 if e.error_type in (
                "missing_signature", "missing_timestamp", "invalid_timestamp"
            ) else 401
            return JSONResponse(
                status_code=status_code,
                content={"error": e.error_type, "message": e.message},
            )

        logger.debug(
            "HMAC validation succeeded for %s %s", request.method, path
        )
        return await call_next(request)

    async def _resolve_secret(self, request: Request) -> tuple[str | None, tuple[str, str] | None]:
        """Resolve the effective shared secret for this request.

        Returns:
            Tuple of (secret, error). If error is not None, the request should
            be rejected with a 401 containing the error tuple (error_type, message).
        """
        # 1. secretResolver callback (if provided) takes highest priority
        if self.secret_resolver is not None:
            resolved = await self.secret_resolver(request)
            if resolved:
                return resolved, None

        # 2. X-Harden-Client-Id header -> look up in config.clients
        client_id = request.headers.get(CLIENT_ID_HEADER.lower())
        if client_id:
            if client_id in self.config.clients:
                client_identity = self.config.clients[client_id]
                if client_identity.shared_secret:
                    return client_identity.shared_secret, None
            # Client ID was provided but not found in clients dictionary
            return None, ("unknown_client", "Unknown or unconfigured client.")

        # 3. Fall back to config.shared_secret_base64
        return self.config.shared_secret_base64 or None, None
