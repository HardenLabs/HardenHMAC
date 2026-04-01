"""Environment variable parsing for HardenHMAC configuration."""

from __future__ import annotations

import os
from typing import Any


def _try_load_dotenv() -> None:
    """Attempt to load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _parse_bool(value: str) -> bool:
    """Parse a boolean string value."""
    return value.lower() in ("true", "1", "yes")


def load_config_from_env(
    prefix: str = "HARDEN_HMAC_",
    env: dict[str, str] | None = None,
) -> "HmacConfig":
    """Parse environment variables into an HmacConfig.

    If python-dotenv is installed and no explicit env dict is provided,
    .env file variables are loaded into os.environ first.

    Args:
        prefix: Environment variable prefix.
        env: Optional dict of environment variables (for testing).
             If None, uses os.environ after loading .env.

    Returns:
        Parsed HmacConfig.
    """
    from hardenlabs_hmac.config import (
        HmacClientIdentity,
        HmacConfig,
        HmacTargetConfig,
        SignedHeadersConfig,
    )

    if env is None:
        _try_load_dotenv()
        env = dict(os.environ)

    upper_prefix = prefix.upper()

    # Extract all env vars with the prefix
    prefixed: dict[str, str] = {}
    for key, value in env.items():
        if key.upper().startswith(upper_prefix):
            # Strip prefix and normalize to uppercase
            suffix = key[len(upper_prefix):]
            prefixed[suffix.upper()] = value

    # Parse global settings
    shared_secret = prefixed.get("SHARED_SECRET_BASE64", "")
    try:
        timestamp_tolerance = int(prefixed.get("TIMESTAMP_TOLERANCE_SECONDS", "30"))
    except ValueError:
        timestamp_tolerance = 30

    # Parse signed headers
    include_auth = _parse_bool(
        prefixed.get("SIGNED_HEADERS__INCLUDE_AUTHORIZATION", "true")
    )
    include_x = _parse_bool(
        prefixed.get("SIGNED_HEADERS__INCLUDE_X_HEADERS", "true")
    )
    signed_headers = SignedHeadersConfig(
        include_authorization=include_auth,
        include_x_headers=include_x,
    )

    # Parse targets: keys matching TARGETS__{NAME}__{FIELD}
    targets: dict[str, dict[str, Any]] = {}
    target_prefix = "TARGETS__"
    for key, value in prefixed.items():
        if not key.startswith(target_prefix):
            continue
        rest = key[len(target_prefix):]
        parts = rest.split("__", 1)
        if len(parts) != 2:
            continue
        target_name = parts[0].lower().replace("_", "-")
        field_name = parts[1].upper()
        if target_name not in targets:
            targets[target_name] = {}
        targets[target_name][field_name] = value

    target_configs: dict[str, HmacTargetConfig] = {}
    for name, fields in targets.items():
        target_signed_headers: SignedHeadersConfig | None = None
        if "SIGNED_HEADERS__INCLUDE_AUTHORIZATION" in fields or "SIGNED_HEADERS__INCLUDE_X_HEADERS" in fields:
            target_signed_headers = SignedHeadersConfig(
                include_authorization=_parse_bool(
                    fields.get("SIGNED_HEADERS__INCLUDE_AUTHORIZATION", "true")
                ),
                include_x_headers=_parse_bool(
                    fields.get("SIGNED_HEADERS__INCLUDE_X_HEADERS", "true")
                ),
            )

        target_tolerance: int | None = None
        if "TIMESTAMP_TOLERANCE_SECONDS" in fields:
            try:
                target_tolerance = int(fields["TIMESTAMP_TOLERANCE_SECONDS"])
            except ValueError:
                target_tolerance = None

        target_configs[name] = HmacTargetConfig(
            base_url=fields.get("BASE_URL", ""),
            shared_secret=fields.get("SHARED_SECRET", ""),
            signed_headers=target_signed_headers,
            timestamp_tolerance_seconds=target_tolerance,
        )

    # Parse clients: keys matching CLIENTS__{NAME}__{FIELD}
    clients: dict[str, dict[str, str]] = {}
    client_prefix = "CLIENTS__"
    for key, value in prefixed.items():
        if not key.startswith(client_prefix):
            continue
        rest = key[len(client_prefix):]
        parts = rest.split("__", 1)
        if len(parts) != 2:
            continue
        client_name = parts[0].lower().replace("_", "-")
        field_name = parts[1].upper()
        if client_name not in clients:
            clients[client_name] = {}
        clients[client_name][field_name] = value

    client_configs: dict[str, HmacClientIdentity] = {}
    for name, fields in clients.items():
        client_configs[name] = HmacClientIdentity(
            shared_secret=fields.get("SHARED_SECRET", ""),
        )

    return HmacConfig(
        shared_secret_base64=shared_secret,
        targets=target_configs,
        clients=client_configs,
        signed_headers=signed_headers,
        timestamp_tolerance_seconds=timestamp_tolerance,
    )
