"""Exceptions for HardenHMAC validation."""


class HmacValidationError(Exception):
    """Raised when HMAC validation fails."""

    def __init__(self, error_type: str, message: str) -> None:
        self.error_type = error_type
        self.message = message
        super().__init__(f"{error_type}: {message}")
