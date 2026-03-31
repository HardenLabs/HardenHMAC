"""FastAPI/Starlette middleware for HardenHMAC request validation."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from hardenlabs_hmac.config import SIGNATURE_HEADER, TIMESTAMP_HEADER, HmacConfig
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
        body = body_bytes.decode("utf-8")

        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"

        # Extract headers as dict
        request_headers: dict[str, str] = {}
        for name, value in request.headers.items():
            request_headers[name] = value

        signature_header = request.headers.get(SIGNATURE_HEADER.lower())
        timestamp_header = request.headers.get(TIMESTAMP_HEADER.lower())

        # Resolve secret: try resolver first, then fall back to config
        effective_secret = await self._resolve_secret(request)

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

    async def _resolve_secret(self, request: Request) -> str | None:
        """Resolve the effective shared secret for this request."""
        if self.secret_resolver is not None:
            resolved = await self.secret_resolver(request)
            if resolved:
                return resolved

        return self.config.shared_secret_base64 or None
