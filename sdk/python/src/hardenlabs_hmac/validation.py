"""Request validation for HardenHMAC."""

import time

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.signing import verify


def validate_request(
    config: HmacConfig,
    method: str,
    path: str,
    body: str,
    signature_header: str | None,
    timestamp_header: str | None,
    request_headers: dict[str, str] | None = None,
    current_timestamp: int | None = None,
) -> None:
    """Validate an HMAC-signed request.

    Checks timestamp freshness and signature correctness.

    Args:
        config: HMAC configuration with shared secret and tolerance.
        method: HTTP method.
        path: Request path including query string.
        body: Request body (empty string if none).
        signature_header: Value of X-Harden-Signature header.
        timestamp_header: Value of X-Harden-Timestamp header.
        request_headers: All request headers for signed header reconstruction.
        current_timestamp: Current Unix timestamp (if None, uses time.time()).

    Raises:
        HmacValidationError: If validation fails, with error_type and message.
    """
    if not signature_header:
        raise HmacValidationError(
            "missing_signature", "X-Harden-Signature header is required."
        )

    if not timestamp_header:
        raise HmacValidationError(
            "missing_timestamp", "X-Harden-Timestamp header is required."
        )

    try:
        request_timestamp = int(timestamp_header)
    except (ValueError, TypeError):
        raise HmacValidationError(
            "invalid_timestamp",
            "X-Harden-Timestamp header is not a valid integer.",
        )

    now = current_timestamp if current_timestamp is not None else int(time.time())
    delta = now - request_timestamp

    if delta > config.timestamp_tolerance_seconds:
        raise HmacValidationError(
            "timestamp_expired",
            f"Request timestamp is {delta} seconds in the past "
            f"(tolerance: {config.timestamp_tolerance_seconds}s).",
        )

    if delta < -config.timestamp_tolerance_seconds:
        raise HmacValidationError(
            "timestamp_out_of_range",
            f"Request timestamp is {-delta} seconds in the future "
            f"(tolerance: {config.timestamp_tolerance_seconds}s).",
        )

    canonical_string = build_canonical_string(
        method,
        path,
        body,
        request_timestamp,
        config.signed_headers,
        request_headers,
    )

    if not verify(config.shared_secret_base64, canonical_string, signature_header):
        raise HmacValidationError(
            "signature_invalid",
            "HMAC signature does not match the expected value.",
        )
