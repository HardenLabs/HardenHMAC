"""Tests for request validation."""

import pytest

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.signing import sign
from hardenlabs_hmac.validation import validate_request

TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="
BASE_TIMESTAMP = 1700000000

config = HmacConfig(
    shared_secret_base64=TEST_SECRET,
    signed_headers=SignedHeadersConfig.none(),
    timestamp_tolerance_seconds=30,
)


def _sign(method: str, path: str, body: str, timestamp: int) -> str:
    canonical = build_canonical_string(
        method, path, body, timestamp, SignedHeadersConfig.none()
    )
    return sign(TEST_SECRET, canonical)


def test_valid_request() -> None:
    sig = _sign("GET", "/api/test", "", BASE_TIMESTAMP)
    validate_request(
        config, "GET", "/api/test", "",
        sig, str(BASE_TIMESTAMP),
        current_timestamp=BASE_TIMESTAMP,
    )


def test_missing_signature() -> None:
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            None, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "missing_signature"


def test_empty_signature() -> None:
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            "", str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "missing_signature"


def test_missing_timestamp() -> None:
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            "some-sig", None,
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "missing_timestamp"


def test_invalid_timestamp() -> None:
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            "some-sig", "not-a-number",
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "invalid_timestamp"


def test_timestamp_expired() -> None:
    sig = _sign("GET", "/api/test", "", BASE_TIMESTAMP)
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            sig, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP + 31,
        )
    assert exc_info.value.error_type == "timestamp_expired"


def test_timestamp_at_tolerance_succeeds() -> None:
    sig = _sign("GET", "/api/test", "", BASE_TIMESTAMP)
    validate_request(
        config, "GET", "/api/test", "",
        sig, str(BASE_TIMESTAMP),
        current_timestamp=BASE_TIMESTAMP + 30,
    )


def test_future_timestamp() -> None:
    future_ts = BASE_TIMESTAMP + 100
    sig = _sign("GET", "/api/test", "", future_ts)
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            sig, str(future_ts),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "timestamp_out_of_range"


def test_invalid_signature() -> None:
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/test", "",
            "0" * 64, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "signature_invalid"


def test_tampered_body() -> None:
    sig = _sign("POST", "/api/test", '{"a":1}', BASE_TIMESTAMP)
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "POST", "/api/test", '{"a":2}',
            sig, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "signature_invalid"


def test_tampered_path() -> None:
    sig = _sign("GET", "/api/test", "", BASE_TIMESTAMP)
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            config, "GET", "/api/other", "",
            sig, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP,
        )
    assert exc_info.value.error_type == "signature_invalid"


def test_custom_tolerance() -> None:
    strict_config = HmacConfig(
        shared_secret_base64=TEST_SECRET,
        signed_headers=SignedHeadersConfig.none(),
        timestamp_tolerance_seconds=5,
    )
    sig = _sign("GET", "/api/test", "", BASE_TIMESTAMP)
    with pytest.raises(HmacValidationError) as exc_info:
        validate_request(
            strict_config, "GET", "/api/test", "",
            sig, str(BASE_TIMESTAMP),
            current_timestamp=BASE_TIMESTAMP + 6,
        )
    assert exc_info.value.error_type == "timestamp_expired"
