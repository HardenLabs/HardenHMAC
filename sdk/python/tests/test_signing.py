"""Tests for HMAC signing and verification."""

import re

from hardenlabs_hmac.signing import sign, verify

TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="


def test_sign_produces_lowercase_hex_64_chars() -> None:
    sig = sign(TEST_SECRET, "test data")
    assert len(sig) == 64
    assert re.match(r"^[0-9a-f]{64}$", sig)


def test_sign_deterministic() -> None:
    sig1 = sign(TEST_SECRET, "canonical string")
    sig2 = sign(TEST_SECRET, "canonical string")
    assert sig1 == sig2


def test_sign_different_inputs_produce_different_signatures() -> None:
    sig1 = sign(TEST_SECRET, "input 1")
    sig2 = sign(TEST_SECRET, "input 2")
    assert sig1 != sig2


def test_sign_different_keys_produce_different_signatures() -> None:
    other_secret = "YW5vdGhlci10ZXN0LWtleS0yNTYtYml0cy1sb25nISE="
    sig1 = sign(TEST_SECRET, "same input")
    sig2 = sign(other_secret, "same input")
    assert sig1 != sig2


def test_verify_valid_signature() -> None:
    canonical = "GET\n/api/test\n\n\n1700000000"
    sig = sign(TEST_SECRET, canonical)
    assert verify(TEST_SECRET, canonical, sig) is True


def test_verify_invalid_signature() -> None:
    canonical = "GET\n/api/test\n\n\n1700000000"
    assert verify(TEST_SECRET, canonical, "0" * 64) is False


def test_verify_tampered_canonical_string() -> None:
    canonical = "GET\n/api/test\n\n\n1700000000"
    sig = sign(TEST_SECRET, canonical)
    tampered = "GET\n/api/test\n\n\n1700000001"
    assert verify(TEST_SECRET, tampered, sig) is False
