"""Configuration models for HardenHMAC."""

from __future__ import annotations

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
    def default() -> SignedHeadersConfig:
        """Default configuration: include Authorization and X-* headers."""
        return SignedHeadersConfig()

    @staticmethod
    def none() -> SignedHeadersConfig:
        """Configuration that signs no headers."""
        return SignedHeadersConfig(
            include_authorization=False,
            include_x_headers=False,
        )


@dataclass(frozen=True)
class HmacTargetConfig:
    """Per-target configuration for a named service target (client-side).

    Each target has its own base URL, shared secret, and optionally overrides
    global signed headers and timestamp tolerance settings.
    """

    base_url: str = ""
    shared_secret: str = ""
    signed_headers: SignedHeadersConfig | None = None
    timestamp_tolerance_seconds: int | None = None


@dataclass(frozen=True)
class HmacConfig:
    """Configuration for HMAC signing and validation.

    Supports two modes:
    1. Single-secret mode: set shared_secret_base64 for simple client or server use.
    2. Multi-target mode: populate targets with named service configurations.

    Global signed_headers and timestamp_tolerance_seconds serve as defaults
    that individual targets can override.
    """

    shared_secret_base64: str = ""
    targets: dict[str, HmacTargetConfig] = field(default_factory=dict)
    signed_headers: SignedHeadersConfig = field(
        default_factory=SignedHeadersConfig.default
    )
    timestamp_tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS

    def get_effective_secret(self, target_name: str) -> str:
        """Resolve the effective shared secret for a named target.

        Returns the target's secret if set, otherwise falls back to the global secret.

        Args:
            target_name: The target name.

        Returns:
            The effective Base64-encoded shared secret.

        Raises:
            KeyError: If the target is not found.
        """
        if target_name not in self.targets:
            raise KeyError(
                f"Target '{target_name}' is not configured. "
                f"Available targets: [{', '.join(self.targets.keys())}]."
            )
        target = self.targets[target_name]
        return target.shared_secret if target.shared_secret else self.shared_secret_base64

    def get_effective_signed_headers(self, target_name: str) -> SignedHeadersConfig:
        """Resolve the effective signed headers config for a named target."""
        if target_name in self.targets:
            target = self.targets[target_name]
            if target.signed_headers is not None:
                return target.signed_headers
        return self.signed_headers

    def get_effective_timestamp_tolerance(self, target_name: str) -> int:
        """Resolve the effective timestamp tolerance for a named target."""
        if target_name in self.targets:
            target = self.targets[target_name]
            if target.timestamp_tolerance_seconds is not None:
                return target.timestamp_tolerance_seconds
        return self.timestamp_tolerance_seconds

    def for_target(self, target_name: str) -> HmacConfig:
        """Build an effective HmacConfig for a specific target with all overrides resolved."""
        return HmacConfig(
            shared_secret_base64=self.get_effective_secret(target_name),
            signed_headers=self.get_effective_signed_headers(target_name),
            timestamp_tolerance_seconds=self.get_effective_timestamp_tolerance(target_name),
        )

    @classmethod
    def from_env(
        cls,
        prefix: str = "HARDEN_HMAC_",
        env: dict[str, str] | None = None,
    ) -> HmacConfig:
        """Load configuration from environment variables.

        Supports the following environment variables (prefix default: HARDEN_HMAC_):
            {prefix}SHARED_SECRET_BASE64 — global shared secret
            {prefix}TIMESTAMP_TOLERANCE_SECONDS — global tolerance
            {prefix}SIGNED_HEADERS__INCLUDE_AUTHORIZATION — true/false
            {prefix}SIGNED_HEADERS__INCLUDE_X_HEADERS — true/false
            {prefix}TARGETS__{NAME}__BASE_URL — per-target base URL
            {prefix}TARGETS__{NAME}__SHARED_SECRET — per-target secret
            {prefix}TARGETS__{NAME}__TIMESTAMP_TOLERANCE_SECONDS — per-target tolerance

        If python-dotenv is installed, environment variables from a .env file
        are loaded automatically before parsing.

        Args:
            prefix: Environment variable prefix. Default: "HARDEN_HMAC_".
            env: Optional dict of environment variables (for testing).
                 If None, uses os.environ.

        Returns:
            Parsed HmacConfig.
        """
        from hardenlabs_hmac.env_loader import load_config_from_env

        return load_config_from_env(prefix=prefix, env=env)
