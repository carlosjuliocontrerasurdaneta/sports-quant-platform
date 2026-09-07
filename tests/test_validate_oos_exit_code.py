"""El codigo de salida de `scripts/validate_oos.py` distingue "nada que validar"
de "algo se rompio" (KI-034).

Hasta el 2026-09-06 ambas cosas sumaban al mismo contador `failures` y el script
salia con 1. Daba igual mientras nadie mirara ese codigo: la tarea mensual
`SQP_Validate_OOS_Cdev` terminaba con `LastTaskResult = 1` y nadie se enteraba.

Desde AUD-MED-003 el centinela SI lo mira y lo eleva a ERROR en el health check,
asi que un 1 fabricado por una liga sin backfill encenderia una alarma sobre una
condicion normal. Y una alarma que suena cuando no pasa nada se aprende a
ignorar -- que es exactamente como el CI de este repositorio llego a estar 75
runs seguidos en rojo sin que nadie mirara.

No hay fichero de tests previo para este script: se crea con el arreglo.
"""
from __future__ import annotations

import importlib.util

import pytest

from sqp.config import ROOT


def _cargar():
    """Carga el script como modulo. Es un CLI, no un paquete importable."""
    spec = importlib.util.spec_from_file_location(
        "validate_oos_cli", ROOT / "scripts" / "validate_oos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cli():
    return _cargar()


def test_una_liga_sin_cuotas_de_cierre_no_es_un_fallo(cli, monkeypatch, capsys):
    """El caso que encendia la alarma sin motivo: una liga descubierta cuyo
    backfill de cuotas todavia no existe."""
    monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {})
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py", "--leagues", "mlb", "nba"])
    assert cli.main() == 0
    salida = capsys.readouterr().out
    assert "0 liga(s) validada(s) de 2" in salida
    assert "Nada que validar en: mlb, nba" in salida


def test_sin_ninguna_liga_descubierta_tampoco_es_un_fallo(cli, monkeypatch):
    """Rama que ya salia con 0; se fija para que no derive con el cambio."""
    monkeypatch.setattr(cli, "discover_leagues_with_odds", lambda root: [])
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py"])
    assert cli.main() == 0


def test_un_error_de_verdad_sigue_saliendo_distinto_de_cero(cli, monkeypatch):
    """Contraprueba obligatoria: sin ella, "devolver 0 siempre" pasaria los dos
    tests de arriba y el script no podria avisar de nada.

    Un fallo real propaga la excepcion y `SystemExit(main())` la convierte en un
    codigo distinto de cero. Lo que se elimino es el 1 FABRICADO por una
    condicion normal, no la capacidad de fallar.
    """
    def revienta(root, lg):
        raise RuntimeError("el store de cuotas esta corrupto")

    monkeypatch.setattr(cli, "load_closing_odds", revienta)
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py", "--leagues", "mlb"])
    with pytest.raises(RuntimeError):
        cli.main()


def test_no_declara_fallo_por_una_liga_sin_backfill(cli, monkeypatch):
    """Version explicita del contrato, dicha como invariante: el numero de ligas
    sin cuotas no puede cambiar el codigo de salida."""
    for n in (1, 5, 33):
        monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {})
        monkeypatch.setattr(cli.sys, "argv",
                            ["validate_oos.py", "--leagues", *[f"l{i}" for i in range(n)]])
        assert cli.main() == 0, f"{n} ligas sin cuotas devolvieron un fallo"


