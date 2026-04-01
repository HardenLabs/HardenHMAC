"""HMAC-SHA256 signing and verification with constant-time comparison."""

import base64
import hashlib
import hmac as hmac_module


def sign(shared_secret_base64: str, canonical_string: str) -> str:
    """Compute the HMAC-SHA256 signature of a canonical string.

    Args:
        shared_secret_base64: The shared secret as a Base64-encoded string.
        canonical_string: The canonical string to sign.

    Returns:
        Lowercase hexadecimal signature string (64 characters).
    """
    # Note: Python's bytes type is immutable and cannot be reliably zeroed after use.
    # Using bytearray would not help because hmac.new() copies the key internally.
    # Key material may persist in memory until garbage collected.
    # Strip whitespace before decoding to match C#/TypeScript behavior.
    key_bytes = base64.b64decode(shared_secret_base64.strip(), validate=True)
    data_bytes = canonical_string.encode("utf-8")
    digest = hmac_module.new(key_bytes, data_bytes, hashlib.sha256).hexdigest()
    return digest


def verify(
    shared_secret_base64: str, canonical_string: str, signature: str
) -> bool:
    """Verify a signature against a canonical string using constant-time comparison.

    Args:
        shared_secret_base64: The shared secret as a Base64-encoded string.
        canonical_string: The canonical string that was signed.
        signature: The signature to verify (64-char lowercase hex).

    Returns:
        True if the signature is valid.
    """
    expected = sign(shared_secret_base64, canonical_string)
    return hmac_module.compare_digest(expected, signature)
