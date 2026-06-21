class SQPError(Exception):
    """Base error."""

class ProviderNotConfiguredError(SQPError):
    """A data provider is required but not configured (missing key/vendor)."""

class DataValidationError(SQPError):
    """Input data failed validation."""
