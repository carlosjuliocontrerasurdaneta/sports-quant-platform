# Verificación independiente · ronda `audit-2026-09-23`

## Veredicto: **NO APTO**

Se aplica la regla 1 del contrato (`audits/prompts/verificar-remediacion.md`): queda abierto un P1 original, **AUD-003**, que está bloqueado. Es el caso «P1 original bloqueado + tests verdes → NO APTO».

El resto de la remediación se sostiene:

- 12 IDs verificados-corregidos;
- 1 verificado-mitigado (AUD-004);
- ninguna regresión atribuible a `33ba978`;
- validación global en verde.

Este veredicto califica solo la remediación evaluada. No garantiza ausencia de defectos ni rentabilidad.

## 1. Alcance y metodología

- **Verificador:** agente nuevo `independent-code-reviewer` en `fable`, por la regla 1 de `MODEL_ROUTING.md`. No tenía el contexto de la sesión que implementó y trabajó en solo lectura. Redactó los entregables la sesión principal (`claude-opus-5-5`), que es la que implementó. Todo lo evaluado y la evidencia son del verificador.
- **Objeto evaluado:** `main` @ `1a0f746`, publicado, con CI en verde. La base es `7bd565e` y la remediación de código es `33ba978`. `git diff 33ba978 1a0f746 -- src scripts tests .claude/hooks configs` sale vacío. El árbol estaba limpio al empezar y al terminar.
- **Método por ID:**
  - reconstruir la causa y la activación originales;
  - inspeccionar el parche y sus llamadores;
  - reproducir el escenario en un ROOT temporal;
  - ejecutar los tests contra HEAD y contra la base exportada con `git archive 7bd565e` (`-o pythonpath=`);
  - comprobar cada criterio de aceptación;
  - buscar regresiones, bypass y fallos trasladados.
- **Tests de la remediación (13 ficheros):**
  - **HEAD:** 293 passed.
  - **Base:** 44 failed y 244 passed. Fallan todos los discriminantes; algunos fallos son de entorno de la copia (tests de BAT, documentación y reinstalación de hooks).
  - `test_gate_block_visibility.py` no se puede recoger en la base, porque el símbolo que importa no existe allí.

## 2. Estado por ID

