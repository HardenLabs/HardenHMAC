"""Tests for env_loader.py — environment variable parsing edge cases."""

from __future__ import annotations

from unittest.mock import patch

from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.env_loader import _parse_bool, _try_load_dotenv, load_config_from_env


TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE="


class TestFromEnvDefaults:
    """Test from_env() with no env vars set returns defaults."""

    def test_empty_env_returns_default_config(self) -> None:
        config = load_config_from_env(env={})
        assert config.shared_secret_base64 == ""
        assert config.timestamp_tolerance_seconds == 30
        assert config.targets == {}
        assert config.clients == {}
        assert config.signed_headers.include_authorization is True
        assert config.signed_headers.include_x_headers is True


class TestTimestampToleranceParsing:
    """Test timestamp tolerance parsing, including invalid values."""

    def test_valid_tolerance(self) -> None:
        config = load_config_from_env(env={
            "HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "60",
        })
        assert config.timestamp_tolerance_seconds == 60

    def test_invalid_tolerance_falls_back_to_default(self) -> None:
        config = load_config_from_env(env={
            "HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "not-a-number",
        })
        assert config.timestamp_tolerance_seconds == 30

    def test_empty_tolerance_falls_back_to_default(self) -> None:
        config = load_config_from_env(env={
            "HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "",
        })
        # Empty string can't be parsed as int -> fallback
        assert config.timestamp_tolerance_seconds == 30

    def test_float_tolerance_falls_back_to_default(self) -> None:
        config = load_config_from_env(env={
            "HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "30.5",
        })
        assert config.timestamp_tolerance_seconds == 30


class TestClientConfigFromEnv:
    """Test client configuration parsing from env vars."""

    def test_single_client(self) -> None:
        env = {
            "HARDEN_HMAC_CLIENTS__MY_SERVICE__SHARED_SECRET": TEST_SECRET,
        }
        config = load_config_from_env(env=env)
        assert "my-service" in config.clients
        assert config.clients["my-service"].shared_secret == TEST_SECRET

    def test_multiple_clients(self) -> None:
        env = {
            "HARDEN_HMAC_CLIENTS__SERVICE_A__SHARED_SECRET": "c2VjcmV0LWE=",
            "HARDEN_HMAC_CLIENTS__SERVICE_B__SHARED_SECRET": "c2VjcmV0LWI=",
        }
        config = load_config_from_env(env=env)
        assert len(config.clients) == 2
        assert "service-a" in config.clients
        assert "service-b" in config.clients

    def test_client_with_no_matching_field_ignored(self) -> None:
        """Key with only one part after CLIENTS__ is not a valid client field."""
        env = {
            "HARDEN_HMAC_CLIENTS__ORPHAN": "value",
        }
        config = load_config_from_env(env=env)
        assert config.clients == {}


class TestTargetConfigFromEnv:
    """Test target configuration parsing edge cases."""

    def test_target_with_signed_headers_override(self) -> None:
        env = {
            "HARDEN_HMAC_TARGETS__MY_API__BASE_URL": "https://api.example.com",
            "HARDEN_HMAC_TARGETS__MY_API__SHARED_SECRET": TEST_SECRET,
            "HARDEN_HMAC_TARGETS__MY_API__SIGNED_HEADERS__INCLUDE_AUTHORIZATION": "false",
            "HARDEN_HMAC_TARGETS__MY_API__SIGNED_HEADERS__INCLUDE_X_HEADERS": "false",
        }
        config = load_config_from_env(env=env)
        target = config.targets["my-api"]
        assert target.signed_headers is not None
        assert target.signed_headers.include_authorization is False
        assert target.signed_headers.include_x_headers is False

    def test_target_invalid_tolerance_ignored(self) -> None:
        env = {
            "HARDEN_HMAC_TARGETS__SVC__BASE_URL": "https://svc.example.com",
            "HARDEN_HMAC_TARGETS__SVC__TIMESTAMP_TOLERANCE_SECONDS": "bad",
        }
        config = load_config_from_env(env=env)
        target = config.targets["svc"]
        assert target.timestamp_tolerance_seconds is None

    def test_target_with_no_matching_field_ignored(self) -> None:
        """Key with only one part after TARGETS__ is not a valid target field."""
        env = {
            "HARDEN_HMAC_TARGETS__ORPHAN": "value",
        }
        config = load_config_from_env(env=env)
        assert config.targets == {}


class TestParseBool:
    def test_true_values(self) -> None:
        assert _parse_bool("true") is True
        assert _parse_bool("True") is True
        assert _parse_bool("TRUE") is True
        assert _parse_bool("1") is True
        assert _parse_bool("yes") is True
        assert _parse_bool("Yes") is True

    def test_false_values(self) -> None:
        assert _parse_bool("false") is False
        assert _parse_bool("0") is False
        assert _parse_bool("no") is False
        assert _parse_bool("") is False
        assert _parse_bool("anything") is False


class TestDotenvFallback:
    """Test dotenv import fallback when python-dotenv is not installed."""

    def test_try_load_dotenv_succeeds_when_installed(self) -> None:
        """When dotenv is installed, _try_load_dotenv should not raise."""
        _try_load_dotenv()  # Should not raise

    def test_try_load_dotenv_handles_import_error(self) -> None:
        """When dotenv is not available, _try_load_dotenv silently passes."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):
            if name == "dotenv":
                raise ImportError("no dotenv")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            _try_load_dotenv()  # Should not raise

    def test_from_env_without_explicit_env_uses_os_environ(self) -> None:
        """When env=None, load_config_from_env loads from os.environ."""
        with patch.dict("os.environ", {"HARDEN_HMAC_SHARED_SECRET_BASE64": TEST_SECRET}, clear=True):
            config = load_config_from_env(env=None)
        assert config.shared_secret_base64 == TEST_SECRET


class TestCaseInsensitivePrefix:
    def test_lowercase_prefix_in_env(self) -> None:
        env = {
            "harden_hmac_SHARED_SECRET_BASE64": TEST_SECRET,
        }
        config = load_config_from_env(env=env)
        assert config.shared_secret_base64 == TEST_SECRET

    def test_mixed_case_prefix_in_env(self) -> None:
        env = {
            "Harden_Hmac_SHARED_SECRET_BASE64": TEST_SECRET,
        }
        config = load_config_from_env(env=env)
        assert config.shared_secret_base64 == TEST_SECRET
