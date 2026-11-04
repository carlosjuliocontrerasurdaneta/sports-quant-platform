# Informe del auditor Claude — ronda `audit-2026-10-18`

- **Fecha:** 2026-10-18.
- **Base:** `3e8bbac`. Al empezar el árbol estaba limpio y `main` iba 2 commits por delante de `origin/main`.
- **Modo:** orquestado, de solo lectura. La sesión principal (`claude-opus-5-5`) coordinó a 7 especialistas con `model: "opus"`, aplicando la regla 2 de despacho para la ruta full-audit. La validación adversarial de los 4 candidatos cuantitativos se encargó a `independent-code-reviewer` con `model: "fable"`, aplicando la regla 1 (veredictos sobre modelo, gate y CLV). Además, la sesión principal revalidó por un segundo método los candidatos que no son cuantitativos.
- **Segunda opinión:** OpenAI no participó, porque el MCP `codex` dio CONNECTION_CLOSED. No se inventó su informe.

## Independencia y contaminación (declarada)

- Contexto de la sesión principal:
  - La sesión principal vio mensajes de commit y el índice de memoria del harness, que mencionan hallazgos de `audit-2026-10-15` (AUD-001, 003 y 012) y el residuo KI-071.
  - Leyó los títulos de AUD-001..013 solo después de fijar sus conclusiones, en el paso 7 del contrato.
- Especialistas:
  - Tenían prohibido leer `audit/`, `audits/`, `Obsidian/`, `.claude/memory/` y known-issues.
  - Todos declararon haber visto IDs AUD-/KI- en comentarios del código y en el índice de memoria que inyecta el harness, sin apoyarse en ellos.
  - El de seguridad vio una línea de Obsidian dentro de un diff histórico (58f9523).
- Escrituras de terceros durante la auditoría: varios especialistas atribuyeron a «otro proceso» cambios en `data/bets/` y `audit/latest/`.
  - Los de `audit/latest/` son la preservación de ronda que hizo el coordinador.
  - Los de `data/bets/` corresponden al run diario de producción de hoy a las 12:00 locales (`SQP_Diario_Completo_Cdev`, 18-10 12:00:01, resultado 0x0).
  - Ninguno de esos cambios es anómalo.
- Escrituras de la propia auditoría:
  - `.codex-tmp/pytest-*`, que está ignorado por git.
  - Líneas añadidas a `logs/sqp.log` por pytest y por las sondas, debido al mecanismo descrito en CLAUDE-011.
  - Los entregables de esta fase y el registro de enrutamiento en `current-task.md`.

## Inventario y cobertura

