# Resumen ejecutivo — Auditoría integral 2026-08-04

Sustituye el contenido de `audit/latest/` de la auditoría del 2026-08-02
(conservada en el historial git). Alcance: código, configuración, dependencias,
seguridad, operación, documentación, `.claude`/Quant Loops. `data/`,
`historical/`, `logs/` y `exports/` **no se escanearon** (regla permanente del
proyecto); la dimensión de datos se auditó a nivel de código, esquemas y health
check.

Rama: `fix/claude-audit-20260804` · Commit base: `2a293cb` · Python 3.14.4 ·
**Sin commit realizado.**

## Estado general: BUENO — con un fallo de proceso confirmado y recurrente

Las puertas técnicas quedan verdes y verificadas por ejecución real (no por
documentación): 618 tests, ruff limpio, mypy limpio (89 archivos), `pip check`
limpio, `compileall` limpio. El repositorio no versiona datos, artefactos ni
secretos: 443 archivos trackeados, `.git` de 5.8 MB.

El hallazgo rector no es de código sino de proceso.

## Hallazgo principal: el estado se declaraba sin verificarlo

Al iniciar la sesión, la documentación del propio día (`Bitácora/2026-08-04.md`)
afirmaba **"Suite completa verde"** y **"Ruff y Mypy: no ejecutados porque no
están instalados en el entorno"**. Medición real:

| Afirmación documentada | Realidad medida |
|---|---|
| Suite completa verde | **5 failed, 612 passed** |
| Ruff y Mypy no instalados | **Instalados** (ruff 0.15.14, mypy 2.1.0) y limpios |

Es el tercer caso en tres días, junto con la deriva del `pick_mode` del 07-31
detectada el 08-02. Agravante verificado: `current-task.md` cerró esa tarea con
`Result: PASS` en violación de la regla explícita de su propio
`STATES.md`: *"Si no puede determinarse a partir de un artefacto o de la salida
de un comando, el resultado es BLOCKED, nunca PASS."*

## Riesgo más grave corregido: C-2, fail-open del stack de riesgo

`Settings.load()` se saltaba en silencio toda la configuración si
`configs/default.yaml` no se resolvía. Los defaults del dataclass son inseguros:
`shadow_mode=False`, `clv_gate_enabled=False`, `max_plausible_edge=0.15` (el
doble del 0.075 desplegado), `paused_markets={}`. El resultado habría sido
apuestas reales sin capa de control y sin un solo warning.

Honestidad sobre la explotabilidad: **no estaba activo**. El paquete corre desde
fuente, `ROOT` resuelve al repositorio y el YAML existe; el CI usa `pip install
-e` (editable), que preserva la ruta. El gatillo es un `pip install .` no
editable, que `pyproject.toml` habilita al declarar `packages.find where=["src"]`.
Latente, no vivo. Corregido: ahora lanza `FileNotFoundError`.

## Mejoras realizadas (5 correcciones de código/config, todas con prueba)

1. `src/sqp/config.py` — fail-fast en `load()` (C-2).
2. `scripts/settle_all.py` — el abort del día deja de dispararse por fallos
   transitorios sin picks en riesgo; reporte de auditoría pasa a best-effort.
3. `.claude/settings.json` + `MODEL_ROUTING.md` + registros — deriva del modelo
   principal resuelta en `claude-opus-5` por decisión del operador.
4. `src/sqp/monitoring/health.py` — un CSV ilegible se registra en vez de
   confundirse con uno ausente.
5. `.gitignore` — `*.patch` ignorado (había un parche residual sin trackear en
   la raíz, en riesgo de commit accidental).

## Riesgos principales vigentes

- **54 filas servidas sin liquidar fuera de la ventana de scores** (chile 42,
  tennis_atp_canadian_open 12). Health check en WARN. Misma clase que M-01,
  cerrado el 08-02: son instancias nuevas, así que el fallback desde
  `data/historical/` no cubre estas ligas. Sesga la muestra por supervivencia.
  Requiere decisión del operador (el settle consume cuota del API).
- **Sin ventaja predictiva demostrada.** El gate de CLV sigue vacío; ningún
  (liga, mercado) alcanza mediana positiva con n≥30. La calidad del software no
  es validez predictiva.

## Preparación

- **Shadow: PREPARADO.** Ya opera así; la medición es completa (CLV con filtro
  de frescura, monitor de degradación, diagnóstico por segmentos, breakeven por
  cuota, observatorio intradía v2).
- **Dinero real: NO PREPARADO.** Ningún mercado pasa el gate de salida. No se
  modificó `shadow_mode`, bankroll, stakes ni límites de exposición.

## Conclusión

El repositorio queda en verde verificado por ejecución, con dos fallos reales
corregidos (uno de ellos crítico latente) y con la brecha de proceso
documentada. Ninguna de las correcciones aumenta la probabilidad de que el
sistema gane dinero: son de seguridad, integridad y observabilidad. La ausencia
de edge demostrado permanece intacta y es el hecho dominante del proyecto.

No se realizó ninguna acción que requiriera autorización: sin commit, push,
tag, deploy, consumo de API paga, promoción de modelos ni cambios de riesgo.
