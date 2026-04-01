"""Tests for canonical string builder."""

from hardenlabs_hmac.canonical import build_canonical_string, build_signed_headers
from hardenlabs_hmac.config import SignedHeadersConfig


def test_basic_get_canonical_string() -> None:
    result = build_canonical_string("GET", "/api/users", "", 1700000000)
    assert result == "GET\n/api/users\n\n\n1700000000"


def test_post_with_body() -> None:
    body = '{"name":"Alice"}'
    result = build_canonical_string("POST", "/api/users", body, 1700000001)
    assert result == f"POST\n/api/users\n\n{body}\n1700000001"


def test_method_is_uppercased() -> None:
    result = build_canonical_string("get", "/api/users", "", 1700000000)
    assert result.startswith("GET\n")


def test_path_includes_query_string() -> None:
    result = build_canonical_string("GET", "/api/users?active=true", "", 1700000000)
    assert "/api/users?active=true" in result


def test_root_path() -> None:
    result = build_canonical_string("GET", "/", "", 1700000000)
    assert result == "GET\n/\n\n\n1700000000"


def test_empty_body_is_empty_string() -> None:
    result = build_canonical_string("GET", "/", "", 1700000000)
    # The body field (4th field) should be empty
    parts = result.split("\n")
    assert parts[3] == ""


def test_signed_headers_sorted_alphabetically() -> None:
    config = SignedHeadersConfig(include_authorization=True, include_x_headers=True)
    headers = {
        "X-Request-Id": "abc",
        "Authorization": "Bearer tok",
    }
    result = build_canonical_string("GET", "/", "", 1700000000, config, headers)
    assert "authorization:Bearer tok\nx-request-id:abc" in result


def test_excludes_x_harden_headers() -> None:
    config = SignedHeadersConfig(include_x_headers=True)
    headers = {
        "X-Request-Id": "abc",
        "X-Harden-Signature": "should-be-excluded",
        "X-Harden-Timestamp": "12345",
    }
    result = build_canonical_string("GET", "/", "", 1700000000, config, headers)
    assert "x-request-id:abc" in result
    assert "x-harden-" not in result


def test_exclude_headers_overrides_inclusion() -> None:
    config = SignedHeadersConfig(
        include_x_headers=True,
        exclude_headers=["X-Custom-B"],
    )
    headers = {
        "X-Custom-A": "keep",
        "X-Custom-B": "exclude",
    }
    result = build_canonical_string("GET", "/", "", 1700000000, config, headers)
    assert "x-custom-a:keep" in result
    assert "x-custom-b" not in result


def test_header_values_are_trimmed() -> None:
    config = SignedHeadersConfig(include_authorization=True)
    headers = {"Authorization": "  Bearer tok  "}
    result = build_canonical_string("GET", "/", "", 1700000000, config, headers)
    assert "authorization:Bearer tok" in result
    assert "  Bearer" not in result


def test_additional_headers() -> None:
    config = SignedHeadersConfig(
        include_authorization=False,
        include_x_headers=False,
        additional_headers=["Content-Type"],
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/html",
    }
    result = build_canonical_string("GET", "/", "", 1700000000, config, headers)
    assert "content-type:application/json" in result
    assert "accept" not in result


def test_no_matching_headers_empty() -> None:
    config = SignedHeadersConfig.none()
    headers = {"Authorization": "Bearer tok", "X-Custom": "value"}
    result = build_canonical_string("GET", "/api", "", 1700000000, config, headers)
    assert result == "GET\n/api\n\n\n1700000000"


# ATK-1: Newline injection validation
def test_newline_in_method_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="method must not contain newline characters"):
        build_canonical_string("GET\nX-Injected:evil", "/api/test", "", 1700000000)


def test_newline_in_path_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="path must not contain newline characters"):
        build_canonical_string("GET", "/api/test\nX-Injected:evil", "", 1700000000)


# ATK-3: X-Harden-Client-Id always signed
def test_client_id_signed_even_when_x_headers_disabled() -> None:
    config = SignedHeadersConfig(include_authorization=False, include_x_headers=False)
    headers = {
        "X-Harden-Client-Id": "my-client",
        "X-Custom-Header": "should-not-be-signed",
    }
    result = build_canonical_string("GET", "/api/secure", "", 1700000050, config, headers)
    assert "x-harden-client-id:my-client" in result
    assert "x-custom-header" not in result


def test_build_signed_headers_returns_names() -> None:
    config = SignedHeadersConfig(include_authorization=True, include_x_headers=True)
    headers = {
        "X-Request-Id": "abc",
        "Authorization": "Bearer tok",
    }
    header_string, header_names = build_signed_headers(config, headers)
    assert header_names == ["authorization", "x-request-id"]
    assert header_string == "authorization:Bearer tok\nx-request-id:abc"
