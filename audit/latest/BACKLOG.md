# Backlog — Auditoría 2026-09-06

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.

## Primera prioridad del próximo ciclo

### B-1 · Los seis hallazgos de la auditoría concurrente de Codex (2026-09-06)

Un proceso externo de Codex reescribió `auditoria-integral-codex.md` durante esta
sesión con una auditoría nueva del **mismo commit** `01993fd`. Reporta tres HIGH
y tres MEDIUM, todos `REPRODUCED`. **Quedan fuera de la aprobación de esta
sesión** («todos los confirmados» se resolvió contra los IDs de *este* informe) y
requieren aprobación propia.

Se verificó que ninguno colisiona con los parches aplicados (detalle en
`FINDINGS.md`, sección final).

**AUD-20260906-01 quedó CORREGIDO** el mismo 2026-09-06, autorizado aparte por
el operador (KI-032). Era un hallazgo legítimo que *esta* auditoría no encontró:
`_exigir_pnl_legible` sólo rechaza el fichero cuando **no queda ningún** PnL
numérico, así que una corrupción **parcial** atravesaba el `fillna(0.0)` y
convertía una pérdida en un movimiento de cero. Reproducido antes de parchear:
banca 1.000 con dos pérdidas de −400 daba **600** en vez de 200, y
`apply_dynamic_bankroll` aceptaba esa cifra. Ahora lanza y el staking cae a 0.

La discriminación es **por tipo de movimiento**, no por severidad: `settle.py`
grada push y void con `pnl` 0.0 explícito, así que un importe vacío en esos dos
estados sigue siendo un cero legítimo y la decisión registrada en
`test_un_push_con_pnl_vacio_no_dispara_la_guarda` **no se contradice** — que es
también lo que proponía Codex. Impacto en producción: ninguno; medido antes de
endurecer la guarda, de las 1.305 filas reales y los 2 ajustes **cero** tienen
importe no numérico, y el balance real sigue siendo 915,75.

**Quedan los otros cinco (AUD-20260906-02..06). Para cerrarlos:** aprobación
explícita por ID.

### B-2 · Causa raíz del fallo de `SQP_Validate_OOS_Cdev` del 2026-09-01

`rc=0x1` observado en el Programador de tareas. `validate_oos.py:main()` devuelve
1 tanto por excepción no capturada como por la rama benigna «liga sin cuotas de
cierre». Se comprobó hoy que de **33 ligas descubiertas, 0** carecen de cierre
utilizable, así que esa rama no lo explicaría hoy.

**Bloqueado por:** `logs/validate_oos.log` está denegado por la política de
permisos (`Read(./logs/**)` en `.claude/settings.json`).

**Para cerrarlo:** autorización puntual para un `grep -E "Traceback|ERROR"` sobre
ese log. El aviso ya está arreglado (AUD-MED-003); lo que falta es el
diagnóstico. La tarea no se reintenta sola hasta el **2026-10-01**.

**Sugerencia aparte:** separar los dos códigos de salida de `validate_oos.py`
—«nada que validar» no es un fallo— para que el centinela nuevo no marque en rojo
una condición benigna. Requiere decisión: cambia el contrato de salida del script.

## Requiere decisión humana

### B-3 · Base del `Dockerfile`

La imagen fija `python:3.11-slim`; producción corre 3.14. Se corrigió la
afirmación falsa (AUD-LOW-004) pero **no** la base: alinearla exige construir la
imagen para validarla, y ningún paso de CI la construye. Las opciones son
alinearla a 3.14 y añadir un `docker build` al CI, o dejarla declarada como
entorno de demo, que es lo que ahora dice.

### B-4 · Limpieza de residuo en disco (≈205 MB, todo ignorado por git)

Propuesto en el informe de auditoría y **no autorizado**, así que no se tocó:

| ID | Ruta | Categoría | Tamaño |
|---|---|---|---|
| CL-01 | `graphify-out/2026-07-08 … 2026-09-05` (39 dirs) | `GENERADO_RECONSTRUIBLE` | ~180 MB |
| CL-02 | `.codex-tmp/run-2026081*` (20 dirs) | `ELIMINABLE_CONFIRMADO` | 25 MB |
| CL-03 | `.claude/hooks/__pycache__/` | `OBSOLETO_REEMPLAZADO` | trivial |

`CL-05` (`.claude/reviews/runtime/`, 965 ficheros) y `CL-06`
(`audit/full-audit-SKILL-reemplazado-2026-08-30.md`) se clasificaron
`NO_VERIFICABLE` / `CONSERVAR` y **no** entran en ningún plan de borrado.

## Inferidos: falta evidencia

### B-5 · AUD-INF-001 · Carrera del lock huérfano

`storage/lock.py` rompe un `.lock` a los 300 s y el titular, al salir, hace
`unlink()` sin comprobar que siga siendo suyo. No se encontró ninguna sección
crítica capaz de superar 300 s desde que `d27fdd4` sacó la red fuera.

**Para cerrarlo:** medir la duración real de la retención del lock en producción.
Si ninguna se acerca a 300 s, se descarta; si alguna lo hace, es HIGH.

### B-6 · AUD-INF-002 · Temporales de nombre fijo

`clv_gate.write_clv_gate` y los dos escritores de `promotion_log.csv` usan
`with_suffix(".tmp")` fijo, patrón que `atomic_write_csv` abandonó por colisión
entre escritores concurrentes. Hoy los escribe un único proceso diario.

**Para cerrarlo:** decidir si se unifican con el patrón de `atomic_write_csv`
(temporal único por proceso y llamada) por prevención, o se documenta que son
escritores únicos.

## Cobertura pendiente

### B-7 · Áreas excluidas por política de permisos

`logs/` y `.env` quedaron `EXCLUIDA`. La coherencia `.env` ↔
`configs/default.yaml` no pudo verificarse directamente; el mecanismo que la
vigila (`_warn_risk_divergence`) existe y se ejecuta en cada `Settings.load()`,
pero su veredicto vive en el log.

### B-8 · Presupuesto del hook de revisión cruzada

`crossreview-on-stop.sh` tiene un timeout de 600 s y no se ha medido cuánto tarda
`codex review` en este repositorio. Es el mismo tipo de brecha que AUD-HIGH-001
del 2026-09-04 (un hook cuyo trabajo no cabía en su timeout). Medirlo consume una
llamada de pago, así que requiere autorización.
