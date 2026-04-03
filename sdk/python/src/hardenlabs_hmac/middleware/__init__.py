"""HardenHMAC middleware integrations."""

try:
    from hardenlabs_hmac.middleware.depends import (
        HmacValidate,
        HmacValidationHttpError,
        install_hmac_exception_handler,
    )
except ImportError:
    __all__: list[str] = []
else:
    __all__ = [
        "HmacValidate",
        "HmacValidationHttpError",
        "install_hmac_exception_handler",
    ]
