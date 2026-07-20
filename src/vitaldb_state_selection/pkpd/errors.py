"""Errors raised by the deterministic PK/PD scientific core."""


class PKPDValidationError(ValueError):
    """Raised when a scientific input or computed state violates its contract."""
