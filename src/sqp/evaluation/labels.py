"""Como se identifica un partido -- NOMBRE y FECHA -- en las vistas de picks.

Una sola definicion de cada cosa, porque las dos se habian duplicado a mano:

- **Nombre.** "Picks del Dia" mostraba el partido y las otras tres vistas no: en
  `totals` la seleccion es literalmente "Over"/"Under", asi que una fila decia
  `mlb | totals | Over | 8.5` sin decir de QUE partido (operador, 2026-08-26).
  Los datos siempre estuvieron ahi; no se arrastraban a la tabla.
- **Fecha.** La columna `game_date` del stream viene del proveedor en **UTC**, y
  un partido nocturno en EEUU empieza despues de las 00:00Z: en UTC cae en el
  dia siguiente. Tres vistas convertian a hora local por su cuenta y
  `tipster_table` no convertia -- funcionaba solo porque su unico llamador le
  sobrescribia `game_date` antes de llamarla. Cualquier otro llamador obtenia
  fechas UTC en silencio. Ahora la conversion vive aqui y no se puede saltar.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

SEPARADOR = " @ "  # visitante @ local, la convencion que ya usaba "Picks del Dia"


def decision_prob(df: pd.DataFrame) -> pd.Series:
    """Probabilidad con la que el sistema DECIDIO el pick: la calibrada cuando
    existe, con fallback POR FILA a la estimada.

    Tercera definicion compartida que vive aqui por la misma razon que las otras
    dos. `_decision_probability` (pipeline/probabilities.py) devuelve dos
    probabilidades: `p_used` es la mezcla CRUDA sin calibrar y se guarda como
    `estimated_probability`; `p_decision` lleva el calibrador aplicado, se guarda
    como `calibrated_probability` y es la que produce `estimated_edge`
    (`daily.py:841`). `segments` ya usaba la correcta desde la decision del
    2026-07-27 -- "medir sobre otra probabilidad que la que decidio el pick
    distorsionaria el control" -- pero `html_report._todos_records` y
    `tipster_table` seguian con la cruda.

    Medido sobre las ultimas 2.000 filas de `served_mlb.csv` (auditoria
    2026-08-31, A-01): `estimated_edge` es consistente con la calibrada en
    2.000/2.000 filas y con la estimada en 729; ambas difieren en 1.272 filas
    (hasta 8,95 pp), el signo del margen cambia en 252, y la lista de "margen
    positivo" contaba 441 selecciones en vez de 271.
    """
    est = pd.to_numeric(df.get("estimated_probability"), errors="coerce")
    cal = pd.to_numeric(df.get("calibrated_probability"), errors="coerce")
    if not isinstance(est, pd.Series):
        est = pd.Series(est, index=df.index, dtype=float)
    if not isinstance(cal, pd.Series):
        cal = pd.Series(cal, index=df.index, dtype=float)
    return cal.fillna(est)


def match_label(df: pd.DataFrame, *, fallback: str = "event_id") -> pd.Series:
    """Serie `"visitante @ local"` alineada con `df`.

    Si faltan `home`/`away` cae a `fallback` (por defecto `event_id`): un
    identificador feo identifica el partido, una celda vacia no.
    """
    if "home" in df.columns and "away" in df.columns:
        return (df["away"].fillna("").astype(str) + SEPARADOR
                + df["home"].fillna("").astype(str))
    if fallback in df.columns:
        return df[fallback].fillna("").astype(str)
    return pd.Series("", index=df.index, dtype=str)


def local_today() -> str:
    """Fecha de HOY en hora local, `YYYY-MM-DD`. La pareja de
    `game_date_local`: comparar una contra una fecha UTC volveria a introducir
    el desfase que este modulo existe para eliminar."""
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def local_date(valores: pd.Series) -> pd.Series:
    """Fecha LOCAL (`YYYY-MM-DD`) de una serie de instantes UTC.

    Para `generated_at` y demas sellos que el pipeline escribe en UTC. Truncarlos
    con `str[:10]` da la fecha UTC, y compararla contra `local_today` vuelve a
    introducir el desfase que este modulo existe para eliminar: a partir de las
    20:00 locales (00:00Z) el sello dice manana. Medido el 2026-08-28 a las 20:26
    locales, el aviso de cobertura del tablero declaraba "0 de 14 ligas
    refrescadas hoy" horas despues de un run correcto.

    Donde no parsee, cae al truncado en crudo: una fecha aproximada informa, una
    celda vacia no.
    """
    ts = pd.to_datetime(valores, errors="coerce", utc=True)
    tz = datetime.now(timezone.utc).astimezone().tzinfo
    fecha = ts.dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    return fecha.fillna(valores.astype(str).str[:10]).astype(str)


def picks_vigentes(df: pd.DataFrame, *, hoy: str | None = None) -> pd.DataFrame:
    """Filas cuyo PARTIDO no se ha jugado todavia (fecha local >= hoy).

    Es el filtro correcto para una lista de picks, y no «lo generado en el ultimo
    run», que era lo que hacian las vistas. La diferencia no es teorica: el run
    guarda 7 dias de horizonte y las ligas no se refrescan todas cada dia -- el
    guardian de presupuesto aplazo 14 ligas el 2026-08-27, y un run que cruza la
    medianoche parte los candidatos en dos dias de generacion. Medido el
    2026-08-28: «Todos los Picks» mostraba **82 filas de UNA liga** mientras
    quedaban **577 filas de 13 ligas con el partido por jugar**, invisibles solo
    porque otra liga se sirvio despues.

    Esconder un pick vigente contradice la REGLA FUNDAMENTAL del operador (la
    lista es de TODOS los deportes y mercados). Lo que si hay que decir es de
    cuando es cada fila: la vista muestra la fecha de generacion al lado, para
    que una cuota de hace tres dias no se lea como fresca.

    Una fila SIN fecha conocida se conserva. No poder fechar un partido no
    demuestra que se haya jugado, y borrar filas porque falta una columna es la
    averia que este proyecto lleva repitiendo -- el mismo esquema legado que
    `game_date_local` ya tolera devolviendo cadena vacia.
    """
    if df.empty:
        return df
    fecha = game_date_local(df)
    return df[(fecha == "") | (fecha >= (hoy or local_today()))]


# Identidad MINIMA de un pick. Sin estas tres no se puede afirmar que dos filas
# sean el mismo pick, y colapsarlas borraria picks distintos. `line` se anade
# cuando existe, pero no es obligatoria: en `h2h` es nula por definicion.
_IDENTIDAD_PICK = ("event_id", "market", "selection")


def picks_vigentes_unicos(df: pd.DataFrame, *, hoy: str | None = None) -> pd.DataFrame:
    """Picks vigentes con UNA fila por pick: la servida mas RECIENTE.

    Es el criterio completo de una lista de picks, y vive aqui porque estaba
    duplicado a mano. `picks_vigentes` sola no basta sobre el stream servido: ese
    stream ACUMULA una fila por dia de horizonte (`served_store.KEY_COLS` lleva
    `generated_at`), asi que sin colapsar, el mismo pick sale hasta siete veces.
    Medido el 2026-09-01: 2.182 filas vigentes para 1.000 picks reales.

    Se conserva la mas reciente porque aqui manda el ULTIMO precio conocido, al
    reves que en la medicion de ROI, donde vale el del momento de decidir.

    Si no queda NINGUN pick vigente se cae al ultimo dia generado, aunque sus
    partidos ya se hayan jugado: un tablero en blanco es lo que hizo creer al
    operador durante 53 dias que el sistema no generaba nada.

    El arreglo del 2026-08-28 aplico esta logica a las tres vistas del dashboard
    y dejo fuera `scripts/daily_picks.py` y `scripts/tipster_report.py`, que son
    los que invoca `DIARIO_COMPLETO.bat` (KI-027). Extraerla evita la cuarta
    divergencia: el modo de fallo dominante de este repo es la deriva entre
    artefactos duplicados.

    LIMITE CONOCIDO: `picks_vigentes` compara FECHAS, no instantes, asi que un
    partido que empezo hace horas sigue contando como vigente hasta que cambia el
    dia local. Medido el 2026-09-01: 66 de los 128 picks de hoy ya habian
    empezado (ninguno con stake). Es el criterio canonico desde el 2026-08-28 y
    NO se cambia aqui: tocarlo afectaria tambien a las tres vistas del dashboard
    y es una decision de negocio del operador, no del que corrige un CLI.
    """
    if df.empty:
        return df
    vigentes = picks_vigentes(df, hoy=hoy)
    if vigentes.empty:
        # Sin nada vigente se cae al ultimo dia generado; si ni siquiera hay
        # `generated_at`, se devuelve todo antes que dejar la vista en blanco.
        if "generated_at" not in df.columns:
            return df
        gen = df["generated_at"].astype(str).str[:10]
        return df[gen == gen.max()]
    # Colapsar EXIGE la identidad completa. Con una clave parcial, dos partidos
    # distintos que compartan mercado/seleccion/linea (p. ej. dos `totals/Over
    # 2.5`) se fusionarian en uno: borrar filas porque falta una columna es la
    # averia que este proyecto lleva repitiendo, y aqui incumpliria ademas la
    # REGLA FUNDAMENTAL. Sin identidad se conservan todas.
    if not set(_IDENTIDAD_PICK).issubset(vigentes.columns):
        return vigentes
    claves = [*_IDENTIDAD_PICK] + (["line"] if "line" in vigentes.columns else [])
    if "generated_at" in vigentes.columns:
        # `sort` estable: ante sellos repetidos manda el orden de llegada, que en
        # un fichero append-only es el cronologico.
        vigentes = vigentes.sort_values("generated_at", kind="stable")
    # Sin `generated_at` no se puede afirmar cual es la mas reciente, pero el
    # stream es append-only: la ultima del fichero es la ultima servida.
    return vigentes.drop_duplicates(claves, keep="last")


def game_date_local(df: pd.DataFrame) -> pd.Series:
    """Fecha del PARTIDO en hora local (`YYYY-MM-DD`), alineada con `df`.

    Se deriva de `start_time` (instante UTC), no de `game_date`: esa columna la
    escribe el proveedor en UTC y un partido nocturno en EEUU empieza despues de
    las 00:00Z, asi que en UTC aparece como del dia siguiente. Un WNBA a las
    22:00 hora local sale archivado como de manana.

    No es la fecha de GENERACION: el run guarda 7 dias de horizonte, asi que
    "generado hoy" incluye partidos de hasta 6 dias despues (de las 541 filas
    del 2026-08-26, solo 105 se jugaban ese dia).

    Donde `start_time` falte o no parsee, cae a `game_date` en crudo: una fecha
    aproximada situa el partido, una celda vacia no.
    """
    if "start_time" in df.columns:
        st = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
        tz = datetime.now(timezone.utc).astimezone().tzinfo
        fecha = st.dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    else:
        fecha = pd.Series(pd.NA, index=df.index, dtype="object")
    if "game_date" in df.columns:
        fecha = fecha.fillna(df["game_date"].astype(str).str[:10])
    return fecha.fillna("").astype(str)
