# Verificación independiente · ronda `audit-2026-09-22-r2`

## Veredicto: **APTO CON PENDIENTES**

Regla 3 del contrato (`audits/prompts/verificar-remediacion.md`): no queda ningún P0/P1 abierto, las validaciones pasan y quedan pendientes menores. Este veredicto califica solo la remediación evaluada; no garantiza ausencia de defectos ni rentabilidad.

- **P0/P1 de la ronda:**
  - AUD-001 (P0): verificado-corregido.
  - AUD-002 (P1): verificado-mitigado.
  - AUD-003 (P1): verificado-corregido.
  - AUD-004 (P1): verificado-corregido.
- **Pendientes:**
  - REG-001 (MEDIUM/P2): regresión nueva ligada a AUD-002.
  - El riesgo residual declarado de AUD-002.
  - CLN-001 (P3).

## 1. Alcance y metodología

**Quién verificó.** Un agente nuevo `independent-code-reviewer` en `fable` (regla 1 de `MODEL_ROUTING.md`), sin participación en la remediación de r2 y en solo lectura. Los entregables los redactó la sesión coordinadora a partir de la evidencia del verificador.

**Objeto.** `main` @ `52867ab`, publicado y con CI verde. La base de r2 es `9fa276a`. Commits de su remediación: `c6f1971`, `d718fa1`, `af9d156`, `4fa1673`, `efe09bb` y `7bd565e` (este último, solo memoria).

**Cambios posteriores sobre el mismo código.** El gate recibió después lock y actualización antes del bucle (ronda `audit-2026-09-23`, `33ba978`), y el BAT recibió un backfill (`32dd92c`). En cada ID se separa lo que corrigió r2 de lo que se añadió después.

**Método:**
- Bases exportadas con `git archive`: `9fa276a`, que es el estado anterior a r2, y `d718fa1`, el anterior a AUD-003.
- Reproducciones en directorios temporales.
- 12 mutantes sobre copias de `src/` más un control.
- Consulta de solo lectura al Programador de tareas.
- De `data/` solo se leyeron agregados. `logs/` no se pudo leer (permiso denegado).

## 2. Estado por ID

| ID | Sev./Prio. | Estado | Evidencia |
|---|---|---|---|
| AUD-001 | HIGH/P0 | **verificado-corregido** | Remediación publicada antes del run del 23/09 (CI `35804096043`, 00:54Z). Hoy `git status --porcelain -- src scripts configs *.bat` da 0 líneas; la guarda está en `DIARIO_COMPLETO.bat:73` y aborta antes de liquidar. El run del 23/09 no abortó: a las 12 h de ese día se modificaron 16 ficheros de `data/predictions` y 3 de `data/bets` (deducido; el log no se pudo leer). `SQP_Diario_Completo_Cdev` terminó el 24/09 con `LastTaskResult 0` |
| AUD-002 | HIGH/P1 | **verificado-mitigado** | Ver el detalle debajo de la tabla |
| AUD-003 | MEDIUM/P1 | **verificado-corregido** | Con 41 cortes no hay aviso. Con 42, 49 y 50 cortes, INFO con la cota y sin orden (antes, WARNING «RE-PRE-REGISTRAR»). Con 51, ERROR con la orden. Fiel al pre-registro 2026-09-04 §3.1. `fwer_bound` se conserva |
| AUD-004 | MEDIUM/P1 | **verificado-corregido** | `.claude/skills/full-audit/` sin cambios respecto a HEAD (último commit `56edbcd`). La reversión a `8952755` ya no está (969 líneas de diferencia). Tests de contrato y sincronización: 31/31. `sync_agent_instructions --check` y `validate_claude_model_routing`: OK |
| CLN-001 | —/P3 | **sigue parcial** | `.codex-tmp/` tiene hoy 99 directorios y 19 ficheros; ha vuelto a crecer con rondas posteriores. Los 8 directorios con ACL denegada siguen sin verificar. No se borró nada |
| IDs de r22 (tabla de STATUS) | — | **fuera de verificación formal** | Solo se comprobó que la suite completa está en verde |

**Detalle de AUD-002:**
- **Escenario original, antes de la corrección** (`9fa276a` y `d718fa1`):
  - un registro corrupto con el test de entrada gastado acababa en `allowed True`;
  - borrar el registro también daba `allowed True`;
  - los bytes no UTF-8 hacían que el consumidor lanzara un `UnicodeDecodeError` no capturado.
- **Después, en HEAD:**
  - el escritor lanza `RegistroEstadoIlegibleError` y deja el fichero intacto;
  - se escribe el centinela y el consumidor da `allowed False`;
  - borrar el registro con el centinela presente lanza error;
  - la recuperación con `bloqueo_de_lectura` funciona.
- **Degradación:** las pausas se reconstruyen desde `degradation_log.csv`. En producción el log y el registro coinciden: 12 pausas en cada uno, 0 diferencias.
- **Rutas alternativas (bypass):** ninguna. Solo `_persist_under_lock` y `_release_under_lock` escriben el registro, bajo el mismo lock desde r23.
- **Mutaciones:** 12 de 12 muertas; el control pasa 114/114.
- **Riesgo residual:** ver §4.

## 3. Regresiones

### REG-001 (ligada a AUD-002): MEDIUM, confianza HIGH, REPRODUCED, P2

- **Qué pasa:** con `degradation_pause.json` ilegible, `run_degradation_monitor` lanza error y el fallback solo devuelve las pausas que ya constaban en el log. Así, **un mercado que se degrade por primera vez no se pausa** mientras dure la corrupción, y eso es indefinido porque el registro ya no se reescribe.
- **Reproducción:** con `mlb|totals` degradado (40 derrotas, Brier 0,49 frente a 0,25, ROI −1), la versión anterior lo pausaba; HEAD devuelve solo `{'nba': ['h2h']}`.
- **Ubicación:** `src/sqp/risk/degradation.py:204-217` y `:313`.
- **Controles compensatorios:** el prediction gate está en default-deny (0 mercados `allowed`), y se registra un ERROR cada día.
- **Corrección mínima:** en el fallback, evaluar `evaluate_pauses(metrics, previous=<estado reconstruido desde el log>)` sin reescribir el registro, más un test con un mercado que se degrade nuevo mientras el registro está corrupto.

## 4. Riesgo residual declarado de AUD-002 (reproducido)

- **Escenario:** si falla **también** la escritura del propio centinela, este no existe. Un consumidor que no revalida el gate (por ejemplo `run_daily.py`, que es manual) lee el `allowed True` vencido, y al recuperarse el corte sigue dentro sin pestillo (`allowed True, latched False`).
- **Condición:** hacen falta dos fallos correlacionados.
- **Compensación:** `run_all` compensa desde r23 con `gate_deny_all`.
- **Impacto hoy:** nulo, porque en producción hay 0 mercados `allowed` y no existe el centinela.

## 5. Validación global

| Comprobación | Resultado |
|---|---|
| `ruff check src scripts tests --no-cache` | rc 0 |
| `mypy src` | rc 0, 107 ficheros |
| Suite completa (`--basetemp=.codex-tmp/pytest-verifr2-full`) | **2386 passed, 1 skipped**, 1235 s, rc 0 |
| `gh run list` | CI en verde en `52867ab` y en los commits de r2 (`af9d156`, `4fa1673`, `7bd565e`). `efe09bb` se canceló porque lo sustituyó el run del commit siguiente |

## 6. Limitaciones y observaciones

- **Lectura de `logs/` denegada.** El resultado del run del 23/09 se deduce de los ficheros generados. El historial del Programador no permite leer ese día (KI-054).
- **Documentación de r2 incompleta (LOW/P3, proceso).** `CHANGES.md`, `VALIDATION.md` y el manifest de la ronda seguían describiendo «sin remediación». Este documento, el `STATUS.md` actualizado y el manifest dejan constancia de la remediación y de su verificación. `CHANGES.md` y `VALIDATION.md` se conservan como estaban, como parte de la historia de la ronda.
- **Aviso operativo (no es un defecto de r2).** El registro de producción evalúa **52 cortes** (`fwer_bound` 0,0634), por encima del límite de 50 del pre-registro. El ERROR «RE-PRE-REGISTRAR» es correcto: **el operador debe re-pre-registrar el criterio** antes de que un corte nuevo alcance n ≥ 300.
- **Fallo previo fuera de alcance.** `release_prediction_gate_latch` con un registro cuya raíz es una lista lanza `AttributeError`, sin escribir nada y sin abrir el gate. Ya ocurría en `9fa276a`.

## 7. Próxima acción

1. **Corregir REG-001** (P2), con su test.
2. **Decisión del operador:** re-pre-registrar el criterio del gate para K = 52.
3. CLN-001: inspeccionar los 8 directorios con ACL denegada usando la cuenta que los creó.