| Área | Prioridad | Estado | Componentes | Método | Validación (¿existe? / ¿pasa ahora?) | Limitaciones |
|---|---|---|---|---|---|---|
| Precios, edge, Kelly, exposición | P0 | REVISADA | `markets/`, `risk/kelly.py`, `daily.py:335,937-1060`, configuración efectiva con `Settings.load()` | Lectura, más NaN/inf | 447 tests del área en verde; la configuración efectiva coincide con `default.yaml` | No se leyó `.env`: permiso denegado, por política |
| Liquidación y ledger | P0 | REVISADA | `settlement/`, `settlement_math.py`, `bankroll.py`, `settle_all.py`, `SETTLE_ALL.bat` | Lectura más regradeo de datos guardados | 0 inconsistencias de pnl, 0 duplicados por DEDUP_KEY | Prórroga y penaltis en copas: NOT_VERIFIABLE |
| Prediction gate | P0 | REVISADA | `risk/prediction_gate.py`, `update_prediction_gate.py`, `gate_status.py` | Lectura más sondas | **Activo**, default-deny. Último registro: 2026-10-18 ~15:05Z, 0 mercados habilitados (54 por muestra insuficiente, 6 con el test único agotado), K=52, techo 63 | El fondo del pre-registro no se reevaluó |
| CLV gate | P1 | REVISADA | `risk/clv_gate.py`, `audit/clv.py` | Lectura más sonda | **Desactivado** por configuración. El registro existe (15:10Z) | CLAUDE-009 |
| Calibración | P0 | REVISADA | `calibration/*`, `train_calibration.py` | Lectura; joblib en solo lectura | Los 3 calibradores vivos no están degenerados; el detector actúa también al servir | No se verificó el sha256 del sidecar |
| Backtesting y OOS | P1 | REVISADA_PARCIALMENTE | `roi_engine.py`, `validate_oos.py`, `VALIDATE_OOS.bat` | Lectura | Tarea OOS del 01-10: 0x0 | `engine.py` y `tuning.py`, solo en parte |
| Features y modelos (cutoff) | P0 | REVISADA | `features/`, `models/`, `sports/`, `pipeline/daily.py`, `probabilities.py` | Lectura más reproducción en memoria | 254 tests en verde; 0 filas servidas con `generated_at ≥ start_time` | ML y Monte Carlo no se usan en producción (NO_APLICABLE) |
| Proveedores | P1 | REVISADA | `providers/*` | Lectura | Hay timeout en todas las llamadas HTTP; la clave se redacta en los errores; guard de modo offline | `espn_tennis`, `espn_goalies` y `nhl_api`, solo en parte |
| Almacenamiento y atomicidad | P0 | REVISADA | `storage/*`, `lock.py`, `atomic.py` | Lectura más duplicados agregados | 0 duplicados en servido, graduado, calendario y abridores | CLAUDE-003 |
| Operaciones BAT | P1 | REVISADA | 10 `.bat`, `run_all.py`, `run_status.py` | Estática (no se ejecutó ninguno) | Contrato «liquidar antes de generar» verificado | — |
| Tareas programadas | P1 | REVISADA | 5 tareas SQP_* | `Get-ScheduledTask`/`Info` | El diario del 17-10 falló con 0x8007045B y el del 18-10 terminó con 0x0; `RestartCount=0` | El historial del Programador está deshabilitado |
| CI | P1 | REVISADA | `.github/workflows/ci.yml` | `gh run list/view` | **En verde** el último run (39029952562, 32e1b2f, 6 jobs en success). HEAD no tiene CI porque no se ha hecho push | — |
| Dependencias | P1 | REVISADA | `pyproject.toml`, `requirements.lock` | Comparación de lo instalado con el lock; pip-audit | 25 pines iguales a lo instalado; `pip check` limpio; pip-audit limpio | CLAUDE-016 |
| Seguridad y secretos | P0 | REVISADA | 974 ficheros rastreados, 727 commits, hooks, CI, Dockerfile | `git grep`, `git log -G`, sondas del hook | 0 secretos reales | `logs/` NOT_VERIFIABLE (permiso de lectura denegado) |
| Plataforma GitHub | P1 | REVISADA | Ajustes del repo | `gh api` | Repo PUBLIC; secret scanning y push protection desactivados | — |
| Sistema de instrucciones (.claude) | P1 | REVISADA | settings, hooks, 34 skills, 22 agents, commands, routing | Sondas de hooks y comprobación de rutas | 64+190 tests en verde; `sync_agent_instructions --check` → 0 | Conservación de los `deny` frente al shell: NOT_VERIFIABLE |
| Tests (suite global) | P1 | REVISADA | `tests/` | pytest completo, dos veces | Run 1 (`-x`): 1 fallo intermitente. Run 2: rc=0. Aislado: 52 passed | CLAUDE-017 |
| Calidad estática | P1 | REVISADA | src, scripts, tests | ruff y mypy | ruff rc=0; mypy rc=0 (113 ficheros) | — |
| Arquitectura | P2 | REVISADA_PARCIALMENTE | `src/sqp` | Grafo de imports AST | 8 ciclos entre paquetes, sin fallo demostrado (observación) | — |
| Documentación | P2 | REVISADA_PARCIALMENTE | Docstrings y comentarios citados por los hallazgos | Lectura puntual | — | No se auditó `docs/` entera |
| Limpieza del repositorio | P3 | REVISADA_PARCIALMENTE | Raíz, `.claude/worktrees/` | `git grep` de consumidores | `BUILD_INFO.json` y `OPTIMIZATION.diff` sin consumidores; worktrees excluidos | Observación; no se propone borrar nada |
| Datos productivos completos | — | EXCLUIDA | `data/`, `logs/` | Solo agregados | — | Regla de CLAUDE.md |
| Obsidian, memoria, auditorías previas | — | EXCLUIDA | — | — | — | Independencia |
| Dockerfile | P3 | REVISADA_PARCIALMENTE | `Dockerfile` | Estática | Usuario no root, COPY explícito; nadie construye la imagen | No se construyó |

## Hallazgos del auditor (IDs de origen)

La ficha completa de cada hallazgo está en `../FINDINGS.md`, con el alias `CLAUDE-### → AUD-###`. Abajo va la lista de origen con su especialista.

