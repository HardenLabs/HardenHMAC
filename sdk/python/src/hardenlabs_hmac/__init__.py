"""HardenHMAC - Cross-language HMAC-SHA256 request signing."""

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.client import sign_request_headers
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.exceptions import HmacValidationError
from hardenlabs_hmac.signing import sign, verify
from hardenlabs_hmac.validation import validate_request

__all__ = [
    "build_canonical_string",
    "sign",
    "sign_request_headers",
    "verify",
    "validate_request",
    "HmacConfig",
    "SignedHeadersConfig",
    "HmacValidationError",
]

__version__ = "0.1.0"
