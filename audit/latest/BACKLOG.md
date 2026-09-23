# BACKLOG — ronda `audit-2026-09-22-r2`

Nada aplicado. Cada fila necesita **autorización expresa** del operador. Hay que respetar el orden: 1 antes que 2.

| Orden | ID | Prio | Cambio mínimo | Archivos | Pruebas | Aceptación | Autorización pendiente |
|---|---|---|---|---|---|---|---|
| 1 | `AUD-004` | P1 | Copia de seguridad fuera del árbol y restauración desde `HEAD` | `.claude/skills/full-audit/**` | 3 pruebas de contrato | `not slow` sin fallos | Sí: destructivo para cambios sin commit |
| 2 | `AUD-001` | **P0** (antes del 23/09 12:00) | Commit **selectivo** de la remediación r22 + push. **No** `git add -A` | 6 módulos de código, 6 tests, `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh`, `audit/` | ruff, mypy, `not slow`, CI | `git status --porcelain -- src scripts configs *.bat` vacío; CI verde; run del 23/09 sin «ABORTADO» | Sí: commit y push |
| 3 | `AUD-003` | P1 | Aviso informativo en 42–50 cortes; «RE-PRE-REGISTRAR» sólo con > 50; conservar `fwer_bound`; corregir el comentario | `src/sqp/risk/prediction_gate.py`, `tests/test_prediction_gate.py` | 49 cortes → sin orden; 51 → `error` | Ningún veredicto cambia | Sí: toca un gate (clase de escalación) |
| 4 | `AUD-002` | P1 (antes del primer test de entrada, ~25–26/09) | El escritor distingue ausente de ilegible; ilegible → excepción, sin escribir | `src/sqp/risk/{prediction_gate,degradation}.py`, `src/sqp/exceptions.py`, tests | Corrupto → fichero intacto; ausente → estado inicial; regresión del pestillo | La reproducción ya no reabre tests ni pestillos | Sí: toca un gate (clase de escalación) |
| 5 | `CLN-001` | P3 | Vaciar los subdirectorios **accesibles** de `.codex-tmp/` de rondas cerradas | `.codex-tmp/*` | — | `grep -r` sin `Permission denied` accesible | Sí: borrado |

Dependencias: 2 depende de 1 (si no, el CI se pone en rojo). 3 y 4 son independientes entre sí, pero conviene que entren antes de que `mlb|h2h`/`mlb|spreads` crucen `n ≥ 300`.
