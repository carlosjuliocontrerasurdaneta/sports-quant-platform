# Backlog — Auditoría 2026-08-30

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.

## Requiere decisión humana

### D-1 · La política de modelo estaba aplicada a medias (I-1) — **CERRADO**

Resuelto el 2026-08-30 por decisión del operador: Opus 5 en las cuatro puntas.
Se alinearon `.claude/automation/MODEL_ROUTING.md` y los dos literales de
`tests/test_claude_model_routing.py`. Suite completamente verde, 1378 passed.
La jerarquía de capacidad no cambia: `claude-fable-5` sigue siendo el techo y el
destino de las tareas de máximo razonamiento vía el disparador de escalado.

## Cobertura pendiente (primera prioridad de la próxima auditoría)

### P-1 · Gates de riesgo sin revisión línea a línea

`src/sqp/risk/prediction_gate.py`, `clv_gate.py`, `degradation.py`, `kelly.py` y
`bankroll.py` quedaron `PARCIAL`. Con `shadow_mode: false` el sistema dimensiona
stakes reales, así que son el código con más consecuencia directa sobre el
capital y deben ser lo primero que se audite completo.

### P-2 · Pipeline diario, settlement, features, providers y storage

`PARCIAL`. Los hotspots por `git log` desde la última auditoría persistida son
`audit/html_report.py` (21 commits), `pipeline/daily.py` (19),
`configs/default.yaml` (17), `config.py` (16), `calibration/calibrator.py` (9),
`features/rest_form.py` (8) y `scripts/daily_picks.py` (8). Empezar por ahí.

### P-3 · Divergencia efectiva `.env` ↔ YAML no verificada

Existe el mecanismo (`_warn_risk_divergence`, `config.py:68`) pero no se
comprobó su salida real, porque `.env` no es legible bajo la política de
permisos. Cerrarlo requiere ejecutar una carga de configuración que reporte
divergencias sin exponer valores.

### P-4 · Backtesting y walk-forward

`COBERTURA_NO_VERIFICABLE` en esta auditoría. Requiere corridas largas.

### P-5 · Scripts `.bat` sin validación

Ocho `.bat` operacionales en la raíz. Ni `ruff`, ni `mypy`, ni `pytest` los
cubren, y `RUN_DIARIO_ALL.bat` orquesta el run de producción. No existe
comprobación automática de que su encadenamiento siga siendo correcto.

### P-6 · `pip-audit` no ejecutado

No está instalado en este entorno. Instalarlo sería modificar dependencias, que
la fase de diagnóstico prohíbe. La auditoría del 2026-08-04 sí lo corrió
("No known vulnerabilities found"), pero eso fue hace 179 commits.

## No accionable, en seguimiento

### B-1 · Revalidación del registro live con historial vacío

`INFERIDO`, confianza BAJA. Ver `FINDINGS.md`. No se corrige por falta de
evidencia observada.

### 152 filas servidas irrecuperables

Acumulado histórico fuera de la ventana de scores del proveedor. El propio
health check lo declara no accionable y lo registra para seguimiento. Cerrarlo
exigiría backfill con consumo de cuota de API, que es una acción sujeta a
aprobación.
