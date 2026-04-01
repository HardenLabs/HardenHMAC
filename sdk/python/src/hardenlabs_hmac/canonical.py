"""Canonical string builder for HardenHMAC v1.0 specification."""

from hardenlabs_hmac.config import (
    CLIENT_ID_HEADER_LOWER,
    HARDEN_HEADER_PREFIX,
    X_HEADER_PREFIX,
    SignedHeadersConfig,
)


def build_canonical_string(
    method: str,
    path: str,
    body: str,
    timestamp: int,
    signed_headers_config: SignedHeadersConfig | None = None,
    request_headers: dict[str, str] | None = None,
) -> str:
    """Build a canonical string from request components.

    Args:
        method: HTTP method (will be uppercased).
        path: Request path including query string.
        body: Request body, or empty string if none.
        timestamp: Unix timestamp in seconds.
        signed_headers_config: Configuration for which headers to sign.
        request_headers: All request headers (name -> value).

    Returns:
        The canonical string per the v1.0 specification.
    """
    if "\n" in method:
        raise ValueError("method must not contain newline characters")
    if "\n" in path:
        raise ValueError("path must not contain newline characters")

    config = signed_headers_config or SignedHeadersConfig.none()
    headers = request_headers or {}
    signed_headers_string = _build_signed_headers_string(config, headers)

    return "\n".join(
        [
            method.upper(),
            path,
            signed_headers_string,
            body or "",
            str(timestamp),
        ]
    )


def build_signed_headers(
    config: SignedHeadersConfig,
    request_headers: dict[str, str],
) -> tuple[str, list[str]]:
    """Build the signed headers string and return the header names.

    Args:
        config: Signed headers configuration.
        request_headers: All request headers.

    Returns:
        Tuple of (header_string, sorted_header_names).
    """
    selected = _select_headers(config, request_headers)
    header_names = [name for name, _ in selected]
    header_string = "\n".join(f"{name}:{value}" for name, value in selected)
    return header_string, header_names


def _build_signed_headers_string(
    config: SignedHeadersConfig,
    request_headers: dict[str, str],
) -> str:
    """Build the signed headers portion of the canonical string."""
    selected = _select_headers(config, request_headers)
    return "\n".join(f"{name}:{value}" for name, value in selected)


def _select_headers(
    config: SignedHeadersConfig,
    request_headers: dict[str, str],
) -> list[tuple[str, str]]:
    """Select and sort headers based on configuration."""
    exclude_set = {h.lower() for h in config.exclude_headers}
    additional_set = {h.lower() for h in config.additional_headers}

    selected: list[tuple[str, str]] = []

    for name, value in request_headers.items():
        lower_name = name.lower()
        trimmed_value = value.strip()

        # Always exclude X-Harden-* headers, EXCEPT X-Harden-Client-Id
        # (client identity is an identity claim, not signing metadata)
        if lower_name.startswith(HARDEN_HEADER_PREFIX) and lower_name != CLIENT_ID_HEADER_LOWER:
            continue

        include = False

        if config.include_authorization and lower_name == "authorization":
            include = True

        if config.include_x_headers and lower_name.startswith(X_HEADER_PREFIX) and (
            not lower_name.startswith(HARDEN_HEADER_PREFIX)
            or lower_name == CLIENT_ID_HEADER_LOWER
        ):
            include = True

        # X-Harden-Client-Id is always signed when present (identity claim must not be spoofable)
        if lower_name == CLIENT_ID_HEADER_LOWER:
            include = True

        if lower_name in additional_set:
            include = True

        # Apply exclude override
        if lower_name in exclude_set:
            include = False

        if include:
            selected.append((lower_name, trimmed_value))

    # Sort alphabetically by lowercase name
    selected.sort(key=lambda h: h[0])
    return selected
