# Resumen ejecutivo — Auditoría integral 2026-07-29/30

Commit base: `4036fea` · Rama: `main` · Python 3.14.4 · Sin commit realizado.

## Estado general

**La calidad de software es alta. La validez predictiva no está demostrada.** Son
dos cosas distintas y este informe las mantiene separadas.

Lo primero: el repositorio tiene atomicidad de escrituras, lock inter-proceso,
separación crudo/derivado, split temporal por evento en calibración, walk-forward
real en el backtest de ratings, redacción de credenciales en excepciones,
timeouts en las 8 llamadas HTTP y 466 pruebas verdes. No hay secretos versionados
ni en el historial (174 commits revisados).

Lo segundo: **el modo precisión que corre en producción desde el 2026-07-28
descansa sobre una premisa que hoy no se cumple**, y su output operativo estaba
caído sin que nadie lo notara.

## Riesgos principales

| # | Riesgo | Severidad | Estado |
|---|---|---|---|
| 1 | Los picks de producción eran **invisibles en todos los reportes**: el filtro comparaba `flags` por igualdad exacta y el modo precisión concatena `"shadow_mode;accuracy_mode"`. Dashboard, reporte consolidado y ranking devolvían 0 picks. | CRÍTICO | **Corregido** (B-01) |
| 2 | El umbral 0.70 **no se aplica a una probabilidad calibrada**: no existe calibrador promovido para `(liga, h2h)`, así que `calibrate_probability` es un no-op. La columna se llama `calibrated_probability` de todos modos. | CRÍTICO | **Aviso implementado**; la decisión de política es humana (Q-01) |
| 3 | La selección es **cuasi-tautológica**: `p_decision = 0.5·p_model + 0.5·fair`, así que "≥0.70" equivale a `p_model + fair ≥ 1.40`, y el mercado aporta la mitad del criterio. El edge se calcula contra el precio CON vig, luego los picks tienen EV estimado negativo por construcción. | ALTO | **Requiere decisión humana** (Q-02) |
| 4 | El modo precisión eludía el **único filtro de cuotas degeneradas** del pipeline (`kelly.py`), y existen cuotas `1.0` en el histórico capturado. | ALTO | **Corregido** (B-05, B-13) |
| 5 | `shadow_mode` tenía un **fail-open**: un `SHADOW_MODE` con valor no reconocido (vacío, `on`, con espacio) anulaba el `shadow_mode: true` del yaml y resolvía a `False`, sin log. | ALTO | **Corregido** (B-08) |
| 6 | **La política vigente no tiene backtest.** `validate_oos.py` y `backtest_roi.py` miden la regla por edge/Kelly. El −5.32% de ROI OOS conocido no describe el modo precisión. | ALTO | **Pendiente** (B-02) |
| 7 | El run diario **falló el 2026-07-29** (`LastTaskResult = 1`) y no existe ningún mecanismo de alerta en el repositorio. | ALTO | **Requiere decisión humana** (S-1) |
| 8 | Los 14 Quant Loops no definían `PASS`/`DEGRADED`/`BLOCKED`/`DONE`; usaban cinco vocabularios distintos y ninguno con umbral. | ALTO | **Corregido** (K-003) |
| 9 | 10 agentes y 5 rutas enrutaban a `fable`, modelo **sin créditos en la cuenta**, sin fallback: los subagentes más críticos fallaban al arrancar. Verificado en esta misma auditoría. | ALTO | **Corregido** (K-004) |

## Mejoras realizadas

14 hallazgos corregidos, cada uno con prueba de regresión (27 pruebas nuevas):

- **Producción**: visibilidad de picks en reportes, guarda de cuota degenerada en
  la selección de precisión y en el consenso no-vig, piso de banca en 0, cierre
  del fail-open de los 8 flags de entorno booleanos, aviso cuando el modo
  precisión corre sin calibrador.
- **Datos**: 4 escrituras no atómicas convertidas a atómicas (una de ellas,
  `predictions_*.csv`, es la fuente de `start_time` para el cálculo de riesgo);
  el upsert de abridores ya no sobrescribe nombres buenos con nulos; reintento en
  429; reset del contador de créditos por llamada.
- **Seguridad / CI**: mypy incorporado a CI (pasaba en verde y no se ejecutaba),
  Docker sin root, `Makefile` con lockfile, detector de secretos ampliado a tres
  formatos que eran ciegos (verificado por ejecución), clave de API fuera del
  `repr`, `ruff target-version` coherente con `requires-python`.
- **Claude Code**: definición exacta de los cuatro estados de salida en
  `STATES.md` referenciada por los 14 loops; orden crítico SETTLE→RUN corregido
  en el loop 01 y en `.claude/CLAUDE.md`; `shadow_mode` añadido literalmente a
  los gates de aprobación; conflicto entre dos protocolos de memoria resuelto;
  política de modelos unificada en una sola fuente; 17 duplicados mojibake de la
  bóveda Obsidian eliminados tras verificar byte-identidad.

## Preparación para shadow

**Adecuada, y ahora mejor que antes.** `shadow_mode: true` sigue activo, se
verificó que no existe ninguna ruta de código que lo eluda (un solo
`BetCandidate(`, la revalidación solo baja stakes, los caps solo escalan
`stake > 0`), y el fail-open que sí podía eludirlo quedó cerrado. Con B-01
corregido, el periodo de shadow por fin produce evidencia observable.

Lo que falta para que el shadow sea informativo, no solo inocuo: los picks aún no
tienen backtest de su propia regla (B-02) y el gate de salida del shadow para el
modo precisión no está definido — es la tarea nº1 de `Obsidian/Tareas.md` y
ningún loop la cubre (K-010).

## Preparación para dinero real

**No preparada. No hay evidencia que la respalde.**

1. No existe estimación out-of-sample del hit rate del umbral 0.70. La única
   evidencia OOS del repositorio (−5.32% ROI) corresponde a otra regla de
   selección.
2. El backtest está anclado al cierre y producción a la apertura; el propio
   código lo documenta. El sesgo va en la dirección desfavorable: el resultado
   real esperado es **peor** que el del backtest (B-03).
3. Los parámetros de riesgo se sintonizaron sobre la misma ventana que luego se
   llama OOS (B-04).
4. No hay intervalos de confianza en ninguna métrica, y los gates disparan sobre
   `n` de 15–30 con umbrales por debajo del ruido muestral (B-11).
5. No hay kill switch ni límite de drawdown con enforcement (B-15).
6. Sigue habiendo un agujero latente post-shadow: banca negativa producía stakes
   negativos y `settle.py` convierte una pérdida en ganancia (`pnl = -stake`).
   Corregido, pero es señal de que la ruta con dinero real no está ejercitada.

## Conclusión

El repositorio queda en mejor estado, más consistente y más auditable que al
empezar: 14 defectos reales corregidos con prueba, un fallo crítico de
observabilidad reparado, un fail-open de seguridad cerrado y la capa de
instrucciones de Claude Code hecha verificable.

Nada de esto es evidencia de que el sistema pueda ganar dinero. El hallazgo
central de la auditoría es que **el modo precisión mide contra un umbral que hoy
no describe lo que el sistema estima**: sin calibrador h2h, "probabilidad
calibrada ≥ 0.70" es "media de un modelo no calibrado y del favorito del mercado
≥ 0.70". El hit rate que se observe debe juzgarse contra la frecuencia observada
por banda, nunca contra el 0.70 nominal.

Estado final: **DONE para el alcance de corrección**, con seis decisiones
pendientes de autorización humana listadas en `BACKLOG.md`.
