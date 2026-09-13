# Current Task

Status: closed
Result: DEGRADED
Primary loop: `audit.md`
Skills: `full-audit` (fases 0-3) → `audit-remediation` (fases 4-5)
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`); revisión independiente en `fable` de los cambios de contrato del ledger
Date: 2026-09-13

## Routing

Modo no orquestado en las fases 0–3 (validación independiente por segundo
método en la misma sesión). En la Fase 4, escalón `fable` (parámetro
`model: "fable"` de `Agent`, según la REGLA DE DESPACHO de `MODEL_ROUTING.md`)
para revisar AUD-MED-002 (`half_win`/`half_loss`) y AUD-MED-003/004 (picks
`superseded`, fallback histórico de tenis): clase de escalado «cambiar el
contrato de un artefacto persistido» (`settled_*.csv`). Veredicto: 0 defectos
confirmados; 1 sugerencia menor aplicada. No se tocó ningún parámetro de
riesgo, modelo, estrategia, umbral ni gate, y no se contradijo ninguna decisión
registrada (AUD-MED-006 registra la vigente, no la cambia).

## Objetivo

Auditoría integral del proyecto y aplicación de las correcciones aprobadas
(«todos los hallazgos confirmados y las mejoras demostradas»).

## Resultado: por qué DEGRADED y no PASS

Se cumplen: comandos requeridos con exit 0 (ruff, mypy, fast 1787 passed,
slow 224 passed / 1 skipped), artefactos obligatorios escritos y legibles
(`audit/latest/{FINDINGS,BACKLOG,CHANGES,VALIDATION,EXECUTIVE_SUMMARY}.md`,
`MANIFEST.json`), repositorio Git reconstituido y rama publicada. Lo que impide
`PASS`, dicho sin esconderlo:

- **AUD-HIGH-002 (2b)**: las 5 tareas del Programador siguen en «Solo
  interactivo»; cambiarlas exige orden explícita del operador. Sin eso, un día
  sin sesión sigue sin producir picks (ahora al menos con aviso al logon).
- **`VALIDATE_OOS.bat` sigue sin ejecutarse** (B-01, `rc 1` del 01-09).
- **`wnba_totals_calibration_iso.joblib`** (colapsado, inerte) no se movió a
  `retired/`: escritura en `data/` bloqueada por el clasificador de permisos.
- El ledger histórico **no se regraduó** (1 línea de cuarto mal graduada, 150
  picks sin veredicto): la corrección aplica hacia delante; regraduar el pasado
  es decisión aparte.
- `codex review` y `pip-audit` no ejecutados (cuota / red).

## Siguiente acción

Del operador: (1) abrir/mergear el PR `prod/remediacion-20260913` → `main` y
comprobar el CI sobre él; (2) decidir el modo de inicio de sesión de las
tareas; (3) `! cmd /c VALIDATE_OOS.bat`; (4) mover el `.joblib` retirado;
(5) aprobar el MCP `graphify` o retirar la instrucción de `.claude/CLAUDE.md`.
