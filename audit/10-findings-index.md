# 10 — Índice de hallazgos

Base: commit `7871bdb`. 56 hallazgos: **0 críticos, 11 altos, 19 medios,
14 bajos, 12 informativos** (de los cuales 8 son controles verificados **sin**
hallazgos, registrados para que conste qué se comprobó).

**Por qué no hay ningún hallazgo crítico:** `shadow_mode: true`
(`configs/default.yaml:100`) pone a 0 el stake de todos los picks y tiene
precedencia sobre el resto de flags (`daily.py:389-392`). Ningún defecto de esta
auditoría puede perder dinero hoy. Varios de los altos **se vuelven críticos el
día que el shadow mode se levante**, y así están anotados.

| ID | Sev. | Confianza | Categoría | Ubicación | Descripción breve | Responsable | Alcance |
|---|---|---|---|---|---|---|---|
| [COR-01] | Alta | Confirmado (ejec.) | Liquidación | `settlement/settle.py:42-44` | Línea `NaN` en totals: Under siempre gana, Over siempre pierde, sin mirar el marcador | data-engineer | S |
| [COR-02] | Alta | Confirmado (ejec.) | Liquidación | `settlement/settle.py:39-41` | Línea `NaN` en spreads se grada siempre como pérdida | data-engineer | S |
| [QNT-01] | Alta | Confirmado (ejec.) | Cuantitativa | `pipeline/daily.py:628-640` + `pipeline/probabilities.py:119-124` | Penalización de incertidumbre efectiva 0.175 frente al 0.35 configurado | odds-market-auditor | S/M |
| [QNT-03] | Alta | Confirmado | Estabilidad numérica | `markets/vig.py:28,16` | `NaN` atraviesa los dos guards de de-vig y anula el mercado completo en silencio | odds-market-auditor | M |
| [QNT-04] | Alta (latente) | Confirmado (ejec.) | Riesgo | `risk/clv_gate.py:34` + `audit/clv.py:128-133` | Un solo CLV `inf` aprueba un mercado en el gate que gobierna el stake real | risk-manager | S |
| [ARCH-02] | Alta | Confirmado | Duplicación | `pipeline/probabilities.py:17-34` vs `backtesting/roi_engine.py:92-95` | El camino precios→consenso existe 3 veces con reglas distintas; ya divergió una vez | backend-architect | M |
| [DAT-01] | Alta | Confirmado | Paridad backtest | `backtesting/roi_engine.py:92-95` | El backtest evalúa precios que producción descarta: mide otra política | backtest-reviewer | M |
| [DAT-04] | Alta | Alta confianza | Supervivencia | `monitoring/health.py:78` | 54 filas servidas que nunca se gradúan sesgan todos los agregados | data-engineer | S/M |
| [TST-01] | Alta | Confirmado | Test inválido | `tests/test_audit_2026_07_29.py:142-152` | La prueba que protege el shadow mode se auto-salta si el shadow mode se apaga | qa-engineer | S |
| [TST-02] | Alta | Confirmado | Cobertura ausente | `tests/settlement/test_settle_grade.py` | Ningún test cubre línea no finita; el fixture la usa como valor por defecto | qa-engineer | S |
| [OPS-06] | Alta | Alta confianza | Proceso | `audit/latest/FINDINGS.md:30-44` | Estado declarado sin verificar: 3 afirmaciones falsas en 3 días; sin control automático | devops-engineer | M |
| [ARCH-01] | Media | Confirmado | Mantenibilidad | `pipeline/daily.py:476-740` | `run_league` concentra 6 responsabilidades; oculta la composición de [QNT-01]/[QNT-02] | backend-architect | M |
| [ARCH-03] | Media | Confirmado | Duplicación | `pipeline/daily.py:602-612` vs `backtesting/roi_engine.py:159-170` | `_model_map` duplicado literalmente entre producción y backtest | backend-architect | S |
| [COR-03] | Media | Confirmado | Consistencia | `pipeline/probabilities.py:37-43` | `books_count` cuenta líneas que el consenso descartó; anula la penalización de mercado fino | odds-market-auditor | S |
| [COR-04] | Media | Confirmado | Concurrencia | `storage/lock.py:41-52` | Bucle sin pausa ni deadline si `stat()` falla de forma persistente | python-engineer | S |
| [COR-05] | Media | Requiere verif. | Sesgo de selección | `pipeline/daily.py:616` | Cualquier advertencia elimina el evento del stream de calibración, no solo del staking | calibration-auditor | S/M |
| [QNT-02] | Media | Confirmado | Riesgo | `pipeline/daily.py:630,668` | El tope de edge implausible se evalúa sobre la probabilidad ya encogida | risk-manager | S |
| [QNT-05] | Media | Confirmado | Kelly / correlación | `risk/kelly.py:14-27` + `pipeline/daily.py:614` | Hasta 6 selecciones del mismo partido dimensionadas como independientes; sin cap por evento | risk-manager | M |
| [QNT-06] | Media | Confirmado | Tamaño de muestra | `risk/clv_gate.py:23`, `risk/degradation.py:35`, `calibration/calibrator.py:420` | Tres decisiones distintas con el mismo n=30 y sin intervalos de confianza | calibration-auditor | M |
| [DAT-02] | Media | Confirmado | Paridad backtest | `backtesting/roi_engine.py:173-184` | El backtest carece del tope de exposición global entre ligas que sí tiene producción | backtest-reviewer | M |
| [DAT-03] | Media | Confirmado | Realismo de ejecución | `pipeline/daily.py:656,714` | Precio = mediana entre casas: no es obtenible; sin costes ni disponibilidad | backtest-reviewer | M |
| [DAT-05] | Media | Requiere verif. | Reproducibilidad | `backtesting/roi_engine.py:119-146` | Emparejamiento codicioso con consumo: el resultado depende del orden de entrada | backtest-reviewer | S |
| [DAT-07] | Media | Requiere verif. | Contaminación train/test | `backtesting/tuning.py:75-133` + `roi_engine.py:190` | Sin confirmar que `tune_*` use un periodo anterior a `bet_from_date` | leakage-detector | M |
| [PRF-01] | Media | Confirmado | Concurrencia | `storage/lock.py:48-51` | El lock se degrada a "sin lock" y escribe igual; solo queda constancia en el log | python-engineer | S |
| [PRF-02] | Media | Confirmado | Disponibilidad | `storage/lock.py:41-52` | Mismo defecto que [COR-04], visto como riesgo de cuelgue del run diario | python-engineer | S |
| [TST-03] | Media | Confirmado | Instrumentación | `.github/workflows/ci.yml:58-62` | `pytest-cov` no instalado en local; cobertura en CI sin umbral | qa-engineer | S |
| [TST-04] | Media | Alta confianza | Cobertura ausente | `storage/lock.py`, `storage/atomic.py` (+4) | 6 módulos sin import en ningún test; 2 son infraestructura crítica | qa-engineer | S |
| [TST-05] | Media | Confirmado | Estrategia de pruebas | `tests/test_{kelly,vig,edge}.py` | Sin tests de propiedad sobre ~150 líneas de funciones puras de mercado y riesgo | qa-engineer | M |
| [OPS-01] | Media | Confirmado | Entorno | `.github/workflows/ci.yml:19-21` vs runtime 3.14.4 | Se opera en Python 3.14; el CI valida 3.11–3.13 | devops-engineer | S |
| [OPS-03] | Media | Confirmado | Documentación | `configs/default.yaml:11-26` | El YAML documenta valores nominales que no son los efectivos (ver [QNT-01]) | documentation-writer | S |
| [ARCH-04] | Baja | Confirmado | Duplicación | `audit/clv.py:124-136` vs `audit/clv_movement.py:131-152` | Agregación de CLV duplicada; un cambio de definición exige dos ediciones | backend-architect | S |
| [ARCH-05] | Baja | Confirmado | Mantenibilidad | `audit/html_report.py` (832 líneas) | Cálculo y presentación mezclados en el archivo más grande del proyecto | backend-architect | L |
| [COR-06] | Baja | Requiere verif. | Manejo de errores | `markets/vig.py:36-42` | Solo se captura `ValueError` de `brentq`; `RuntimeError` propagaría | python-engineer | S |
| [COR-07] | Baja | Confirmado | Integridad de datos | `storage/atomic.py:16-22` | Sin `fsync` antes del `replace`: atómico entre procesos, no ante corte de energía | python-engineer | S |
| [COR-08] | Baja | Confirmado | Coste / errores | `pipeline/daily.py:513-517` | La comprobación de temporada falla-abierto hacia el gasto de cuota | provider-integrator | S |
| [QNT-08] | Baja | Requiere verif. | Corrección numérica | `pipeline/probabilities.py:58-68` | El no-vig de h2h agrupa sin filtrar por `point` y usa un mínimo, no una igualdad | odds-market-auditor | S |
| [DAT-08] | Baja | Confirmado | Escalabilidad | `backtesting/roi_engine.py:63-66` | `load_closing_odds` concatena todo el histórico de la liga por llamada | performance-engineer | M |
| [SEC-04] | Baja | Confirmado (mecanismo) | Deserialización | `calibration/calibrator.py:50-54`, `models/ml_predict.py:17-21` | `joblib`/pickle desde `data/models/`; riesgo depende del modelo de amenaza | security-reviewer | S |
| [SEC-05] | Baja | Confirmado | Fallo silencioso | `audit/html_report.py:208,395` (+3) | 5 manejadores amplios descartan la excepción sin registrarla | python-engineer | S |
| [PRF-03] | Baja | Confirmado | Escalabilidad | `backtesting/roi_engine.py:63-66` | Mismo defecto que [DAT-08], visto como rendimiento | performance-engineer | M |
| [PRF-05] | Baja | Confirmado | Ciclo de desarrollo | `audit/01-baseline-results.md:47` | Sin medición de cobertura disponible ni bloqueante | qa-engineer | S |
| [PRF-06] | Baja | Confirmado | Fiabilidad operativa | `DIARIO_COMPLETO.bat` | Punto de fallo total documentado y acotado — **sin acción pendiente** | devops-engineer | — |
| [OPS-02] | Baja | Confirmado | Documentación | `Makefile:15` | `make check` es la puerta documentada y `make` no existe en el entorno | devops-engineer | S |
| [OPS-04] | Baja | Confirmado | Higiene | raíz: `rc`, `t`, `tatus`, `observaciones…` | 4 residuos de shell sin trackear; precedente de commit accidental (B-2) | devops-engineer | S |
| [ARCH-06] | Info | Confirmado | Arquitectura | `risk/clv_gate.py:8-10` | La prohibición de ciclos existe solo como comentario, sin test que la imponga | backend-architect | S |
| [QNT-07] | Info | Confirmado | Reglas de puntuación | `backtesting/engine.py:33-54` | Condicionamiento de empates correcto — **verificado sin hallazgos** | calibration-auditor | — |
| [SEC-01] | Info | Confirmado | Red | `providers/*` (8 llamadas) | Todas las llamadas HTTP declaran timeout — **verificado sin hallazgos** | security-reviewer | — |
| [SEC-02] | Info | Confirmado | Secretos | `providers/odds_api.py:114-143` | Redacción de `apiKey` implementada en ambos caminos de error — **verificado** | security-reviewer | — |
| [SEC-03] | Info | Confirmado | Inyección | `scripts/claude_project_health.py:32-42` | Único `subprocess` es seguro; sin `eval`/`exec`/`shell=True` — **verificado** | security-reviewer | — |
| [SEC-06] | Info | Requiere verif. | Secretos | `.env.example` | **Lectura denegada por permisos**: no verificable en esta pasada | security-reviewer | S |
| [PRF-04] | Info | Requiere verif. | Rendimiento | `configs/default.yaml:43-45` | Sin confirmar si Monte Carlo se invoca en el run diario o solo como cross-check | performance-engineer | — |
| [PRF-07] | Info | Confirmado | Idempotencia | `pipeline/daily.py:561-577` | Caché y dedup del served stream correctos — **verificado sin hallazgos** | data-engineer | — |
| [TST-06] | Info | Confirmado | Estrategia | `tests/test_audit_2026_07_29.py` (+) | Suite fuertemente orientada a regresiones vividas — **fortaleza** | qa-engineer | — |
| [OPS-05] | Info | Requiere verif. | Operación | `Obsidian/Estado del proyecto.md` | Las 6 tareas del Programador no son verificables desde el repositorio | devops-engineer | S |
| [OPS-07] | Info | Confirmado | Documentación | `README.md:109-123` vs `configs/default.yaml:72` | `pick_mode` documentado y configurado coinciden — **verificado sin hallazgos** | documentation-writer | — |
| [OPS-08] | Info | Confirmado | Cumplimiento | `backtesting/engine.py:78`, `pipeline/daily.py:369` | El lenguaje obligatorio está en el código, no solo en la doc — **verificado** | documentation-writer | — |

## Recuento por confianza

| Confianza | Nº | Comentario |
|---|---:|---|
| Confirmado por **ejecución** | 5 | [COR-01], [COR-02], [QNT-01], [QNT-04] y la línea base de `01` |
| Confirmado por lectura directa | 37 | Ruta y símbolo citados en cada uno |
| Alta confianza (heredado, no re-medido) | 3 | [DAT-04], [OPS-06], [TST-04] |
| **Requiere verificación** | 8 | [COR-05], [COR-06], [QNT-08], [DAT-05], [DAT-07], [SEC-06], [PRF-04], [OPS-05] |
| Reachability pendiente pese a comportamiento confirmado | 2 | [COR-01], [COR-02] — el defecto está probado; su frecuencia real no |
