"""Ventana de fechas para los fetch de resultados de los proveedores.

Los proveedores (ESPN, MLB StatsAPI) piden resultados por RANGO DE FECHAS
CIVILES, no por instantes. Antes cada uno construia ese rango con
`date.today()`, que es la fecha LOCAL de la maquina. Eso rompe por los dos
extremos:

- **Por el final.** Esta maquina corre en UTC-4. A las 21:00 locales ya son las
  01:00Z del dia siguiente, y `date.today()` sigue diciendo "ayer". Un partido
  que el proveedor indexa en la fecha nueva queda FUERA del rango y no se
  liquida en esa pasada.
- **Por la zona del recinto.** El proveedor no indexa por UTC sino por la fecha
  local del partido, que va de UTC-11 a UTC+14. Un partido en Oceania puede
  aparecer un dia por delante de UTC; uno en Hawai, un dia por detras.

Asi que el rango se ancla en UTC y se ensancha un dia por cada lado. Es un
SUPERCONJUNTO estricto de lo que devolvia la version local en cualquier zona
horaria: nunca puede perder un dia que antes si entraba.

Coste de los dos dias extra: cero en las consultas por rango (MLB StatsAPI y el
modo chunked de ESPN mandan la misma cantidad de peticiones); en el modo
`day_by_day` de ESPN y en tenis son dos peticiones mas por fetch sobre las
`days_back` que ya hace (2 de 367 en un backfill anual). Ninguna toca la cuota
de The Odds API, que es la unica de pago.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Las fechas locales de los recintos van de UTC-11 a UTC+14, asi que la fecha
# civil con la que el proveedor indexa un partido puede ir un dia por delante o
# por detras de la fecha UTC del mismo instante.
VENUE_TZ_MARGIN_DAYS = 1


def utc_today() -> date:
    """Fecha UTC de hoy. Nunca usar `date.today()` para hablar con proveedores:
    es hora local y en UTC-4 va un dia por detras media noche de cada dia."""
    return datetime.now(timezone.utc).date()


def fetch_window(days_back: int, *, today: date | None = None) -> tuple[date, date]:
    """Rango `(start, end)` inclusivo para pedir `days_back` dias de resultados.

    `today` solo existe para los tests; en produccion se toma de UTC.
    """
    if days_back < 0:
        raise ValueError(f"days_back debe ser >= 0, recibido {days_back}")
    ref = today if today is not None else utc_today()
    start = ref - timedelta(days=days_back + VENUE_TZ_MARGIN_DAYS)
    end = ref + timedelta(days=VENUE_TZ_MARGIN_DAYS)
    return start, end
