"""Pestana "Picks del Dia": TODOS los candidatos, con la razon de su stake.

Motivo de estos tests: la pestana mostraba solo los ACCIONABLES via
`rank_candidates` (stake>0 o flag `shadow_mode`). Al levantar shadow el
2026-08-16 ese flag dejo de emitirse y **la pestana que se abre por defecto
quedo en blanco**, sin que nada lo señalara. El operador paso 53 dias creyendo
que el sistema no generaba nada; generaba 63 candidatos al dia, ninguno con
dinero.

Una tabla vacia y una tabla que dice "0 con stake, 42 cortados por el cap, 20
por el gate" transmiten cosas MUY distintas. Estos tests fijan la segunda.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.audit.html_report import _picks_records
from sqp.audit.report import rank_candidates


def _en_dias(n: int) -> str:
    """Instante UTC a mediodia dentro de `n` dias. Las fechas fijas ya no valen:
    la pestana filtra por PARTIDO no jugado (`picks_vigentes`), asi que un
    fixture anclado al pasado describe una lista que nadie deberia ver."""
    return (datetime.now(timezone.utc) + timedelta(days=n)).strftime(
        "%Y-%m-%dT12:00:00Z")


def _served(tmp_path, liga, rows):
    """Escribe `served_{liga}.csv` con la forma real del stream."""
    base = {"event_id": "e1", "league": liga, "market": "h2h",
            "selection": "A", "line": None, "price_decimal": 2.0,
            "estimated_probability": 0.55, "calibrated_probability": 0.55,
            "implied_probability_novig": 0.5, "estimated_edge": 0.10,
            "books_count": 8, "stake": 0.0, "home": "H", "away": "V",
            "flags": "", "data_label": "real",
            "start_time": _en_dias(1), "generated_at": _en_dias(0)}
    df = pd.DataFrame([{**base, **r} for r in rows])
    df.to_csv(tmp_path / f"served_{liga}.csv", index=False)
    return tmp_path


class TestElTableroYLosCLIUsanElMismoCriterio:
    """Candado de convergencia. `_todos_records` tenia su PROPIA copia del
    criterio de vigencia + colapso, y la copia es justo lo que ya fallo: el
    arreglo del 2026-08-28 se escribio en el tablero y dejo fuera los dos CLI
    que invoca DIARIO_COMPLETO.bat (KI-027). Al extraer `picks_vigentes_unicos`
    el 2026-09-01 la asimetria quedo al reves. Ahora los tres comparten helper.
    """

    def test_el_tablero_devuelve_los_mismos_picks_que_el_helper(self, tmp_path):
        from sqp.audit.html_report import _todos_records
        from sqp.evaluation.labels import picks_vigentes_unicos
        _served(tmp_path, "mlb", [
            {"event_id": "e1", "generated_at": _en_dias(-3)},
            {"event_id": "e1", "generated_at": _en_dias(0)},   # misma servida, otro dia
            {"event_id": "e2", "start_time": _en_dias(-5)},    # ya jugado
        ])
        _served(tmp_path, "epl", [{"event_id": "e3", "generated_at": _en_dias(-2)}])
        crudo = pd.concat([pd.read_csv(p) for p in sorted(tmp_path.glob("served_*.csv"))],
                          ignore_index=True)
        assert len(_todos_records(tmp_path)) == len(picks_vigentes_unicos(crudo))

    def test_no_fusiona_dos_partidos_distintos_sin_event_id(self, tmp_path):
        """La copia colapsaba con clave PARCIAL: sin `event_id`, dos partidos
        que compartieran mercado, seleccion y linea salian como uno. El helper
        exige identidad completa y conserva las filas."""
        from sqp.audit.html_report import _todos_records
        _served(tmp_path, "mlb", [
            {"home": "A", "away": "B", "market": "totals", "selection": "Over", "line": 2.5},
            {"home": "C", "away": "D", "market": "totals", "selection": "Over", "line": 2.5},
        ])
        df = pd.read_csv(tmp_path / "served_mlb.csv").drop(columns=["event_id"])
        df.to_csv(tmp_path / "served_mlb.csv", index=False)
        assert len(_todos_records(tmp_path)) == 2, (
            "sin identidad de evento no se pueden fusionar dos partidos")


def _cands(tmp_path, rows):
    base = {"event_id": "e1", "league": "mlb", "market": "h2h",
            "selection": "A", "line": None, "price_decimal": 2.0,
            "estimated_probability": 0.55, "implied_probability_novig": 0.5,
            "estimated_edge": 0.10, "kelly_stake_pct": 0.0, "stake": 0.0,
            "home": "H", "away": "V", "flags": "", "data_label": "real",
            "start_time": _en_dias(1),
            "generated_at": _en_dias(0)}
    df = pd.DataFrame([{**base, **r} for r in rows])
    (tmp_path / "candidates_mlb.csv").write_text(df.to_csv(index=False),
                                                 encoding="utf-8")
    return tmp_path


class TestMuestraTodosLosCandidatos:
    def test_incluye_los_de_stake_cero(self, tmp_path):
        """El nucleo: sin esto la pestana estaba vacia y parecia una averia."""
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "BLOQUEADA", "stake": 0.0,
             "flags": "prediction_gate"},
        ]))
        assert [r["selection"] for r in recs] == ["BLOQUEADA"]

    def test_incluye_los_cortados_por_el_cap(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "CAP", "flags": "edge_exceeds_max_plausible"},
        ]))
        assert len(recs) == 1

    def test_incluye_los_pausados(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "PAUSADO", "flags": "market_paused"},
        ]))
        assert len(recs) == 1

    def test_ordena_por_edge_descendente(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "BAJO", "estimated_edge": 0.01},
            {"selection": "ALTO", "estimated_edge": 0.30},
        ]))
        assert [r["selection"] for r in recs] == ["ALTO", "BAJO"]


class TestColumnaEstado:
    """El 0 tiene que venir explicado. 64 filas a stake 0 sin razon visible
    parecen un fallo del pipeline."""

    def test_reporta_el_flag_como_estado(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"flags": "edge_exceeds_max_plausible"}]))
        assert recs[0]["estado"] == "edge_exceeds_max_plausible"

    def test_sin_flag_y_con_stake_dice_con_stake(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [{"stake": 5.0, "flags": ""}]))
        assert recs[0]["estado"] == "con stake"

    def test_sin_flag_y_sin_stake_dice_sin_stake(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [{"stake": 0.0, "flags": ""}]))
        assert recs[0]["estado"] == "sin stake"


class TestVigenciaPorPartidoNoPorRun:
    """La pestana filtraba por DIA DE GENERACION mas reciente. Como las ligas no
    se refrescan todas cada dia -- el guardian de presupuesto aplazo 14 el
    2026-08-27, y un run que cruza la medianoche parte los candidatos en dos
    dias -- eso escondia picks perfectamente vigentes. Medido el 2026-08-28:
    82 filas de UNA liga visibles, 577 filas de 13 ligas por jugar ocultas."""

    def test_un_pick_de_ayer_con_partido_manana_sigue_en_la_lista(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "FRESCO", "generated_at": _en_dias(0)},
            {"selection": "DE_AYER", "generated_at": _en_dias(-1),
             "estimated_edge": 0.05},
        ]))
        assert sorted(r["selection"] for r in recs) == ["DE_AYER", "FRESCO"]

    def test_un_pick_de_un_partido_ya_jugado_desaparece(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "JUGADO", "start_time": _en_dias(-2)},
            {"selection": "POR_JUGAR"},
        ]))
        assert [r["selection"] for r in recs] == ["POR_JUGAR"]

    def test_la_fila_dice_de_cuando_es(self, tmp_path):
        """Mezclar runs sin decirlo haria leer una cuota de hace tres dias como
        fresca."""
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "DE_AYER", "generated_at": _en_dias(-1)}]))
        assert recs[0]["generado"] == _en_dias(-1)[:10]

    def test_las_dos_caras_del_mismo_mercado_siguen_apareciendo(self, tmp_path):
        """Riesgo REAL de haber convergido esta vista al helper comun: el helper
        colapsa, y colapsar de mas escondería picks. No lo hace porque
        `selection` esta en la clave de identidad, pero eso hay que fijarlo: la
        REGLA FUNDAMENTAL dice que la lista es de TODOS los mercados, y son los
        gates los que quitan el stake, nunca la lista.

        `candidates_*.csv` se reescribe en cada run, asi que el colapso es aqui
        un no-op medido (169 filas antes y despues el 2026-09-01); este test
        impide que deje de serlo sin que nadie se entere."""
        recs = _picks_records(_cands(tmp_path, [
            {"event_id": "e1", "market": "totals", "selection": "Over", "line": 8.5},
            {"event_id": "e1", "market": "totals", "selection": "Under", "line": 8.5,
             "estimated_edge": 0.05},
        ]))
        assert sorted(r["selection"] for r in recs) == ["Over", "Under"]


class TestVigenciaEsPorInstanteNoPorFecha:
    """KI-028. `picks_vigentes` comparaba solo FECHAS locales, asi que un partido
    que empezo hace horas seguia listado como vigente hasta que cambiaba el dia.
    El sistema es PREGAME: una vez empezado, las cuotas mostradas son en vivo, no
    las que se estimaron. Medido el 2026-09-01 a las 19:00 locales: 66 de los 128
    picks del dia ya habian empezado. De los 156 partidos del 2026-09-02, a las
    23:00 UTC habrian empezado 142 -- el 91% de la lista por defecto."""

    def _fila(self, start_time, **extra):
        base = {"event_id": "e1", "league": "mlb", "market": "h2h",
                "selection": "A", "line": None, "home": "H", "away": "V",
                "start_time": start_time, "game_date": start_time[:10],
                "generated_at": start_time}
        return {**base, **extra}

    def test_un_partido_de_hoy_que_ya_empezo_deja_de_ser_vigente(self):
        from sqp.evaluation.labels import picks_vigentes
        ahora = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
        df = pd.DataFrame([
            self._fila("2026-09-02T18:00:00Z", selection="YA_EMPEZO"),
            self._fila("2026-09-02T23:00:00Z", selection="AUN_NO"),
        ])
        out = picks_vigentes(df, hoy="2026-09-02", ahora=ahora)
        assert list(out["selection"]) == ["AUN_NO"], (
            "el mismo dia no basta: lo que decide es si ya empezo")

    def test_un_sello_ilegible_se_trata_como_NO_empezado(self):
        """Semantica conservadora de `_already_started`: no poder leer la hora no
        demuestra que el partido se jugara, y borrar filas porque falta una
        columna es la averia que este proyecto lleva repitiendo."""
        from sqp.evaluation.labels import picks_vigentes
        ahora = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
        df = pd.DataFrame([self._fila("2026-09-02T18:00:00Z", selection="X")])
        df.loc[0, "start_time"] = "ayer por la tarde"
        out = picks_vigentes(df, hoy="2026-09-02", ahora=ahora)
        assert len(out) == 1

    def test_formatos_ISO_MEZCLADOS_en_la_misma_serie(self):
        """Sin `format="ISO8601"` pandas infiere UN formato para toda la serie:
        con un valor aware seguido de uno naive (ambos ISO validos) devuelve NaT
        para el segundo, y el partido ya empezado se colaba como vigente.
        Reproducido con pandas 3.0.2. El test de paridad de abajo NO lo detecta
        porque construye un frame de UNA fila por caso."""
        from sqp.evaluation.labels import picks_vigentes
        ahora = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
        df = pd.DataFrame([
            self._fila("2026-09-02T23:00:00Z", selection="AUN_NO"),
            self._fila("2026-09-02T18:00:00", selection="YA_EMPEZO"),  # naive
        ])
        out = picks_vigentes(df, hoy="2026-09-02", ahora=ahora)
        assert list(out["selection"]) == ["AUN_NO"]

    def test_una_fecha_no_ISO_no_cuela_como_instante(self):
        """En sentido contrario: el parser por defecto ACEPTA
        `09/02/2026 18:00:00`, que el canonico rechaza, saltandose el fallback
        por fecha que el contrato conservador exige."""
        from sqp.evaluation.labels import instantes_utc
        s = instantes_utc(pd.Series(["09/02/2026 18:00:00"]))
        assert s.isna().all(), "un sello no-ISO debe quedar sin instante"

    def test_DOCUMENTA_que_el_fallback_si_resucita_partidos_empezados(self):
        """KI-030, tension ABIERTA -- este test fija el comportamiento ACTUAL,
        no el deseable.

        Cuando no queda nada apostable, `picks_vigentes_unicos` cae al ultimo dia
        generado y devuelve las filas TAL CUAL, incluidas las de partidos ya
        empezados: la vista muestra cuotas en vivo como si fueran picks pregame.
        Lo reprodujo Codex revisando el cambio a vigencia por instante.

        No se corrige porque el fallback es la decision del 2026-08-28 (leccion
        de los 53 dias) y esta fijado por
        `test_cae_al_dia_mas_reciente_si_hoy_no_hay`: cambiarlo contradice una
        decision registrada y requiere autorizacion del operador.

        Si algun dia se autoriza, este test debe INVERTIRSE, no borrarse."""
        from sqp.evaluation.labels import picks_vigentes_unicos
        df = pd.DataFrame([
            self._fila("2026-09-02T01:00:00Z", selection="A"),
            self._fila("2026-09-02T02:00:00Z", selection="B", event_id="e2"),
        ])
        assert len(picks_vigentes_unicos(df)) == 2, (
            "comportamiento actual: el fallback resucita el lote ya en juego")

    def test_coincide_con_la_definicion_canonica_del_pipeline(self):
        """Candado anti-deriva: `pipeline.daily._already_started` ya define
        "empezado" y suprime candidatos de eventos en juego. La definicion no se
        importa (acoplaria `evaluation` a `pipeline`), asi que se fija aqui que
        las dos coinciden -- incluido el caso del sello ilegible."""
        from sqp.evaluation.labels import picks_vigentes
        from sqp.pipeline.daily import _already_started
        casos = ["2020-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "", "no es fecha"]
        for st in casos:
            df = pd.DataFrame([self._fila(st or "2026-09-02T18:00:00Z")])
            df.loc[0, "start_time"] = st
            vigente_por_instante = len(picks_vigentes(
                df, hoy="1970-01-01", ahora=datetime.now(timezone.utc))) == 1
            assert vigente_por_instante == (not _already_started(st)), (
                f"discrepancia con _already_started para start_time={st!r}")


class TestNoSeTocoElContadorDeAccionables:
    """`rank_candidates` define "accionable" y alimenta el contador
    `Total accionables` del reporte markdown. Ampliar la PESTANA no debe
    ampliar esa cifra: son preguntas distintas."""

    def test_rank_candidates_sigue_excluyendo_los_de_stake_cero(self):
        df = pd.DataFrame([
            {"stake": 0.0, "flags": "prediction_gate", "estimated_edge": 0.1},
            {"stake": 3.0, "flags": "", "estimated_edge": 0.2},
        ])
        assert len(rank_candidates(df)) == 1


class TestDiaEnHoraLocalNoUTC:
    """El dashboard resolvia "hoy" en UTC. A partir de las 22:00 en Espana
    (00:00Z) buscaba los candidatos del dia SIGUIENTE, no encontraba ninguno y
    mostraba "Sin candidatos accionables hoy" -- cada noche, hasta el run de la
    manana. Detectado por el operador el 2026-08-26 a las 22:15 locales
    (02:15Z del 27).

    Es el mismo fallo -- UTC donde tocaba hora local -- que ya se habia
    corregido en la pestana "Todos los Picks" y quedo sin corregir aqui.
    """

    def test_no_calcula_el_dia_a_partir_de_ahora(self, tmp_path, monkeypatch):
        """La solucion final NO es usar hora local sino no calcular el dia en
        absoluto: se toma el mas reciente presente en los datos. Local arreglaba
        el sintoma de hoy pero volveria a romperse si el run corriera cerca de
        medianoche. Leerlo del dato es inmune al huso."""
        import sqp.audit.html_report as hr

        capturado = {}
        real = hr._picks_records

        def espia(pred_dir, generated_day=None):
            capturado.setdefault("dias", []).append(generated_day)
            return real(pred_dir, generated_day=generated_day)

        monkeypatch.setattr(hr, "_picks_records", espia)
        hr.html_dashboard(predictions_dir=tmp_path / "p",
                          bets_dir=tmp_path / "b", make_latest=False)
        assert capturado["dias"] == [None]

    def test_cae_al_dia_mas_reciente_si_hoy_no_hay(self, tmp_path):
        """Mejor los candidatos de ayer que un tablero en blanco: el blanco es
        lo que hizo creer al operador durante 53 dias que no se generaba nada."""
        pred = tmp_path / "p"
        pred.mkdir()
        df = pd.DataFrame([{
            "event_id": "e1", "league": "mlb", "market": "h2h", "selection": "A",
            "line": None, "price_decimal": 2.0, "estimated_probability": 0.55,
            "implied_probability_novig": 0.5, "estimated_edge": 0.1,
            "kelly_stake_pct": 0.0, "stake": 0.0, "home": "H", "away": "V",
            "flags": "prediction_gate", "data_label": "real",
            "start_time": "2020-01-01T18:00:00Z",
            "generated_at": "2020-01-01T11:00:00+00:00"}])
        (pred / "candidates_mlb.csv").write_text(df.to_csv(index=False),
                                                 encoding="utf-8")
        from sqp.audit.html_report import html_dashboard
        import json
        import re
        path = html_dashboard(predictions_dir=pred, bets_dir=tmp_path / "b",
                              make_latest=False)
        txt = open(path, encoding="utf-8").read()
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", txt, re.S).group(1))
        assert len(data["picks"]) == 1
