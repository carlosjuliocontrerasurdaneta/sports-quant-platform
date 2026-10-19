# FINDINGS — ronda `audit-2026-10-18`

- **Base:** `3e8bbac`. **Fecha:** 2026-10-18.
- **Fuente:** `claude/REPORT.md`, único auditor. **No hubo segunda opinión:** el MCP codex dio CONNECTION_CLOSED y no existe `openai/REPORT.md`.
- **Validación independiente:**
  - Candidatos cuantitativos (AUD-001, 002, 008 y 009): Fable (`independent-code-reviewer`, `model: "fable"`), en modo adversarial y con su propio método.
  - Resto: la sesión principal, por un segundo método (re-ejecución de la sonda, conteo agregado, `gh api` y `Get-ScheduledTaskInfo`).
- **Origen de todos los IDs:** exclusivo Claude.

## Resumen

| Métrica | Valor |
|---|---|
| Confirmados | 17. Por severidad: CRITICAL 0, HIGH 1, MEDIUM 6, LOW 10 |
| Por prioridad | P0 0 · P1 1 · P2 6 · P3 10 |
| Inferidos / no verificables | 14 |
| Descartados documentados | 24 |
| Validación global | ruff 0 · mypy 0 · pytest completo rc=0 (con un fallo intermitente en otro run, AUD-017) · CI de main en verde |
| Estado de los controles | Prediction gate activo, default-deny, 0 mercados con stake real · CLV gate desactivado · diario del 18-10 0x0 (el del 17-10 falló) |

| ID | Alias | Sev. | Conf. | Evidencia | Prio. | Título |
|---|---|---|---|---|---|---|
| AUD-001 | CLAUDE-001 | HIGH | HIGH | REPRODUCED | P1 | En NHL totals, la masa del empate reglamentario se cuenta como total 2k |
| AUD-002 | CLAUDE-002 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | En NBA, el descanso a varios días vista ignora los partidos programados intermedios |
| AUD-003 | CLAUDE-003 | MEDIUM | HIGH | REPRODUCED | P2 | ResultsStore duplica partidos con el mismo `game_id` |
| AUD-004 | CLAUDE-004 | MEDIUM | HIGH | REPRODUCED | P2 | `fable_gate` no ve las rutas sensibles con contrabarra, relativas a `cwd` ni con `git stage` |
| AUD-005 | CLAUDE-005 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | La tarea diaria no reintenta y el hueco solo se detecta dentro del run |
| AUD-006 | CLAUDE-006 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | Repo público sin ninguna barrera de secretos antes de publicar; el hook excluye `audit/` |
| AUD-007 | CLAUDE-007 | MEDIUM | MEDIUM | STATICALLY_VERIFIED | P2 | `crossreview-on-stop.sh` no acota su tiempo y borra el centinela antes de revisar |
| AUD-008 | CLAUDE-008 | LOW | HIGH | REPRODUCED | P3 | Líneas de cuarto graduadas win/loss antes del arreglo siguen en el gate y en la calibración |
| AUD-009 | CLAUDE-009 | LOW | HIGH | REPRODUCED | P3 | El CLV toma como cierre un snapshot capturado en la entrada o antes |
| AUD-010 | CLAUDE-010 | LOW | HIGH | REPRODUCED | P3 | El informe compara edge estimado y ROI realizado sobre poblaciones distintas |
| AUD-011 | CLAUDE-011 | LOW | HIGH | STATICALLY_VERIFIED | P3 | Los tests escriben en el log de producción `logs/sqp.log` |
| AUD-012 | CLAUDE-012 | LOW | HIGH | REPRODUCED | P3 | El detector de literales no reconoce `key=`, `x-api-key` ni `ghp_` |
| AUD-013 | CLAUDE-013 | LOW | HIGH | REPRODUCED | P3 | `require-dispatch-model.sh` exige `model` en forks, donde no tiene efecto |
| AUD-014 | CLAUDE-014 | LOW | MEDIUM | STATICALLY_VERIFIED | P3 | IDs obsoletos de Sonnet y Haiku en `MODEL_ROUTING.md`, fijados por un test |
| AUD-015 | CLAUDE-015 | LOW | HIGH | STATICALLY_VERIFIED | P3 | El issue `ci-rojo` #4 abierto con el CI en verde silencia el próximo rojo |
| AUD-016 | CLAUDE-016 | LOW | HIGH | REPRODUCED | P3 | `requirements.lock` no fija el cierre transitivo |
| AUD-017 | CLAUDE-017 | LOW | MEDIUM | REPRODUCED | P3 | Test intermitente `test_medir_aborts_with_different_t1` |

---

## AUD-001: en NHL totals, la masa del empate reglamentario se cuenta como total 2k