| ID | Sev./Prio. | Estado | Evidencia principal | Criterio |
|---|---|---|---|---|
| AUD-001 | HIGH/P1 | **verificado-corregido** | `run_all.py:259-266` y `daily.py:673`. Prueba de extremo a extremo propia con `main --mode live --no-report`, gate real y `run_league` real: «autorizado ayer / sin evaluación hoy» da pestillo y **stake 0** en HEAD (en la base, stakes 3,37/2,89/3,71/3,59). Un fallo del store o un lock retenido también dan stake 0 | cumplido. Residual: `run_daily.py --mode live` (manual, no invocado por ningún BAT) usa el registro persistido |
| AUD-002 | HIGH/P1 | **verificado-corregido** | `prediction_gate.py:471` y `:607`: el mismo lock cubre toda la transacción. Sin reentrada (grep de `locked(`). Falla cerrado ante `LockNoAdquiridoError`. 2 tests de concurrencia: fallan en la base, pasan en HEAD | cumplido |
| AUD-003 | HIGH/P1 | **ABIERTO (bloqueado)** | `runner.py:703-714`: sin fallback para candidatos de equipo. El escenario original **sigue ocurriendo** (`void/stale_void` con 70-80 en el histórico). El de FABLE-001 **no ocurre** | **no cumplido.** Pendiente de la decisión de identidad de eventos (KI-057) |
| AUD-004 | MEDIUM/P2 | **verificado-mitigado** | `runner.py:700`: `start_time` del archivo, con el fichero vigente por delante. Test: falla en la base, pasa en HEAD, idempotente | cumplido. **Riesgo residual:** un desplazado *jugado* y no liquidado en ventana pasa de «sin veredicto» a `stale_void` irreversible (el fallo de AUD-003 se traslada). FABLE-002 midió 0 casos en la primera pasada (2026-09-23) |
| AUD-005 | MEDIUM/P2 | **verificado-corregido** | `daily.py:933-1009`. Topes de exposición seguros con banca ≤ 0. `cleanup._actionable` trata `bankroll_zero` como bloqueante. 2 tests (edge y accuracy) | cumplido |
| AUD-006 | MEDIUM/P2 | **verificado-corregido** | `daily_picks.py:123`, `report.py:250`. `roi_esp` = `estimated_edge` salvo redondeo | cumplido |
| AUD-007 | MEDIUM/P2 | **verificado-corregido** | 60/20/20: objetivo ponderado 0,6667 sobre 100 filas (base: 0,75 sobre 80). Sin medias, registro de entrenamiento idéntico bit a bit entre base y HEAD | cumplido. No promueve nada |
| AUD-008 | MEDIUM/P2 | **verificado-corregido** | 1 win + 10 `half_loss`: ROI −0,3636 con n = 11 (base: +1,0 con n = 1), igual a `realized_roi_parts`. El hit rate binario no cambia | cumplido |
| AUD-009 | MEDIUM/P2 | **verificado-corregido** | Lock en los tres stores, sin red dentro. 3 tests con barrera | cumplido. Residual: `log_pitcher_confirmation`, misma clase, sin tocar |
| AUD-010 | MEDIUM/P2 | **verificado-corregido** | `mlb_statsapi.py:128-134`. 4 casos | cumplido |
| AUD-011 | MEDIUM/P2 | **verificado-corregido** | `codex` falso: con rc 7 y salida vacía, o rc 0 y salida vacía, HEAD conserva el marcador y la base lo pierde. Veredicto y «usage limit» se comportan igual en ambos | cumplido. Observación preexistente: sin `codex` instalado el marcador se sigue borrando (`:18`) |
| AUD-012 | LOW/P3 | **verificado-corregido** | `daily.py:431-445`, `runner.py:38`. El orden por nombre conserva la generación más reciente | cumplido. Observación: el test deja de discriminar si corre entre las 01:00 y las 03:00 UTC |
| AUD-013 | LOW/P3 | **verificado-corregido** | `health.py:481`, `gate_status.py:97`. `health_check` corre a diario (`DIARIO_COMPLETO.bat:247`) | cumplido |
| AUD-014 | LOW/P3 | **verificado-corregido** | MC Over 2,25 = 0,52349 frente a 0,52330 analítico (base 0,45649). Las líneas 2,5 y 3,0 dan idéntico que en la base | cumplido |

## 3. Regresiones

- **Ninguna `REG-###` atribuible a `33ba978`.**
- **Defecto nuevo PREEXISTENTE, no regresión, fuera de la línea base de esta ronda**, a incorporar en la próxima (registrado como KI-058):
  - `_grade_served_from_history` → `history_scores_map` (`runner.py:214-241`) tiene la misma clase de fallo que FABLE-001.
  - Una fila servida del juego N de una serie **aplazado** (su `start_time` ya pasó, así que está en `pending`) se gradúa con el marcador del juego N-1.
  - Reproducido por el verificador en un ROOT temporal: `gN` quedó `loss` con el 2-5 de `gN-1`.
  - Ese stream alimenta el prediction gate y los calibradores. Impacto INFERRED; severidad propuesta MEDIUM/P2.

## 4. Validación global

| Comando | Exit | Resultado |
|---|---|---|
| `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-verif-full` | 0 | **2350 passed, 1 skipped**, 19 min 55 s |
| `ruff check src scripts tests` | 0 | All checks passed |
| `mypy src` | 0 | 106 ficheros, sin problemas |
| `gh run list` | — | CI **success** en `1a0f746` y en `7bd565e` |

## 5. P0/P1 abiertos

- **P0:** ninguno.
- **P1: AUD-003**, bloqueado. Hoy su impacto está contenido porque el gate tiene 0 de 49 cortes autorizados y todo el stake es 0. La anulación que produce es irreversible.

## 6. Limitaciones

- **Llamadas reales a Codex por error del verificador:** en el arnés de AUD-011, un `PATH` mal formado (el `C:` se partía en `:`) hizo ejecutar el `codex` **real** hasta 7 veces (`codex review --commit HEAD`). Fue sobre un repo vacío del scratchpad, fuera del proyecto. No tocó el repositorio, pero **puede haber consumido cuota de Codex**. Esos resultados se descartaron y la prueba se repitió con el doble.
- Los arneses importan `sqp` y pueden haber añadido líneas a `logs/sqp.log`, que está ignorado por Git y no se leyó.
- No se midió la frecuencia productiva de los `stale_void` con resultado histórico (AUD-003/004), porque exigiría leer datos a nivel de fila.
- AUD-002 se probó con hilos de un solo proceso, más revisión estructural del lock entre procesos.
- La identidad bit a bit del calibrador se comprobó sobre las métricas del registro de entrenamiento; no hubo mapas persistidos que comparar.
- El verificador no creó el JSON de revisión cruzada V2: la tarea no traía `run_id` ni `review_tree`.
- **Ronda r2** (`audit/audit-2026-09-22-r2/`): sigue sin verificación independiente, y esta fase no la cubre.

## 7. Próxima acción

1. **Decisión del operador sobre la identidad de eventos entre proveedores** (KI-057). Por ejemplo, un id del vendor en el candidato, o una fecha local exacta con zona horaria por liga. Desbloquea AUD-003 y requiere tests de serie, aplazado y doubleheader.
2. Aplicar la misma regla al stream servido (KI-058).
3. Con AUD-003 resuelto, decidir si se reconcilian los `stale_void` ya persistidos. Requiere autorización aparte.
4. Próxima ronda: `log_pitcher_confirmation` (residual de AUD-009) y el borrado del marcador cuando falta `codex` (AUD-011).

## 8. Verificación de la remediación 2 (2026-09-25, sobre `8b19c5d`)

- **Verificador:** agente nuevo en `fable`, en solo lectura. Objeto: el commit `519d580` (AUD-003 y KI-058).
- **Método:** mutaciones sobre copias y reproducción de punta a punta con `fetch_and_settle` real en un ROOT temporal.

**AUD-003:**
- **ESPN: verificado-corregido.**
  - WNBA con resultado exacto en el histórico: base `void`, HEAD `loss −100`, idempotente.
  - Contraprueba sin resultado: sigue expirando.
- **MLB: sigue abierto.** El escenario original acaba en `void/stale_void` por la exclusión (`runner.py:695`).
  - MLB es la liga con más candidatos liquidados (526 filas).
  - Quitar la exclusión no lo arreglaría: la guarda de adyacencia bloquea 647 de 694 eventos MLB, porque las series juegan días consecutivos.
  - Hace falta KI-059.

**KI-058: corregido.** WNBA y MLB con el marcador de la víspera: base 1 graduada mal, HEAD 0.

**Ningún camino liquida con el marcador de otro partido:**
- 0 contradicciones al re-graduar los eventos servidos de 14 ligas.
- Los tests detectan las mutaciones de las guardas de inicio, adyacencia, doubleheader propio y exclusión MLB, y la fecha UTC para MLB.

**Cobertura:**
- **REG-001 (LOW/P3):** si el stream servido ESPN vuelve a ±1, ningún test lo detecta.
- La franja de Asia no tiene un test propio.

**Validación global:**

| Comprobación | Resultado |
|---|---|
| ruff | exit 0 |
| mypy | 106 ficheros OK |
| suite completa | 2361 passed, 1 skipped |
| CI de `8b19c5d` | success |

**Veredicto de la ronda: NO APTO** (regla 1). AUD-003 (P1) sigue abierto en MLB.

**Próxima acción:**
1. KI-059: identidad de calendario MLB.
2. Test de REG-001.
3. Test de la franja de Asia.
