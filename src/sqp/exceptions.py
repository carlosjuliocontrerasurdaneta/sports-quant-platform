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


class LockNoAdquiridoError(SQPError):
    """No se pudo obtener exclusion sobre un recurso en el plazo dado.

    Se lanza en vez de entrar a la seccion critica sin lock. Degradar era peor
    que fallar: los consumidores hacen read-modify-write, asi que el segundo
    escritor pisa lo que el primero acababa de leer y la actualizacion se pierde
    en silencio (Codex, 2026-09-05, AUD-002, reproducido).

    Un lock huerfano de un proceso muerto NO llega aqui: `locked` lo rompe
    pasado `stale_s`. Esta excepcion significa que otro proceso VIVO lo retiene,
    que es justo cuando entrar sin exclusion es mas peligroso.
    """


class RegistroEstadoIlegibleError(SQPError):
    """Un registro con estado (gate de prediccion, monitor de degradacion)
    EXISTE pero no se puede leer: el estado previo es DESCONOCIDO.

    Desconocido no es vacio. Para un CONSUMIDOR, vacio es default-deny y esta
    bien; para el ESCRITOR, tratarlo como vacio reabria tests de entrada ya
    gastados y desarmaba pestillos, y el resultado se persistia encima: el gate
    fallaba ABIERTO (auditoria audit-2026-09-22-r2, AUD-002, reproducido). El
    escritor lanza esto y no escribe; el fichero queda intacto para diagnostico.
    """