| Campo | Detalle |
|---|---|
| Categoría | Validez de la probabilidad primaria |
| Severidad / confianza / evidencia | HIGH / HIGH / REPRODUCED |
| Prioridad | P1 |
| Archivo | `src/sqp/models/distributions.py:244-275` (`poisson_match_probs`). Ruta: `HockeyAdapter` → `PoissonAdapter.estimate` (`sports/adapters.py:128,226`). Sin `dispersion_k` (`registry.py:43`) |
| Activación | Cualquier total de NHL (liga a dos vías, `three_way=False`) |
| Problema | El empate al final del tiempo reglamentario siempre termina con un gol más (prórroga o penaltis), pero la rejilla cuenta la celda (k,k) como total 2k. Para h2h el empate sí se reparte, pero para totals no se le suma el gol |
| Evidencia concreta | `results_nhl.csv` desde 2023-10: n=4.658, 0 empates, 67,75 % de totales impares. Con λ=6,158 (P(Over) producción / corregido / empírico): **4,5** 0,736 / 0,764 / 0,781 · **5,5** 0,579 / 0,553 / 0,558 · **6,5** 0,419 / 0,443 / 0,444 · **7,5** 0,278 / 0,255 / 0,244. El error alterna de signo con la paridad de la línea y la corrección lo deja por debajo de 2 pp. Stream graduado, Over 6,5 deduplicado por evento (n=74): modelo 0,379, servido 0,427, mercado 0,476, acierto 0,500; residuo +0,121 (IC95 [0,013; 0,241]) |
| Esperado / observado | Esperado: el empate cuenta en el total 2k+1. Observado: cuenta en 2k, con un sesgo de 2–5 pp hacia Under en las líneas 2k+0,5 y hacia Over en las 2k+1,5 |
| Causa raíz | Las tasas se ajustan sobre marcadores finales, pero la rejilla independiente admite resultados finales imposibles |
| Consecuencia | Edges espurios en la línea principal de NHL. `market_shrink` 0,5 los reduce a la mitad, pero quedan por encima de `min_edge` 0,02 |
| Controles existentes | Sin calibrador `nhl_totals`. Degradación no pausa `nhl\|totals` (Brier 0,2499 frente a 0,2451; delta por debajo del margen). El gate (n=127 < 300) impide stake real, pero los picks se publican sesgados |
| Corrección mínima | Con `three_way=False`, evaluar los totals asignando la celda (k,k) a t=2k+1, y re-verificar que la media de λ sigue cuadrando. Cambia probabilidades servidas: necesita pre-registro y revisión Fable antes del commit |
| Pruebas | Valor esperado de P(Over 6,5) con empate +1; alternancia por paridad; invariancia con `three_way=True` |
| Criterio de aceptación | Error de P(Over) frente a lo empírico por debajo de 2 pp en 4,5 a 7,5 con λ media, y el fútbol sin cambios |
| Limitaciones | Comparación hecha con λ media, no con la mezcla real por partido. En MLB (NB k=3,8) no se observa el patrón |

## AUD-002: en NBA, el descanso a varios días vista ignora los partidos programados intermedios

| Campo | Detalle |
|---|---|
| Categoría | Desajuste entre entrenamiento y servicio (feature temporal) |
| Severidad / confianza / evidencia | MEDIUM / HIGH / STATICALLY_VERIFIED, más reproducción con los datos servidos hoy |
| Prioridad | P2 |
| Archivo | `src/sqp/models/rest.py:59-85`; `sports/adapters.py:54`; horizonte `config.py:259` (7 días); `ratings.yaml` nba `rest_points_per_day: 0.795` |
| Activación | Evento NBA a 2 o más días en el que un equipo juega otro partido antes |
| Evidencia concreta | `predictions_nba.csv` del 18-10: 18 eventos a D+2..D+6; último resultado del 17-10. En 3 de 18 el ajuste es erróneo: 76ers–Cavaliers el 22-10 (descanso modelo (4,4), real (2,4); ajuste 0 frente a −1,59), Thunder–Nuggets el 23-10 (mismo caso), Spurs–Rockets el 24-10 (0 frente a +0,80). Reproducción en memoria con `_league_meta`/`get_adapter`: descanso A = 3 frente al verdadero 1 |
| Esperado / observado | Esperado: el walk-forward de activación usa el estado del día anterior, es decir, descanso exacto. Observado: a D+2..D+6 el descanso sale topado en 4 |
| Causa raíz | `rest_days` solo conoce partidos jugados, no el calendario |
| Consecuencia | Las h2h y spreads de NBA servidas con antelación no siguen la política pre-registrada y contaminan el stream servido. El día anterior al partido el valor se corrige |
| Controles existentes | Re-estimación diaria; shrink 0,5; gate default-deny sin entrada NBA. `test_nba_rest_activation` no cubre el caso |
| Corrección mínima | Devolver un ajuste 0 cuando el evento no es el siguiente partido de los dos equipos, o calcular el descanso con los eventos programados. Es un cambio de feature de modelo: necesita revisión Fable |
| Pruebas | Evento a D+3 con un partido en D+2: no recibe el descanso del último partido jugado; paridad con `walk_forward_backtest` |
| Limitaciones | El calendario reconstruido solo usa eventos con cuotas. El mismo patrón aparece en `features/research.py` (solo investigación, INFERRED) |

