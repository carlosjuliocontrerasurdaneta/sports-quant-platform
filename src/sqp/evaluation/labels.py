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


def tz_local():
    """Zona horaria LOCAL de la maquina.

    Vive como funcion, y no inline en los tres sitios que la usaban, por la
    misma razon por la que `picks_vigentes` acepta `ahora`: para que un test
    pueda fijarla. Sin esto, cualquier prueba de la conversion UTC->local mide
    en realidad la zona del runner -- y `test_el_tipster_no_depende_de_que_el_
    llamador_convierta` afirmaba que la fecha convertida DIFIERE de la cruda,
    lo cual es falso en UTC: pasaba en la maquina de desarrollo (UTC+2) y
    fallaba en el CI (UTC) desde el 2026-09-02.
    """
    return datetime.now(timezone.utc).astimezone().tzinfo


def local_today() -> str:
    """Fecha de HOY en hora local, `YYYY-MM-DD`. La pareja de
    `game_date_local`: comparar una contra una fecha UTC volveria a introducir
    el desfase que este modulo existe para eliminar."""
    return datetime.now(timezone.utc).astimezone(tz_local()).date().isoformat()


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
    tz = tz_local()
    fecha = ts.dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    return fecha.fillna(valores.astype(str).str[:10]).astype(str)


def instantes_utc(valores: pd.Series | None, *,
                  index: pd.Index | None = None) -> pd.Series:
    """Serie de instantes UTC con la MISMA gramatica que el parser canonico.

    Tres razones para que el parseo viva en un solo sitio:

    1. `format="ISO8601"` no es opcional. Sin el, pandas infiere UN formato para
       toda la serie: con `['...T23:00:00Z', '...T18:00:00']` (aware seguido de
       naive, ambos ISO validos) devuelve `NaT` para el segundo, y un partido ya
       empezado se colaba como vigente. Reproducido con pandas 3.0.2.
    2. En sentido contrario, el parser por defecto ACEPTA `09/02/2026 18:00:00`,
       que `pipeline.daily._parse_iso_utc` rechaza. Eso saltaba el fallback por
       fecha que el contrato conservador exige. Con `ISO8601` da `NaT`, igual
       que el canonico.
    3. El dtype queda SIEMPRE con zona horaria. Sin columna, o con todo `NaT`,
       pandas produce un `datetime64[ns]` naive y compararlo con un instante con
       zona lanza `TypeError`.

    Ambas divergencias las encontro la revision independiente de Codex sobre
    este mismo cambio (2026-09-02).
    """
    idx = index if index is not None else (
        valores.index if valores is not None else None)
    vacio = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns, UTC]")
    if valores is None:
        return vacio
    parsed = pd.to_datetime(valores, errors="coerce", utc=True, format="ISO8601")
    return parsed if getattr(parsed.dt, "tz", None) is not None else vacio


EN_JUEGO = "en_juego"


def ya_empezado(df: pd.DataFrame, *, ahora: datetime | None = None) -> pd.Series:
    """Serie booleana: True donde el partido YA EMPEZO.

    Definicion CANONICA de "empezado" para la capa de vistas, y la unica: la
    usan `picks_vigentes` para excluir y `picks_vigentes_unicos` para MARCAR lo
    que el fallback resucita (KI-030). Tenerla en un solo sitio es lo que impide
    que las dos respuestas diverjan -- que es como nacio KI-027.

    Un sello ILEGIBLE o ausente cuenta como NO empezado, igual que en
    `pipeline.daily._already_started`: no poder leer la hora no demuestra que el
    partido se haya jugado, y en la duda se conserva la fila. `instantes_utc`
    aporta la gramatica de parseo (ver su docstring: sin `format="ISO8601"` un
    naive detras de un aware daba NaT y un partido empezado se colaba).
    """
    if df.empty:
        return pd.Series(False, index=df.index, dtype=bool)
    ahora = ahora or datetime.now(timezone.utc)
    inicio = instantes_utc(df.get("start_time"), index=df.index)
    return inicio.notna() & (inicio <= ahora)


