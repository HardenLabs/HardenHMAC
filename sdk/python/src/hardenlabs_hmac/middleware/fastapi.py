"""FastAPI/Starlette middleware for HardenHMAC request validation."""

import json
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from hardenlabs_hmac.config import SIGNATURE_HEADER, TIMESTAMP_HEADER, HmacConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.validation import validate_request

logger = logging.getLogger("hardenlabs_hmac.middleware")


class HardenHmacMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that validates incoming HMAC-signed requests."""

    def __init__(self, app: ASGIApp, config: HmacConfig) -> None:
        super().__init__(app)
        self.config = config

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

        try:
            validate_request(
                config=self.config,
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