## AUD-003: ResultsStore duplica partidos con el mismo `game_id`

| Campo | Detalle |
|---|---|
| Categoría | Integridad de datos |
| Severidad / confianza / evidencia | MEDIUM / HIGH / REPRODUCED |
| Prioridad | P2 |
| Archivo | `src/sqp/storage/results_store.py:93,155` (clave `(date, home, away, game_id)`); `pipeline/daily.py:115-118`; `providers/mlb_statsapi.py:60-80` |
| Activación | (a) Partido MLB suspendido y reanudado: mismo `gamePk` Final en dos fechas. (b) ESPN renombra un equipo y el backfill vuelve a descargar los mismos partidos |
| Evidencia concreta | Conteo de la sesión principal: mlb 15, ncaab 31 y wncaab 95 filas con `game_id` repetido; atp 2, según el especialista. Ejemplos: 716404 NYM–MIA 1-0 guardado el 2023-09-28 y el 2023-10-02; 401812250 TCU contra «Saint Francis Red Flash» y contra «Red Wolves». Con `_merge_results` y alias: +15, +31 y +95 filas en el ajuste de ratings |
| Esperado / observado | Esperado: una fila por partido del proveedor. Observado: dos, con el rival contado dos veces y la identidad renombrada partida en dos |
| Causa raíz | La identidad del partido incluye fecha y nombres, no solo el `game_id` del proveedor |
| Consecuencia | Ratings sesgados de los equipos afectados (ncaab y wncaab empiezan en noviembre); también afecta a `feature_store` y a la calibración por partido. Impacto en MLB del 0,15 % |
| Controles existentes | `audit_team_names.py` es manual y no detecta duplicados internos. No hay test |
| Corrección mínima | Deduplicar por `gamePk` en `MLBStatsProvider.fetch_results`, y en `upsert` no insertar un `game_id` no vacío que ya exista, avisando del renombre. Añadir alias. Reparar las filas existentes solo con autorización |
| Pruebas | Mismo `gamePk` en dos fechas da una sola fila; mismo `game_id` con otro nombre no hace crecer el store y deja un aviso |
| Limitaciones | No se cuantificó el cambio de probabilidad por partido |

## AUD-004: `fable_gate` no ve las rutas sensibles con contrabarra, relativas a `cwd` ni con `git stage`

