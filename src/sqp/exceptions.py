class SQPError(Exception):
    """Base error."""

class ProviderNotConfiguredError(SQPError):
    """A data provider is required but not configured (missing key/vendor)."""

class DataValidationError(SQPError):
    """Input data failed validation."""

class LedgerIntegridadError(SQPError):
    """El ledger de banca no se pudo leer entero: el saldo es INDETERMINADO.

    Indeterminado no es cero. Las filas que dejan de leerse suelen ser PERDIDAS,
    asi que omitirlas SUBE el saldo y con el todos los stakes (auditoria
    independiente de Codex 2026-09-05, AUD-001: 600 -> 1.000 al corromperse un
    fichero de puras perdidas).
    """
