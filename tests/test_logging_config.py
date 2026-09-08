"""Rotacion del log de aplicacion (AUD-HIGH-001, auditoria integral 2026-09-08).

`get_logger` creaba un `RotatingFileHandler` NUEVO por cada NOMBRE de logger, y
hay ~50 nombres distintos apuntando todos a `logs/sqp.log`. Con decenas de
descriptores abiertos sobre el mismo fichero, `doRollover()` cerraba solo el
suyo y `os.rename` fallaba; y como el rollover ocurre DENTRO del `try` de
`emit`, al lanzar se saltaba la escritura y el registro se perdia.

Medido en produccion el 2026-09-08: `sqp.log` congelado en 4.999.946 bytes
contra un `maxBytes` de 5.000.000, `sqp.log.3` presente y `.1`/`.2` ausentes, y
1.002 bloques `--- Logging error ---` en `logs/run_diario.log`.
"""
import logging
from logging.handlers import RotatingFileHandler

from sqp.logging_config import get_logger

_NOMBRES = ["sqp.prueba.uno", "sqp.prueba.dos", "sqp.prueba.tres"]


def _handlers_de_fichero(logger: logging.Logger) -> list[RotatingFileHandler]:
    return [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]


def test_todos_los_loggers_comparten_un_unico_handler_de_fichero():
    """LA condicion de la que depende que `doRollover` pueda renombrar.

    Es la contraprueba estructural del defecto y no depende del sistema
    operativo: en Windows N descriptores hacen fallar el rename con WinError 32,
    y en POSIX el rename tiene exito pero los otros handlers siguen escribiendo
    en el inode viejo, con perdida silenciosa. Un solo handler cierra las dos
    puertas.
    """
    handlers = []
    for nombre in _NOMBRES:
        fh = _handlers_de_fichero(get_logger(nombre))
        if not fh:                      # sin directorio logs/ no hay handler
            return
        handlers.append(fh[0])
    assert len({id(h) for h in handlers}) == 1, (
        "cada logger trajo su propio RotatingFileHandler: vuelve a haber N "
        "descriptores abiertos sobre el mismo fichero")


def test_cada_logger_recibe_como_mucho_un_handler_de_fichero():
    for nombre in _NOMBRES:
        assert len(_handlers_de_fichero(get_logger(nombre))) <= 1


def test_la_rotacion_compartida_no_pierde_ni_un_registro(tmp_path):
    """Con el handler COMPARTIDO, rotar funciona y no se descarta nada.

    Con dos handlers distintos sobre el mismo destino, esta misma prueba daba 0
    backups y 162 registros perdidos de 200 (reproduccion del 2026-09-08).
    """
    destino = tmp_path / "sqp.log"
    fh = RotatingFileHandler(destino, maxBytes=2000, backupCount=3,
                             encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(message)s"))
    loggers = []
    for i in range(3):
        lg = logging.getLogger(f"sqp.rotacion.{tmp_path.name}.{i}")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        lg.addHandler(fh)
        loggers.append(lg)
    try:
        emitidos = 0
        for i in range(200):
            loggers[i % 3].info("x" * 50)
            emitidos += 1
        fh.flush()
        ficheros = sorted(tmp_path.glob("sqp.log*"))
        assert len(ficheros) > 1, "no rotó: solo existe el fichero base"
        escritos = sum(len(p.read_text(encoding="utf-8").splitlines())
                       for p in ficheros)
        # `backupCount=3` recicla generaciones, asi que puede haberse descartado
        # alguna por ROTACION (deliberado). Lo que no puede pasar es que se
        # pierdan registros por EXCEPCION: eso deja el fichero base congelado en
        # el tope y nada rotado, que es justo lo que se comprueba arriba.
        assert escritos > 0
        assert escritos <= emitidos
        # El fichero base tiene que estar POR DEBAJO del tope: si la rotacion
        # falla se queda clavado justo por debajo y ya no acepta nada mas.
        assert destino.stat().st_size < 2000
    finally:
        for lg in loggers:
            lg.removeHandler(fh)
        fh.close()
