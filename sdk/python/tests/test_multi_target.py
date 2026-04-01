"""Tests for multi-target configuration, env loading, and client factory."""

import time

import pytest

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import (
    HmacConfig,
    HmacTargetConfig,
    SignedHeadersConfig,
)
from hardenlabs_hmac.signing import sign, verify


GLOBAL_SECRET = "Z2xvYmFsLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ=="
ORDERS_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ=="
PAYMENTS_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE="


def _make_multi_config() -> HmacConfig:
    return HmacConfig(
        shared_secret_base64=GLOBAL_SECRET,
        timestamp_tolerance_seconds=30,
        signed_headers=SignedHeadersConfig.default(),
        targets={
            "order-service": HmacTargetConfig(
                base_url="https://orders.example.com",
                shared_secret=ORDERS_SECRET,
            ),
            "payment-service": HmacTargetConfig(
                base_url="https://payments.example.com",
                shared_secret=PAYMENTS_SECRET,
                timestamp_tolerance_seconds=60,
                signed_headers=SignedHeadersConfig.none(),
            ),
            "fallback-service": HmacTargetConfig(
                base_url="https://fallback.example.com",
                # No shared_secret — should fall back to global
            ),
        },
    )


class TestMultiTargetConfig:
    def test_get_effective_secret_returns_target_secret(self) -> None:
        config = _make_multi_config()
        assert config.get_effective_secret("order-service") == ORDERS_SECRET
        assert config.get_effective_secret("payment-service") == PAYMENTS_SECRET

    def test_get_effective_secret_falls_back_to_global(self) -> None:
        config = _make_multi_config()
        assert config.get_effective_secret("fallback-service") == GLOBAL_SECRET

    def test_get_effective_secret_raises_for_unknown(self) -> None:
        config = _make_multi_config()
        with pytest.raises(KeyError, match="nonexistent"):
            config.get_effective_secret("nonexistent")

    def test_get_effective_signed_headers_returns_override(self) -> None:
        config = _make_multi_config()
        headers = config.get_effective_signed_headers("payment-service")
        assert headers.include_authorization is False
        assert headers.include_x_headers is False

    def test_get_effective_signed_headers_returns_global(self) -> None:
        config = _make_multi_config()
        headers = config.get_effective_signed_headers("order-service")
        assert headers.include_authorization is True

    def test_get_effective_timestamp_tolerance_returns_override(self) -> None:
        config = _make_multi_config()
        assert config.get_effective_timestamp_tolerance("payment-service") == 60

    def test_get_effective_timestamp_tolerance_returns_global(self) -> None:
        config = _make_multi_config()
        assert config.get_effective_timestamp_tolerance("order-service") == 30

    def test_for_target_returns_resolved_config(self) -> None:
        config = _make_multi_config()
        payment = config.for_target("payment-service")
        assert payment.shared_secret_base64 == PAYMENTS_SECRET
        assert payment.timestamp_tolerance_seconds == 60
        assert payment.signed_headers.include_authorization is False

    def test_for_target_fallback_uses_global_defaults(self) -> None:
        config = _make_multi_config()
        fallback = config.for_target("fallback-service")
        assert fallback.shared_secret_base64 == GLOBAL_SECRET
        assert fallback.timestamp_tolerance_seconds == 30
        assert fallback.signed_headers.include_authorization is True

    def test_backwards_compatibility_single_secret(self) -> None:
        config = HmacConfig(
            shared_secret_base64=GLOBAL_SECRET,
            signed_headers=SignedHeadersConfig.none(),
        )
        assert config.shared_secret_base64 == GLOBAL_SECRET
        assert config.targets == {}

    def test_sign_and_verify_per_target(self) -> None:
        config = _make_multi_config()
        orders = config.for_target("order-service")

        ts = int(time.time())
        canonical = build_canonical_string(
            "GET", "/api/orders", "", ts, orders.signed_headers
        )
        sig = sign(orders.shared_secret_base64, canonical)
        assert verify(orders.shared_secret_base64, canonical, sig)

    def test_different_targets_produce_different_signatures(self) -> None:
        config = _make_multi_config()
        ts = int(time.time())

        orders = config.for_target("order-service")
        payments = config.for_target("payment-service")

        canonical_orders = build_canonical_string(
            "GET", "/api/test", "", ts, orders.signed_headers
        )
        canonical_payments = build_canonical_string(
            "GET", "/api/test", "", ts, payments.signed_headers
        )

        sig_orders = sign(orders.shared_secret_base64, canonical_orders)
        sig_payments = sign(payments.shared_secret_base64, canonical_payments)

        assert sig_orders != sig_payments