| Campo | Detalle |
|---|---|
| Categoría | Control de proceso (gobernanza de commits) |
| Severidad / confianza / evidencia | MEDIUM / HIGH / REPRODUCED |
| Prioridad | P2 |
| Archivo | `.claude/hooks/fable_gate.py:478` (`shlex.split(..., posix=True)`), `:693-704` |
| Activación | Desde PowerShell, `git commit`/`git add` con `configs\…`; commit desde un subdirectorio; `git stage` |
| Evidencia concreta | Re-verificado por la sesión principal: `_tokeniza(r'git add configs\default.yaml')` devuelve `['git','add','configsdefault.yaml']`. En el repo de prueba del especialista, `PowerShell: git commit -m x configs\default.yaml` sale con rc 0 y git sí commitea `configs/default.yaml`. También dejan pasar `Set-Location configs; …`, `cd src && …` y `git stage -A; git commit` |
| Esperado / observado | Esperado: bloquear igual que con `/`. Observado: deja pasar el commit sin línea FABLE-REVIEW |
| Causa raíz | `shlex` en modo POSIX se come `\` antes de normalizar; las rutas se resuelven contra `CLAUDE_PROJECT_DIR` y no contra `cwd`; `stage` no se reconoce |
| Consecuencia | Un cambio en `configs/**` o `risk/**` puede entrar en un commit sin la revisión Fable que exige la política |
| Controles existentes | Revisión de Codex al Stop, parcial y posterior. El CI no comprueba FABLE-REVIEW |
| Corrección mínima | Normalizar `\` → `/` antes de `shlex` (o usar `posix=False` en PowerShell); resolver contra `payload.cwd` y los `cd`/`Set-Location` del propio comando; tratar `stage` como `add`. La ruta del hook es sensible: revisión Fable |
| Pruebas | Casos parametrizados en `tests/test_fable_gate.py` para los 4 escapes |
| Limitaciones | La ofuscación deliberada queda fuera del alcance declarado del hook |

## AUD-005: la tarea diaria no reintenta y el hueco solo se detecta dentro del run

| Campo | Detalle |
|---|---|
| Categoría | Operaciones y resiliencia |
| Severidad / confianza / evidencia | MEDIUM / HIGH / STATICALLY_VERIFIED, más el incidente real |
| Prioridad | P2 |
| Archivo | Tarea `SQP_Diario_Completo_Cdev`; `src/sqp/monitoring/health.py:231-268,360-379` |
| Activación | Fallo al lanzar la tarea, por ejemplo por un reinicio de Windows Update |
| Evidencia concreta | 17-10 12:00:01 con resultado 0x8007045B (apagado en curso). En el evento System 1074, MoUsoCoreWorker reinició a las 11:59. Los logs del diario no se tocaron entre el 16-10 y el 18-10. `RestartCount=0` (re-verificado). El 18-10 a las 12:00 terminó con 0x0 |
| Esperado / observado | Esperado: reintento acotado o aviso automático. Observado: sin reintento. `pipeline_liveness` y `scheduled_tasks_status` se ejecutan dentro del run, así que no pueden ver el hueco del día anterior |
| Causa raíz | No hay política de reintento, y la detección vive dentro del proceso cuya ausencia hay que detectar |
| Consecuencia | Se pierde un día de picks y de muestra. La liquidación se recupera al día siguiente con `--days-from 3` |
| Controles existentes | `open_dashboard.ps1` al iniciar sesión, que depende de que alguien inicie sesión |
| Corrección mínima | `RestartCount`/`RestartInterval`, con valores que decide el operador; requiere un proceso elevado (S4U). Alternativa: en health_check, comparar la fecha del último «DIARIO COMPLETO: OK» |
| Pruebas | `scheduled_tasks_status` con el estado «en ejecución»; verificación manual de la tarea |
| Limitaciones | No se pudo confirmar si el aviso del dashboard llegó a mostrarse el 17-10 (log denegado) |

## AUD-006: repo público sin ninguna barrera de secretos antes de publicar; el hook excluye `audit/`

| Campo | Detalle |
|---|---|
| Categoría | Seguridad |
| Severidad / confianza / evidencia | MEDIUM / HIGH / STATICALLY_VERIFIED (más REPRODUCED en el hook) |
| Prioridad | P2 |
| Archivo | `.claude/hooks/check-secrets.sh:44,54,67`; `_targets.py:80,85,200`; ajustes de GitHub |
| Activación | Un literal de credencial en un fichero rastreado de `audit/`, `audits/` o con una extensión fuera de `_SUFIJOS`, seguido de push |
| Evidencia concreta | Re-verificado: `gh api` devuelve visibilidad `public`, `secret_scanning: disabled` y `push_protection: disabled`. Sin `.git/hooks` activos; el CI no tiene paso de escaneo. El hook es PostToolUse (avisa después de escribir) y hace `continue` con `audit/*` y `audits/*`, que suman 325 ficheros rastreados entre audit/, audits/ y Obsidian/ |
| Esperado / observado | Esperado: al menos una barrera que bloquee antes de publicar. Observado: ninguna |
| Causa raíz | La exclusión de `audit/` se puso para evitar falsos positivos y no se compensó en otra capa |
| Consecuencia | Si se filtra la clave de pago, queda expuesta públicamente en el historial. Hoy no hay ninguna en el árbol ni en el historial (verificado) |
| Controles existentes | `deny Read(./.env)`; `repr=False`; redacción de la query; hook PostToolUse |
| Corrección mínima | Activar secret scanning y push protection (decisión del operador, cambio externo) o añadir un escaneo al CI; escanear `audit/` aplicando el filtro `_symbolic` en lugar de excluir el directorio |
| Pruebas | Hex falso en una ruta `audit/` simulada; fixture falso en CI |
| Limitaciones | `logs/` no se pudo verificar |

## AUD-007: `crossreview-on-stop.sh` no acota su tiempo y borra el centinela antes de revisar

| Campo | Detalle |
|---|---|
| Categoría | Control y trazabilidad |
| Severidad / confianza / evidencia | MEDIUM / MEDIUM / STATICALLY_VERIFIED (que ocurra en la práctica es INFERRED) |
| Prioridad | P2 |
| Archivo | `.claude/hooks/crossreview-on-stop.sh:28` (`rm -f "$marker"`), `:104` (`codex review` sin `timeout`); hook con 600 s en `settings.json` |
| Activación | Un `codex review` que tarde más de 600 s |
| Evidencia concreta | El grep de `timeout` en el fichero sale vacío (re-verificado). `run-tests-on-stop.sh` sí tiene presupuesto propio y documenta exactamente este fallo |
| Esperado / observado | Esperado: presupuesto propio por debajo de 600 s y restaurar el centinela. Observado: el harness lo mata, el centinela ya está borrado y la revisión se pierde en silencio |
| Causa raíz | No se aplicó el patrón de presupuesto de `run-tests-on-stop.sh` |
| Corrección mínima | `timeout 540 codex review …`; con rc 124, recrear el centinela e informar «NO EJECUTADA» |
| Pruebas | `codex` simulado que tarda o devuelve 124 en `test_audit_hooks.py` |
| Limitaciones | No se midió la duración real de `codex review` |
| Relación histórica | Distinto de `audit-2026-10-15`/AUD-010 (ejecutable ausente), que se corrigió con `command -v` |

## AUD-008: líneas de cuarto graduadas win/loss antes del arreglo siguen en el gate y en la calibración

| Campo | Detalle |
|---|---|
| Categoría | Validez cuantitativa (stream append-only) |
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED. Fable lo rebaja de MEDIUM a LOW porque hoy no afecta a ninguna decisión |
| Prioridad | P3 |
| Archivo | `data/calibration/graded_<fútbol>.csv`; `risk/prediction_gate.py:158,183-206`; `calibration/calibrator.py:724-726`; `calibration/data.py:177-200` |
| Evidencia concreta | Fable re-graduó con `_grade` actual: 92 filas mal graduadas (generadas entre el 19-07 y el 06-09), 58 de ellas en la ventana del gate, que forman 14 unidades (laliga 28, seriea 10, ligamx 8, chile 8, epl 2, mls 2). El especialista obtuvo 124 de 744 con otro cruce. El arreglo ya estaba en `c578f52` (13-09) y `4f06b4f` (17-09) |
| Consecuencia | Hoy ninguna: n entre 32 y 124, frente a min_n 300. Riesgo latente para el test único y para la calibración |
| Corrección mínima | Corte `INVALID_BEFORE` limitado a las filas con línea de cuarto anteriores a `c578f52`. Es un cambio de gate: revisión Fable. Re-graduar solo con autorización expresa |
| Pruebas | Una fila de −0,75 graduada `win` antes del corte queda fuera de `_usable` |
| Limitaciones | 244 filas sin cruce, así que 92 es un mínimo |

## AUD-009: el CLV toma como cierre un snapshot capturado en la entrada o antes

| Campo | Detalle |
|---|---|
| Categoría | Backtest y CLV |
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED. Fable lo rebaja de MEDIUM porque el gate de CLV está apagado |
| Prioridad | P3 |
| Archivo | `src/sqp/audit/clv.py:58-90`; `backtesting/roi_engine.py:73-118` |
| Evidencia concreta | Fable, con los datos de después del run de hoy: 146 de 1.268 filas tienen el cierre en `captured_at ≤ generated_at` (mediana de la diferencia 0,1 min), y explican 135 de los 366 CLV exactamente 0. El beat rate pasa de 0,368 a 0,400 al excluirlas, y la mediana de `ncaaf\|h2h` pasa de 0 a +0,0082 |
| Consecuencia | Diagnóstico sesgado hacia cero. Si se reactivara `clv_gate`, afectaría a decisiones |
| Controles existentes | `clv_gate.enabled: false`; el prediction gate es el que manda. No se pudo descartar un override en `.env` |
| Corrección mínima | Exigir `close_captured_at > generated_at` y, si no se cumple, contar la fila como `sin_cierre` |
| Pruebas | Un pick cuyo único snapshot fresco es igual o anterior a su generación queda sin emparejar |

## AUD-010: el informe compara edge estimado y ROI realizado sobre poblaciones distintas

| Campo | Detalle |
|---|---|
| Categoría | Separación de métricas de apuesta |
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED |
| Prioridad | P3 |
| Archivo | `src/sqp/audit/report.py:265-285,331-333` |
| Evidencia concreta | `mean_est_edge` sobre todas las graduadas (n=3.145) da 0,178; sobre las filas con stake (n=150) da 0,058, frente a `realized_roi` −0,153. El texto dice «mean_est_edge deberia aproximar realized_roi» |
| Consecuencia | La lectura invita a una comparación inflada. No cambia stakes |
| Corrección mínima | Calcular la columna de comparación sobre las mismas filas con stake, o renombrarla con su población |
| Pruebas | `_segment_audit` con una mezcla de filas con y sin stake |

## AUD-011: los tests escriben en el log de producción `logs/sqp.log`

| Campo | Detalle |
|---|---|
| Categoría | Monitorización e higiene de evidencia |
| Severidad / confianza / evidencia | LOW / HIGH / STATICALLY_VERIFIED |
| Prioridad | P3 |
| Archivo | `src/sqp/logging_config.py:76-83`; no hay redirección en `tests/conftest.py` (re-verificado) |
| Evidencia concreta | Hay líneas en `logs/sqp.log` que son de tests: `[mlb] fallo en el pipeline: boom` y `pitcher guard failed: adapter roto`. Además, 348 ERROR del 17-10, un día sin run |
| Consecuencia | Errores sintéticos mezclados con los reales en el log de diagnóstico; rotación a 5 MB |
| Corrección mínima | Fixture autouse que retire o redirija el handler de fichero, o una variable de entorno que lo desactive |
| Pruebas | Un test que compruebe que `logs/sqp.log` no crece al ejecutar la suite |
| Limitaciones | Esta auditoría también añadió líneas por este mismo mecanismo |

## AUD-012: el detector de literales no reconoce `key=`, `x-api-key` ni `ghp_`

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED |
| Prioridad | P3 |
| Archivo | `.claude/hooks/_secret_literals.py:8-13` |
| Evidencia concreta | Con un hex32 falso devuelven `False`: `key="…"`, `ODDS_KEY="…"`, `{"x-api-key": "…"}`, el hex suelto y `ghp_…`. Devuelven `True`: `ODDS_API_KEY=`, `?apiKey=`, `Bearer` y `sk-ant-` |
| Corrección mínima | Añadir `KEY\b`, `[-_]api[-_]key`, `ghp_` y `github_pat_` |
| Pruebas | Casos parametrizados en `tests/test_audit_hooks.py` |

## AUD-013: `require-dispatch-model.sh` exige `model` en forks, donde no tiene efecto

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED |
| Prioridad | P3 |
| Archivo | `.claude/hooks/require-dispatch-model.sh:22-34` |
| Evidencia concreta | `{"subagent_type":"fork"}` sin `model` devuelve rc 2. La herramienta Agent documenta que un fork ignora el override |
| Consecuencia | El despacho parece cumplir la política de escalones, pero el fork corre con el modelo de la sesión; el mensaje del hook es falso para forks |
| Corrección mínima | Dejar pasar `fork` con un aviso; documentarlo en `MODEL_ROUTING.md` |
| Pruebas | Caso fork en `test_audit_hooks.py` |

## AUD-014: IDs obsoletos de Sonnet y Haiku en `MODEL_ROUTING.md`, fijados por un test

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / MEDIUM / STATICALLY_VERIFIED |
| Prioridad | P3 |
| Archivo | `.claude/automation/MODEL_ROUTING.md:98` (`claude-sonnet-5`, `claude-haiku-4-5`); `tests/test_claude_model_routing.py:277` |
| Evidencia concreta | Re-verificado. El entorno de esta sesión declara `claude-sonnet-5-5` y `claude-haiku-5-5` |
| Consecuencia | El documento canónico da como «hecho verificado» IDs que no son los vigentes. La ejecución no cambia, porque se despacha por alias |
| Corrección mínima | Actualizar la línea y el test a la vez, tras verificar contra la documentación viva (memoria `datos-de-modelos-fuente-viva`) |
| Limitaciones | No se contrastó con la documentación viva de Anthropic |

## AUD-015: el issue `ci-rojo` #4 abierto con el CI en verde silencia el próximo rojo

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / HIGH / STATICALLY_VERIFIED |
| Prioridad | P3 |
| Archivo | `.github/workflows/ci.yml`, job `alerta-ci-rojo` |
| Evidencia concreta | `gh issue list --label ci-rojo --state open` devuelve #4 (f128483, 12-10). El último run de main está en success |
| Consecuencia | El próximo fallo en main no abrirá issue (`if [ "$abiertos" != "0" ] … exit 0`) |
| Corrección mínima | Cerrar #4 (decisión del operador, escritura externa); opcionalmente, un paso `if: success()` que lo cierre |

## AUD-016: `requirements.lock` no fija el cierre transitivo

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / HIGH / REPRODUCED |
| Prioridad | P3 |
| Archivo | `requirements.lock:1-3` (la cabecera dice «filtered to sqp's runtime + dev dependency tree») |
| Evidencia concreta | El cierre tiene 32 paquetes. Faltan narwhals (runtime de scikit-learn 1.9.0; 2.20.0 en producción), pygments, ast-serialize, librt, mypy-extensions, pathspec y typing-extensions |
| Consecuencia | El CI y pip-audit no fijan ni auditan esos paquetes. Impacto no demostrado hasta hoy |
| Corrección mínima | Regenerar el lock con el cierre completo |
| Pruebas | Recalcular el cierre y pasar pip-audit |

## AUD-017: test intermitente `test_medir_aborts_with_different_t1`

| Campo | Detalle |
|---|---|
| Severidad / confianza / evidencia | LOW / MEDIUM / REPRODUCED (1 de 3 ejecuciones) |
| Prioridad | P3 |
| Archivo | `tests/research/test_measure_segment_market_weight.py:537-542`; `scripts/research/measure_segment_market_weight.py:219-247,991-994` |
| Evidencia concreta | Primera suite (`-x`): `SystemExit '--medir exige T0 y no existe'` cuando se esperaba «no coincide». Fichero aislado: 52 passed. Suite completa sin `-x`: rc 0. El host estaba muy cargado (7 agentes en paralelo) |
| Causa raíz | NOT_VERIFIABLE. `resolve_t0` lee `git log --diff-filter=A` de un repo temporal creado justo antes; se sospecha una dependencia del orden o del tiempo |
| Consecuencia | Un CI o un hook Stop en rojo sin regresión real; erosiona la confianza en la suite |
| Corrección mínima | Reproducir con `-p no:randomly`/`--count` y fijar las fechas de commit y el entorno git del fixture |
| Pruebas | Ejecutar el test 20 veces seguidas sin fallos |

---

## Inferidos y no verificables (no son defectos confirmados)

| # | Área | Estado | Descripción | Qué falta |
|---|---|---|---|---|
| N-01 | Permisos | INFERRED, posible MEDIUM | Los `allow` `PowerShell(Get-Content *)` y `Select-String *` podrían saltarse los `deny` de `Read(./.env)`, `logs/**` y `data/**`. En esta sesión el clasificador de modo auto bloqueó los intentos | Confirmar en la documentación oficial cómo se combinan los deny de Read con el shell |
| N-02 | Riesgo | NOT_VERIFIABLE | Overrides por entorno de `MARKET_SHRINK`, `MIN_EDGE`, `UNCERTAINTY_PENALTY` y `CLV_GATE_ENABLED`. Se verificó que `KELLY_FRACTION` = 0,08 = yaml | Lectura autorizada de `.env` o de `_warn_risk_divergence` en el log |
| N-03 | Seguridad | NOT_VERIFIABLE | Ausencia de `apiKey=` en `logs/`. Por análisis estático, la clave no se registra | Un conteo hecho por el operador |
| N-04 | Datos | INFERRED, MEDIUM | El histórico de ESPN incluye pretemporada (NFL en agosto, NHL en septiembre); MLB sí filtra `gameType=R` | Decisión del proyecto sobre la pretemporada |
| N-05 | Liquidación | NOT_VERIFIABLE | En copas, el marcador de The Odds API podría incluir prórroga o penaltis, mientras el 1X2 se liquida a 90' | Semántica del proveedor |
| N-06 | Datos | INFERRED, LOW | `date` es UTC en ESPN y local en MLB; el docstring de `daily.py:122-124` dice «local» | Revisar los consumidores que asuman fecha local |
| N-07 | Liquidación | INFERRED, LOW | En el tenis graduado, 24 identidades con `void` y resultado a la vez, porque el `start_time` se movió de día | Si el gate excluye los void, es pérdida de muestra |
| N-08 | Caché | INFERRED, LOW | `FileCache.put` no es atómico; una respuesta cruda malformada se cachea antes del parseo | Payload real malformado |
| N-09 | Concurrencia | INFERRED, LOW | `ServedStore._load` pone en cuarentena el fichero cuando hay un ParserError fuera del lock | Hoy la ejecución es en serie |
| N-10 | Modelos | INFERRED, LOW | `_closest_probable` puede asignar el mismo abridor a dos eventos en menos de 12 h | Caso real |
| N-11 | Operaciones | NOT_VERIFIABLE | `VALIDATE_OOS.bat` hace un commit automático mensual bajo S4U que nadie publica | Log del 01-10 |
| N-12 | Hooks | NOT_VERIFIABLE | Si la suite rápida del Stop cabe en 1.080 s | Ejecución medida |
| N-13 | Gate | INFERRED (diseño) | El EV del gate es ex ante del modelo (ncaaf h2h ev +0,563 con 76/326 aciertos); solo el test de signo protege | Re-pre-registro; decide el operador |
| N-14 | Varios LOW | INFERRED | El backtest no pasa `line_movement_pp` (inerte con coeficiente 0); el tipster no aplica `min_edge` (informativo); `train_calibration --source backtest` entrena con otra variable (autopromoción apagada); el docstring de `update_prediction_gate.py:4` dice «p < 0.05»; `cmd /c` en `codex_review.py:444`; actions fijadas por tag; empate NFL WSH-NYG del 11-10 como push | — |

## Descartados (con motivo)

| Sospecha | Por qué se descarta |
|---|---|
| Fuga de información futura en el ajuste live | Solo entran partidos `completed`; los eventos ya empezados no generan candidatos (`daily.py:870`) |
| Cuotas de cierre en la mezcla con el mercado | `fair` sale de la misma respuesta usada al generar; la revalidación filtra `captured_at <= now` |
| Frescura de las cuotas | El TTL de la caché queda acotado a 90 min; si se supera, stake 0 con la marca `cuota_vencida` |
| Probabilidades inválidas | Rejillas renormalizadas; h2h suma 1; push excluido; no-vig exige el mercado completo |
| Features configuradas sin cablear | Verificado con `_league_meta`/`get_adapter` |
| Lookahead en el gate | 0 de 41.600 filas con `generated_at ≥ start_time` |
| Sesgo de selección en el test de signo | 0 % de grupos con un solo lado |
| n inflado por la repetición diaria del stream | `_independent_units` colapsa a (evento, mercado) |
| Calibradores vivos degenerados | Recorrido ≥ 0,27 en los 3; el detector actúa al servir |
| Fuga en el split de calibración | Holdout por eventos enteros, en orden temporal |
| Baseline NHL que no suma 1 | Solo filas anteriores a ffc5ad3, ya excluidas por `INVALID_BEFORE` |
| Conversiones, Kelly, `split_asian_line` | Correctas |
| pnl incoherente / precios no finitos | 0 casos en 37 ficheros settled |
| Generar con la liquidación fallida | `DIARIO_COMPLETO.bat:190-191` aborta; `settle_all.py:71-84` |
| El guard de árbol sucio no ve los BAT | git interpreta `*.bat` como glob |
| Fallos de CI vigentes | Los dos rojos están explicados y corregidos (urllib3 2.8.0; `fetch-tags`) |
| Producción con versiones distintas del lock | 25 pines iguales; `pip check` limpio |
| Secretos en el árbol o el historial | Solo el nombre de un tmpdir (474b202) y un prefijo narrativo (58f9523) |
| La clave en repr, logs o la clave de caché | `repr=False`, redacción y `apiKey` excluido |
| Timeouts HTTP | Todas las llamadas los tienen |
| Inyección shell / subprocess | Sin `shell=True` ni `os.system`; listas de argumentos |
| XSS en el dashboard | `motivo` sale de cadenas fijas |
| Duplicados de snapshots de cuotas | Snapshot histórico repetido posterior a commence; no entra en el cierre |
| Lost update en los stores | Leer, fusionar y escribir bajo `locked()`, que aborta si no lo obtiene |
| Escrituras anómalas de terceros durante la auditoría | Son el run de producción de las 12:00 y la preservación de la ronda |

## Observaciones (no son defectos)

- **Residuo KI-071** (persistente, ya registrado como pendiente del operador): 14 identidades de pick liquidadas dos veces (mlb 5, epl 5, mls 1, ncaaf 3), todas con stake 0 y anteriores al arreglo `ed81aaa`. Inflan n en el informe y en la degradación. Su reparación necesita autorización expresa.
- `main` va 2 commits por delante de `origin/main` (1821225 y 3e8bbac), sin CI. Sus tests locales dan 164 passed.
- `BUILD_INFO.json` y `OPTIMIZATION.diff` (bundle del 10-09) siguen en la raíz sin consumidores en el código.
- 8 ciclos de importación entre paquetes de `src/sqp`, sin fallo demostrado.
- `.claude/worktrees/` contiene 4 worktrees de agentes con cambios sin commit, excluidos de git, pytest y ruff.
- El dashboard (`SQP_Dashboard`) y la captura de cierre del 18-10 a las 11:00 terminaron con 0x800710E0. No se investigó.

## Comparación histórica con `audit-2026-10-15`

Se hizo después de fijar las conclusiones de esta ronda.

| ID anterior | Estado en esta ronda |
|---|---|
| AUD-002 (tag en CI) y AUD-013 (pip-audit) | **Corregidos, con evidencia nueva**: CI de main en verde con los 6 jobs, incluido dependency-audit |
| AUD-001 (emparejamiento del backtest) | Corregido en `813292d`. Esta ronda no encontró emparejamiento voraz (descartado) |
| AUD-003 (Draw en 2 vías) | Sin recurrencia. El baseline NHL suma 1 después de ffc5ad3 |
| AUD-010 (cross-review sin ejecutable) | Corregido. Ahora aparece un modo de fallo **distinto** en el mismo hook (AUD-007 de esta ronda, nuevo) |
| AUD-007 (log de pitchers) | Corregido; los duplicados históricos siguen pendientes del operador (no se revalidaron) |
| AUD-004, 005, 006, 008, 009, 011, 012 | Sin recurrencia observada en las áreas revisadas; no se re-verificaron uno por uno |
| Todos los AUD-001..017 de esta ronda | **Nuevos** |