def picks_vigentes(df: pd.DataFrame, *, hoy: str | None = None,
                   ahora: datetime | None = None) -> pd.DataFrame:
    """Filas cuyo partido TODAVIA SE PUEDE APOSTAR: no ha empezado.

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

    EL CRITERIO ES EL INSTANTE, NO LA FECHA (KI-028, corregido el 2026-09-02).
    Comparaba solo fechas locales, asi que un partido que empezo hace horas
    seguia listado como vigente hasta que cambiaba el dia. No es cosmetico: el
    sistema es PREGAME, y una vez empezado el partido las cuotas que muestra la
    vista son en vivo, no las que se estimaron. Medido el 2026-09-01 a las 19:00
    locales: 66 de los 128 picks del dia ya habian empezado. Sobre los 156
    partidos de hoy, a las 23:00 UTC habrian empezado 142 -- el 91% de la lista
    por defecto seria inapostable.

    "Empezado" usa la MISMA semantica que `pipeline.daily._already_started`, que
    ya suprime candidatos de eventos en juego: el instante de inicio es pasado, y
    un sello ILEGIBLE se trata como NO empezado (conservador, porque no poder
    leer la hora no demuestra que el partido se jugara). La definicion no se
    importa de `pipeline` para no acoplar `evaluation` a el; un test fija que
    ambas coinciden, que es lo que impide la deriva.

    `ahora` es inyectable para poder fijar la frontera en los tests sin depender
    del reloj.
    """
    if df.empty:
        return df
    empezado = ya_empezado(df, ahora=ahora)
    fecha = game_date_local(df)
    con_fecha_vigente = (fecha == "") | (fecha >= (hoy or local_today()))
    # La fecha sigue filtrando a los que NO tienen sello legible: sin instante no
    # hay nada mejor, y sin ella una fila vieja sin `start_time` viviria siempre.
    return df[~empezado & con_fecha_vigente]


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

    EL FALLBACK MARCA, NO SUPRIME (KI-030, cerrado el 2026-09-04). La caida al
    ultimo dia generado devuelve las filas TAL CUAL, incluidas las de partidos ya
    empezados. Desde que la vigencia se decide por INSTANTE, eso significa que en
    cuanto arranca el ultimo partido pendiente la vista resucita el lote entero YA
    EN JUEGO -- y hasta el 2026-09-04 lo mostraba como si fueran picks pregame,
    con cuotas que a esas alturas son EN VIVO. Lo reprodujo Codex revisando el
    cambio de KI-028.

    Se resolvio SIN tocar el fallback, que es la decision del 2026-08-28 (leccion
    de los 53 dias: un tablero en blanco hizo creer al operador que el sistema no
    generaba nada) y esta fijado por `test_cae_al_dia_mas_reciente_si_hoy_no_hay`.
    Suprimir esas filas habria cambiado una decision registrada para arreglar un
    problema que no era la presencia de las filas sino la MENTIRA sobre su estado.

    Por eso el frame devuelto lleva SIEMPRE la columna booleana ``en_juego``
    (`EN_JUEGO`): False en toda la ruta normal por construccion -- ahi no hay
    partidos empezados --, y la verdad por fila en la ruta del fallback. Anotarlo
    aqui y no en cada vista es deliberado: un consumidor puede olvidarse de
    calcular el marcador, pero no puede olvidarse de una columna que ya viene en
    su frame. La deriva entre copias es el modo de fallo dominante de este repo
    (KI-027).

    Alcance real: con horizonte de 7 dias hacen falta CERO filas apostables en
    todo el stream para alcanzar el fallback, asi que hoy no se dispara (1.920
    vigentes el 2026-09-02).
    """
    if df.empty:
        return df
    vigentes = picks_vigentes(df, hoy=hoy)
    if vigentes.empty:
        # Sin nada vigente se cae al ultimo dia generado; si ni siquiera hay
        # `generated_at`, se devuelve todo antes que dejar la vista en blanco.
        # En las DOS ramas se marca: son justo las filas que pueden estar en
        # juego, y devolverlas sin marcar es el defecto que cerro KI-030.
        caida = (df if "generated_at" not in df.columns
                 else df[df["generated_at"].astype(str).str[:10]
                         == df["generated_at"].astype(str).str[:10].max()])
        return caida.assign(**{EN_JUEGO: ya_empezado(caida)})
    # Colapsar EXIGE la identidad completa. Con una clave parcial, dos partidos
    # distintos que compartan mercado/seleccion/linea (p. ej. dos `totals/Over
    # 2.5`) se fusionarian en uno: borrar filas porque falta una columna es la
    # averia que este proyecto lleva repitiendo, y aqui incumpliria ademas la
    # REGLA FUNDAMENTAL. Sin identidad se conservan todas.
    if not set(_IDENTIDAD_PICK).issubset(vigentes.columns):
        return vigentes.assign(**{EN_JUEGO: False})
    claves = [*_IDENTIDAD_PICK] + (["line"] if "line" in vigentes.columns else [])
    if "generated_at" in vigentes.columns:
        # `sort` estable: ante sellos repetidos manda el orden de llegada, que en
        # un fichero append-only es el cronologico.
        vigentes = vigentes.sort_values("generated_at", kind="stable")
    # Sin `generated_at` no se puede afirmar cual es la mas reciente, pero el
    # stream es append-only: la ultima del fichero es la ultima servida.
    #
    # `en_juego` es False por CONSTRUCCION en esta ruta: `picks_vigentes` ya
    # excluyo todo lo empezado. Se anade igualmente para que la columna exista
    # SIEMPRE y ningun consumidor tenga que preguntarse si esta -- un
    # `df["en_juego"]` que a veces lanza KeyError acabaria en un `.get(...)`
    # silencioso, y de ahi a no mostrar el aviso hay un paso.
    return vigentes.drop_duplicates(claves, keep="last").assign(**{EN_JUEGO: False})


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
        # Mismo parser que `picks_vigentes` (ver `instantes_utc`): sin el, una
        # serie con formatos ISO mezclados daba NaT y la fecha mostrada caia al
        # `game_date` crudo del proveedor, que es UTC -- justo el desfase que
        # esta funcion existe para eliminar.
        st = instantes_utc(df["start_time"], index=df.index)
        tz = tz_local()
        fecha = st.dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    else:
        fecha = pd.Series(pd.NA, index=df.index, dtype="object")
    if "game_date" in df.columns:
        fecha = fecha.fillna(df["game_date"].astype(str).str[:10])
    return fecha.fillna("").astype(str)