| ID | Especialista | Título | Sev. | Evid. |
|---|---|---|---|---|
| CLAUDE-001 | features/modelos + Fable | En NHL totals, la masa del empate reglamentario se cuenta como total 2k | HIGH | REPRODUCED |
| CLAUDE-002 | features/modelos + Fable | En NBA, el descanso de un evento a varios días ignora los partidos intermedios | MEDIUM | STATICALLY_VERIFIED + reproducción |
| CLAUDE-003 | datos | ResultsStore duplica partidos por `game_id` (MLB suspendidos; renombres en ncaab, wncaab y atp) | MEDIUM | REPRODUCED |
| CLAUDE-004 | skills/hooks | `fable_gate` no ve rutas con contrabarra, rutas relativas a `cwd` ni `git stage` | MEDIUM | REPRODUCED |
| CLAUDE-005 | operaciones | La tarea diaria no reintenta y el hueco solo se detecta dentro del run | MEDIUM | STATICALLY_VERIFIED + incidente del 17-10 |
| CLAUDE-006 | seguridad | Repo público sin ninguna barrera de secretos antes de publicar; el hook excluye `audit/` | MEDIUM | STATICALLY_VERIFIED + REPRODUCED |
| CLAUDE-007 | skills/hooks | `crossreview-on-stop.sh` no acota su tiempo y borra el centinela antes de revisar | MEDIUM | STATICALLY_VERIFIED |
| CLAUDE-008 | odds + Fable | Líneas de cuarto mal graduadas antes del arreglo siguen en el stream del gate y de la calibración | LOW | REPRODUCED |
| CLAUDE-009 | calibración + Fable | El CLV acepta un «cierre» capturado en el momento de la entrada o antes | LOW | REPRODUCED |
| CLAUDE-010 | odds | El informe compara `mean_est_edge` y `realized_roi` sobre poblaciones distintas | LOW | REPRODUCED |
| CLAUDE-011 | calibración | Los tests y las sondas escriben en `logs/sqp.log` de producción | LOW | STATICALLY_VERIFIED |
| CLAUDE-012 | seguridad | El detector de literales no reconoce `key=`, `x-api-key` ni `ghp_` | LOW | REPRODUCED |
| CLAUDE-013 | skills/hooks | `require-dispatch-model.sh` exige `model` en forks, donde no tiene efecto | LOW | REPRODUCED |
| CLAUDE-014 | skills/hooks | `MODEL_ROUTING.md:98` da IDs obsoletos de Sonnet y Haiku, y un test los fija | LOW | STATICALLY_VERIFIED |
| CLAUDE-015 | operaciones | El issue `ci-rojo` #4 sigue abierto con el CI en verde, lo que silencia el próximo rojo | LOW | STATICALLY_VERIFIED |
| CLAUDE-016 | operaciones + seguridad | `requirements.lock` no fija el cierre transitivo (incluye narwhals, de runtime) | LOW | REPRODUCED |
| CLAUDE-017 | sesión principal | Test intermitente `test_medir_aborts_with_different_t1` | LOW | REPRODUCED (1 de 3) |

Los inferidos, los no verificables, los descartados y las observaciones están en `../FINDINGS.md`.

## Validaciones ejecutadas (resumen)

El detalle está en `EVIDENCE.json`.

- `ruff check src scripts tests` → 0.
- `mypy src` → 0.
- `pytest -x` completo → 1. Falló `test_medir_aborts_with_different_t1`.
- El mismo fichero, aislado → 52 passed.
- `pytest` completo sin `-x` → 0.
- Suites dirigidas de los especialistas: 254 + 447 + 297 + 94 + 30 + 64 + 190 + 164 passed, todas con rc 0.
- `python scripts/sync_agent_instructions.py --check` → 0.
- `gh run list` → último run de main en success.
- pip-audit sobre el lock → limpio.

## Limitaciones

- No hubo segunda opinión de OpenAI.
- No se leyeron `.env` ni `logs/**`, por los `deny` y el clasificador. Por eso quedan NOT_VERIFIABLE los overrides de riesgo por entorno y la ausencia de secretos en los logs.
- No se hizo ninguna llamada a APIs de cuotas.
- No se ejecutó ningún BAT.
- `evaluation/` (bootstrap, compare, feature_*) solo se revisó en parte.
- La auditoría no demuestra ventaja predictiva ni rentabilidad, y no corrige nada.
