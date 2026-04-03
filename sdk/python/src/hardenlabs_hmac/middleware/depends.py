"""FastAPI dependency for per-route HardenHMAC request validation."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from hardenlabs_hmac.config import CLIENT_ID_HEADER, HmacConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.validation import validate_request

logger = logging.getLogger("hardenlabs_hmac.middleware")

# Same type alias as in the global middleware.
SecretResolver = Callable[[Request], Awaitable[str | None]]


class HmacValidationHttpError(Exception):
    """Raised by :class:`HmacValidate` when HMAC validation fails.

    Carries an HTTP status code and a JSON-serialisable error body that
    matches the format used by :class:`HardenHmacMiddleware`::

        {"error": "<error_type>", "message": "<description>"}

    Register the companion handler with
    :func:`install_hmac_exception_handler` so FastAPI serialises the
    response correctly.
    """

    def __init__(self, status_code: int, error: str, message: str) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(f"{error}: {message}")


def install_hmac_exception_handler(app: FastAPI) -> None:
    """Register the exception handler for :class:`HmacValidationHttpError`.

    Call this once on your FastAPI application so that validation failures
    from :class:`HmacValidate` are returned as JSON responses matching the
    global middleware format::

        app = FastAPI()
        install_hmac_exception_handler(app)
    """

    @app.exception_handler(HmacValidationHttpError)
    async def _handler(request: Request, exc: HmacValidationHttpError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "message": exc.message},
        )


class HmacValidate:
    """FastAPI dependency that validates HMAC signatures on a per-route basis.

    Use with ``Depends()`` to protect individual endpoints instead of applying
    global middleware::

        config = HmacConfig(shared_secret_base64="...")
        hmac_validate = HmacValidate(config)

        app = FastAPI()
        install_hmac_exception_handler(app)

        @app.post("/api/orders")
        async def create_order(request: Request, hmac=Depends(hmac_validate)):
            return {"status": "ok"}

    Args:
        config: HMAC configuration with shared secret and tolerance.
        secret_resolver: Optional async callback that resolves the shared secret
            per-request.  If it returns ``None``, the resolver falls back to
            looking up the client from the ``X-Harden-Client-Id`` header in
            ``config.clients``, and then (if no client ID is provided) to
            ``config.shared_secret_base64``.  If ``X-Harden-Client-Id`` is
            present but does not match a configured client, validation fails
            with an ``unknown_client`` error and does not fall back to
            ``config.shared_secret_base64``.
    """

    def __init__(
        self,
        config: HmacConfig,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        self.config = config
        self.secret_resolver = secret_resolver

    async def __call__(self, request: Request) -> None:
        """Validate the HMAC signature on the incoming request.

        Raises:
            HmacValidationHttpError: 400 for missing/malformed headers, 401 for
                authentication failures.
        """
        body_bytes = await request.body()
        try:
            body = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise HmacValidationHttpError(
                status_code=400,
                error="invalid_body_encoding",
                message="Request body is not valid UTF-8.",
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

        signature_header = request.headers.get("x-harden-signature")
        timestamp_header = request.headers.get("x-harden-timestamp")

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
            raise HmacValidationHttpError(
                status_code=401,
                error=error_type,
                message=error_message,
            )

        if not effective_secret:
            logger.warning(
                "HMAC validation failed: no shared secret configured or resolved for %s %s",
                request.method,
                path,
            )
            raise HmacValidationHttpError(
                status_code=401,
                error="no_secret",
                message="No shared secret configured for this request.",
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
            raise HmacValidationHttpError(
                status_code=status_code,
                error=e.error_type,
                message=e.message,
            )

        logger.debug(
            "HMAC validation succeeded for %s %s", request.method, path
        )

    async def _resolve_secret(
        self, request: Request
    ) -> tuple[str | None, tuple[str, str] | None]:
        """Resolve the effective shared secret for this request.

        Returns:
            Tuple of (secret, error).  If error is not None, the request should
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
