"""Cross-language test vector runner for Python SDK."""

import json
from pathlib import Path

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import SignedHeadersConfig
from hardenlabs_hmac.signing import sign, verify

VECTORS_PATH = Path(__file__).parent.parent.parent.parent / "tests" / "cross-language" / "test-vectors.json"


def _load_vectors() -> list[dict]:
    with open(VECTORS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["vectors"]


def _map_config(config_dict: dict) -> SignedHeadersConfig:
    return SignedHeadersConfig(
        include_authorization=config_dict["include_authorization"],
        include_x_headers=config_dict["include_x_headers"],
        additional_headers=config_dict.get("additional_headers", []),
        exclude_headers=config_dict.get("exclude_headers", []),
    )


def test_all_vectors_canonical_string() -> None:
    vectors = _load_vectors()
    for vector in vectors:
        config = _map_config(vector["signed_headers_config"])
        canonical = build_canonical_string(
            vector["method"],
            vector["path"],
            vector["body"],
            vector["timestamp"],
            config,
            vector["request_headers"],
        )
        assert canonical == vector["expected_canonical_string"], (
            f"Vector '{vector['id']}' canonical string mismatch.\n"
            f"Expected: {vector['expected_canonical_string']!r}\n"
            f"Got:      {canonical!r}"
        )


def test_all_vectors_signature() -> None:
    vectors = _load_vectors()
    for vector in vectors:
        config = _map_config(vector["signed_headers_config"])
        canonical = build_canonical_string(
            vector["method"],
            vector["path"],
            vector["body"],
            vector["timestamp"],
            config,
            vector["request_headers"],
        )
        signature = sign(vector["shared_secret_base64"], canonical)
        assert signature == vector["expected_signature"], (
            f"Vector '{vector['id']}' signature mismatch.\n"
            f"Expected: {vector['expected_signature']}\n"
            f"Got:      {signature}"
        )


def test_all_vectors_verify() -> None:
    vectors = _load_vectors()
    for vector in vectors:
        result = verify(
            vector["shared_secret_base64"],
            vector["expected_canonical_string"],
            vector["expected_signature"],
        )
        assert result is True, f"Vector '{vector['id']}' should verify successfully"