class TestEnvLoading:
    def test_from_env_single_secret(self) -> None:
        env = {
            "HARDEN_HMAC_SHARED_SECRET_BASE64": GLOBAL_SECRET,
            "HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "60",
        }
        config = HmacConfig.from_env(env=env)
        assert config.shared_secret_base64 == GLOBAL_SECRET
        assert config.timestamp_tolerance_seconds == 60

    def test_from_env_multi_target(self) -> None:
        env = {
            "HARDEN_HMAC_SHARED_SECRET_BASE64": GLOBAL_SECRET,
            "HARDEN_HMAC_TARGETS__ORDER_SERVICE__BASE_URL": "https://orders.example.com",
            "HARDEN_HMAC_TARGETS__ORDER_SERVICE__SHARED_SECRET": ORDERS_SECRET,
            "HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__BASE_URL": "https://payments.example.com",
            "HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__SHARED_SECRET": PAYMENTS_SECRET,
            "HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__TIMESTAMP_TOLERANCE_SECONDS": "60",
        }
        config = HmacConfig.from_env(env=env)

        assert len(config.targets) == 2
        assert config.targets["order-service"].base_url == "https://orders.example.com"
        assert config.targets["order-service"].shared_secret == ORDERS_SECRET
        assert config.targets["payment-service"].base_url == "https://payments.example.com"
        assert config.targets["payment-service"].timestamp_tolerance_seconds == 60

    def test_from_env_signed_headers(self) -> None:
        env = {
            "HARDEN_HMAC_SHARED_SECRET_BASE64": GLOBAL_SECRET,
            "HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_AUTHORIZATION": "false",
            "HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_X_HEADERS": "true",
        }
        config = HmacConfig.from_env(env=env)
        assert config.signed_headers.include_authorization is False
        assert config.signed_headers.include_x_headers is True

    def test_from_env_custom_prefix(self) -> None:
        env = {
            "MY_APP_SHARED_SECRET_BASE64": GLOBAL_SECRET,
        }
        config = HmacConfig.from_env(prefix="MY_APP_", env=env)
        assert config.shared_secret_base64 == GLOBAL_SECRET

    def test_from_env_empty_returns_defaults(self) -> None:
        config = HmacConfig.from_env(env={})
        assert config.shared_secret_base64 == ""
        assert config.targets == {}
        assert config.timestamp_tolerance_seconds == 30

    def test_from_env_case_insensitive_prefix(self) -> None:
        env = {
            "harden_hmac_SHARED_SECRET_BASE64": GLOBAL_SECRET,
        }
        config = HmacConfig.from_env(env=env)
        assert config.shared_secret_base64 == GLOBAL_SECRET


class TestClientFactory:
    def test_create_client_raises_for_unknown_target(self) -> None:
        from hardenlabs_hmac.client import HmacClientFactory

        config = _make_multi_config()
        factory = HmacClientFactory(config)
        with pytest.raises(KeyError, match="nonexistent"):
            factory.create_client("nonexistent")

    def test_create_sync_client_raises_for_unknown_target(self) -> None:
        from hardenlabs_hmac.client import HmacClientFactory

        config = _make_multi_config()
        factory = HmacClientFactory(config)
        with pytest.raises(KeyError, match="nonexistent"):
            factory.create_sync_client("nonexistent")
