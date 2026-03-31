"""Configuration models for HardenHMAC."""

from dataclasses import dataclass, field


SIGNATURE_HEADER = "X-Harden-Signature"
TIMESTAMP_HEADER = "X-Harden-Timestamp"
SIGNED_HEADERS_HEADER = "X-Harden-Signed-Headers"
HARDEN_HEADER_PREFIX = "x-harden-"
X_HEADER_PREFIX = "x-"
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 30


@dataclass(frozen=True)
class SignedHeadersConfig:
    """Configuration for which request headers are included in the HMAC signature."""

    include_authorization: bool = True
    include_x_headers: bool = True
    additional_headers: list[str] = field(default_factory=list)
    exclude_headers: list[str] = field(default_factory=list)

    @staticmethod
    def default() -> "SignedHeadersConfig":
        """Default configuration: include Authorization and X-* headers."""
        return SignedHeadersConfig()

    @staticmethod
    def none() -> "SignedHeadersConfig":
        """Configuration that signs no headers."""
        return SignedHeadersConfig(
            include_authorization=False,
            include_x_headers=False,
        )


@dataclass(frozen=True)
class HmacConfig:
    """Configuration for HMAC signing and validation."""

    shared_secret_base64: str
    signed_headers: SignedHeadersConfig = field(
        default_factory=SignedHeadersConfig.default
    )
    timestamp_tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS
