"""Client-side request signing for HardenHMAC."""

import time

from hardenlabs_hmac.canonical import build_canonical_string, build_signed_headers
from hardenlabs_hmac.config import (
    SIGNATURE_HEADER,
    SIGNED_HEADERS_HEADER,
    TIMESTAMP_HEADER,
    HmacConfig,
)
from hardenlabs_hmac.signing import sign


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