class TestElFalloDel2026_09_01:
    """Causa raiz del fallo real, diagnosticada leyendo `logs/validate_oos.log`.

    La corrida mensual del 2026-09-01 listo 32 ligas, valido 4 y murio en la
    quinta con:

        File "scripts/validate_oos.py", line 59, in _cutoff
          return str(results[i].get("date", ""))[:10]
        IndexError: list index out of range

    Fue `frauen_bundesliga`: tiene cuotas capturadas pero CERO resultados
    almacenados, porque es la unica liga con cuotas que no aparece en la lista de
    `BACKFILL_ALL.bat`. Con `results == []`, `max(0, min(-1, 0))` da 0 y
    `results[0]` no existe.

    Y el fallo se llevo por delante las 28 ligas restantes, incluida `mlb`, que
    es la unica con muestra OOS fiable: el operador no vio ni un solo resultado
    util de la validacion de ese mes.
    """

    def test_cutoff_con_resultados_vacios_reventaba(self, cli):
        """La causa exacta, fijada para que se vea si alguien la reintroduce."""
        with pytest.raises(IndexError):
            cli._cutoff([], 0.30, None)

    def test_una_liga_sin_resultados_se_salta_en_vez_de_reventar(self, cli, monkeypatch):
        monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {"e1": object()})
        monkeypatch.setattr(cli, "_league_meta",
                            lambda lg: {"family": "soccer", "three_way": True})
        monkeypatch.setattr(cli.ResultsStore, "load", lambda self, lg: [])
        monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py", "--leagues", "x"])
        assert cli.main() == 0, "una liga sin resultados no es un fallo"

    def test_una_liga_que_revienta_no_se_lleva_a_las_demas(self, cli, monkeypatch, capsys):
        """Lo que de verdad costo caro: el aislamiento por liga. Sin el, la
        primera excepcion aborta la corrida y las demas no se miran."""
        vistas = []

        def validar(league, odds, settings, args):
            vistas.append(league)
            if league == "rota":
                raise IndexError("list index out of range")
            return True

        monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {"e1": object()})
        monkeypatch.setattr(cli, "_validar_liga", validar)
        monkeypatch.setattr(cli.sys, "argv",
                            ["validate_oos.py", "--leagues", "a", "rota", "b", "c"])
        assert cli.main() == 1, "una liga con error SI debe salir distinto de cero"
        assert vistas == ["a", "rota", "b", "c"], (
            f"la corrida se aborto en la liga rota: solo se vieron {vistas}")
        assert "CON ERROR" in capsys.readouterr().out

    def test_el_resumen_distingue_las_tres_categorias(self, cli, monkeypatch, capsys):
        """Sin cuotas, sin resultados y con error son tres cosas distintas y el
        operador necesita separarlas para saber que hacer con cada una."""
        monkeypatch.setattr(cli, "load_closing_odds",
                            lambda root, lg: {} if lg == "sin_odds" else {"e1": object()})
        monkeypatch.setattr(cli, "_validar_liga",
                            lambda lg, o, s, a: lg != "sin_res")
        monkeypatch.setattr(cli.sys, "argv",
                            ["validate_oos.py", "--leagues", "ok", "sin_odds", "sin_res"])
        assert cli.main() == 0
        salida = capsys.readouterr().out
        assert "1 liga(s) validada(s) de 3" in salida
        assert "1 sin cuotas, 1 sin resultados, 0 con error" in salida

    def test_una_liga_RETIRADA_no_enciende_la_alarma(self, cli, monkeypatch):
        """`frauen_bundesliga` se retiro de `configs/leagues/soccer.yaml` el
        2026-09-06 (cierra KI-005: no tiene proveedor de resultados historicos,
        verificado contra el catalogo de ESPN en 2026-06-12 y re-verificado hoy
        con peticiones reales).

        Sus ficheros de cuotas se CONSERVAN -- no se borra lo capturado --, asi
        que `discover_leagues_with_odds` la sigue encontrando y `_league_meta`
        lanza KeyError. Sin guard, esa excepcion caeria en el aislamiento por
        liga, contaria como error y el centinela pondria el health check en rojo
        TODOS LOS MESES por una retirada deliberada.
        """
        monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {"e1": object()})
        monkeypatch.setattr(cli.sys, "argv",
                            ["validate_oos.py", "--leagues", "liga_que_ya_no_existe"])
        assert cli.main() == 0, "una liga retirada no es un fallo"

    def test_la_liga_retirada_ya_no_esta_configurada(self):
        """La otra mitad: si volviera al YAML, el run diario volveria a gastar
        cuota de un plan de pago en una liga que no se puede validar."""
        from sqp.config import CONFIG_DIR, load_yaml
        soccer = load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})
        assert "frauen_bundesliga" not in soccer

    def test_ninguna_liga_configurada_carece_de_proveedor_de_resultados(self):
        """El invariante que la retirada restablece, dicho como propiedad y no
        como caso: una liga que se pricea pero cuyos resultados no se pueden
        obtener nunca podra validarse ni liquidarse desde historico."""
        from sqp.config import CONFIG_DIR, load_yaml
        from sqp.providers.espn_results import ESPN_PATHS
        soccer = load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})
        sin_vendor = sorted(lg for lg in soccer if lg not in ESPN_PATHS)
        assert sin_vendor == [], (
            f"ligas configuradas sin proveedor de resultados: {sin_vendor}")
