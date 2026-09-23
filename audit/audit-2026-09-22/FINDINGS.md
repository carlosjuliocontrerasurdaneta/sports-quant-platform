# FINDINGS — ronda `audit-2026-09-22`

Línea base de diagnóstico de la ronda. Las fases posteriores **no** borran ni
reescriben estos hallazgos para simular su cierre.

- **Ronda:** `audit-2026-09-22`
- **Base:** `9fa276a` (`main`), árbol limpio al inicio
- **Alcance:** auditoría integral (código, scripts, BAT/PowerShell, configuración,
  dependencias, seguridad, datos operativos por agregados, modelos y calibración,
  pipeline y riesgo, sistema de skills/agentes/hooks, CI y tareas programadas),
  incluyendo el **estado observado** de cada control.
- **Auditores disponibles:** Claude (`claude-opus-5`). **No hubo segunda
  opinión**: no se solicitó ni ejecutó un auditor OpenAI para esta ronda.
  `audit/latest/openai/` conserva el informe de `audit-2026-09-18` y **no forma
  parte de esta ronda** (su ruta y hash quedan registrados en `MANIFEST.json`).
- **Informe fuente:** `audit/latest/claude/REPORT.md` + `claude/EVIDENCE.json`.

---

## Métricas

| Métrica | Valor |
|---|---|
| Hallazgos confirmados | 8 |
| Por severidad | MEDIUM 4 · LOW 4 |
| Por prioridad | **P1 1** · P2 3 · P3 4 |
| Candidatos descartados con evidencia | 12 (uno retirado y promovido a `AUD-008`) |
| No verificables declarados | 2 |
| Observaciones informativas | 5 |
| Regresiones respecto a la ronda anterior | 0 |
| IDs históricos revalidados | 7 (6 corregidos, 1 persistente) |
| Áreas de cobertura | 17 REVISADA · 5 REVISADA_PARCIALMENTE · 2 NO_APLICABLE · 2 NO_VERIFICABLE · 2 EXCLUIDA |

**Origen de los hallazgos:** los 8 son *exclusivo Claude*. Esta dimensión se
mantiene separada del estado de evidencia: que no haya segundo auditor no eleva
ni rebaja la confianza de ninguno.

---

## Tabla consolidada

Ordenada por prioridad.

| ID | Alias origen | Origen | Sev. | Conf. | Evidencia | Prio | Problema | Archivos |
|---|---|---|---|---|---|---|---|---|
| `AUD-007` | CLAUDE-007 | exclusivo Claude | MEDIUM | HIGH | `REPRODUCED` | **P1** | El hook `Stop` de pruebas **no cabe en su timeout**: su comando tarda **796,09 s** medidos contra un presupuesto de **600 s**, así que el harness lo mata y el veredicto nunca llega — el turno cierra en verde sin comprobar la suite. Peor: `rm -f "$marker"` está sólo en la rama de éxito, así que un hook matado deja el centinela puesto y el turno siguiente repite los 600 s sin veredicto. Serie: 270,73 s (2026-09-04, 45 % del presupuesto) → 489,76 s (2026-09-18, 82 %) → **796,09 s (hoy, 133 %)** | `.claude/settings.json` (`Stop`, `timeout: 600`); `.claude/hooks/run-tests-on-stop.sh` |
| `AUD-001` | CLAUDE-001 | exclusivo Claude | MEDIUM | HIGH | `STATICALLY_VERIFIED` | P2 | El gate de predicción reparte alpha por Bonferroni entre `K=41` cortes pero evalúa **49**: la cota real de error de familia es `49×0,05/41 = 0,0598`, un 19,5 % por encima del 0,05 declarado. La alarma de re-pre-registro sólo salta con `>50`, así que nunca ha saltado y está a un corte de hacerlo | `src/sqp/risk/prediction_gate.py:102-113,452-466`; `data/bets/prediction_gate.json` (`k_bonferroni 41`, `n_cortes_evaluados 49`, 2026-09-21T15:08:25Z); `docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md:115-125` |
| `AUD-008` | CLAUDE-008 | exclusivo Claude | MEDIUM | HIGH | `REPRODUCED` | P2 | **La revisión cruzada de Codex no se ejecuta.** El runtime abre hilo, devuelve `rawOutput` vacío y sale con código 1 (`codex --version` sí responde: el binario está, el servicio no). Todo cambio de riesgo cierra turno sin revisión de un tercero. Además el gate `Stop` del plugin compone el detalle del error con el primer `stderr` no vacío, que era un aviso de obsolescencia de Node: presenta una causa falsa y **bloquea** el cierre, mientras el hook del propio proyecto degrada bien | `.claude/hooks/crossreview-on-stop.sh`; gate `Stop` del plugin `codex` (`stop-review-gate-hook.mjs:99-128`); reproducido con `codex-companion.mjs task --json` |
| `AUD-002` | CLAUDE-002 | exclusivo Claude | MEDIUM | MEDIUM | `INFERRED` | P2 | La captura Fase 1 de `team_totals` no tiene control de cobertura: pasó de 15 eventos a **3** en un día, sin motivo de parada y sin aviso. Nada compara lo capturado con la jornada esperada, y una muestra pre-registrada recogida con cobertura irregular introduce selección no aleatoria | `src/sqp/pipeline/team_totals_capture.py:201-210,282-285`; `scripts/collect_team_totals_mlb.py`; agregados de `data/odds/team_totals_mlb_202609.csv`; `logs/sqp.log` (líneas filtradas) |
| `AUD-003` | CLAUDE-003 | exclusivo Claude | LOW | HIGH | `REPRODUCED` | P3 | El tope diario de 45 créditos se comprueba **antes** de una petición que cuesta 2, así que se rebasa: producción registró `tope de creditos alcanzado (46/45 hoy)` y el contador del día quedó en 46 | `src/sqp/pipeline/team_totals_capture.py:45,227-231`; `data/odds/.team_totals_credits_2026-09-19` |
| `AUD-004` | CLAUDE-004 | exclusivo Claude | LOW | HIGH | `STATICALLY_VERIFIED` + fallo observado | P3 | `assert time.monotonic() - started < 4` sobre una implementación cuyo plazo de reintentos es 2,0 s: margen 2×, insuficiente bajo carga. Falló en la suite completa (4,485 s) y pasó 5/5 aislado. Vuelve no determinista la puerta que el hook `Stop` convierte en bloqueo de turno | `tests/test_audit_atomic_readers.py:49`; `src/sqp/storage/atomic.py:29` |
| `AUD-005` | CLAUDE-005 | exclusivo Claude | LOW | HIGH | `STATICALLY_VERIFIED` (divergencia latente) | P3 | `bankroll.summary()` es el único consumidor de ROI realizado que no pasa por la definición canónica `settle.realized_roi_parts`: suma `pnl` de **todas** las filas liquidadas y lo divide por el stake de **sólo** las de stake arriesgado. Hoy coincide (−0,152588 por ambas vías) porque `push`/`void` traen `pnl 0` | `src/sqp/risk/bankroll.py:225-233,333-350`; `src/sqp/settlement/settle.py:115-140` |
| `AUD-006` | CLAUDE-006 | exclusivo Claude | LOW | HIGH | `STATICALLY_VERIFIED` | P3 | La lista blanca de `purge_old_artifacts` cubre `.closing_credits_*` pero no `.team_totals_credits_*`, introducida el 2026-09-19: la familia crece sin techo (~365 ficheros/año), que es la causa raíz que `AUD-LOW-002` (2026-09-13) creó la lista para detener | `src/sqp/pipeline/cleanup.py:250-262`; `src/sqp/pipeline/team_totals_capture.py:48` |

---

## Agrupación por causa raíz

**G1 — Un umbral fijado una vez deja de seguir a la magnitud que vigila.**
`AUD-007` (600 s contra una suite que creció de 270 s a 796 s), `AUD-001`
(alarma en 50 en vez de en `K`, con el universo de 41 a 49) y `AUD-004` (4 s de
reloj de pared en vez del plazo de 2,0 s de la implementación). Misma forma en
tres dominios: el control compara contra una constante en lugar de contra la
propiedad. Se mantienen separados porque impacto y corrección son materialmente
distintos —uno es un presupuesto de harness, otro un parámetro pre-registrado
con escalación, el tercero una prueba—, pero **quien remedie debería leerlos
juntos**: la corrección duradera de los tres es la misma idea, atar el umbral a
lo que mide.

**G2 — El colector `team_totals` (2026-09-19) no heredó las envolturas que el
resto del pipeline ya tenía.** `AUD-002` (sin control de cobertura),
`AUD-003` (guarda de presupuesto post-hoc) y `AUD-006` (familia fuera de la
lista de retención). Comparten causa —módulo nuevo que copió los mecanismos pero
no los ganchos de observabilidad y retención— pero no solución, así que el
backlog los ordena juntos y consecutivos.

**G3 — Una definición canónica enrutó a los consumidores incorrectos y dejó
fuera al que ya acertaba por casualidad.** `AUD-005`, aislado.

**G4 — Un control que dice algo distinto de lo que mide.** `AUD-008`: el gate
presenta un aviso de obsolescencia de Node como causa del fallo de la revisión.
Es el patrón `KI-035`, que el proyecto ya corrigió en su propio hook, reaparecido
en el del plugin — fuera de su control.

---

## No verificables

| Asunto | Por qué | A qué afecta |
|---|---|---|
| Cuota real restante en The Odds API | Consultarla exige una llamada externa, prohibida durante el diagnóstico | `AUD-002` (descarta/confirma una de las causas posibles de la caída de cobertura) |
| Calendario MLB del 2026-09-21 | El almacén local de resultados llega al 2026-09-20 | `AUD-002`. **El hallazgo no depende de la respuesta**: la ausencia de control de cobertura es el defecto, juegue la MLB 3 partidos o 15 |

---

## Observaciones informativas

No son defectos. Detalle y cifras en `claude/REPORT.md` §7.

1. **ROI realizado acumulado: −15,26 %** (pnl −84,25 sobre 552,14 de stake
   arriesgado, 1925 filas graduadas). Tasa de acierto observada 38,96 %. Son ROI
   realizado y acierto observado sobre el histórico liquidado: no son
   probabilidad estimada, ni implícita, ni edge, ni ROI esperado, ni promesa de
   rentabilidad.
2. **Gate de predicción: 0 de 49 cortes habilitados**, los 49 en
   `muestra_insuficiente`, sin pestillos. Default-deny efectivo.
3. **Monitor de degradación: 12 de 59 cortes auto-pausados.** El control actúa.
4. **Line shopping inerte**: `execution.books = []`, así que `execution_price`
   repite la mediana del consenso en todas las filas y `price_decimal`, no-vig,
   edge, selección, stake y liquidación siguen sobre la mediana.
5. **Invariantes de la Fase 1 de derivados verificados**: Over+Under = 1,000000
   exacto en las 204 selecciones, 0 filas con `captured_at ≥ commence_time`,
   adelanto mediano 7,53 h.

---

## Descartes

12 candidatos descartados con su explicación en `claude/REPORT.md` §6. Los tres
más relevantes:

- **`grade_captures` no lanza** con ninguna fila graduable (reproducido con tres
  casos bajo pandas 3.0.2).
- **El estado de la pausa por degradación no contradice su log** (12 pausados;
  cada `pause` con `paused=true` vivo). Una primera lectura mía usó claves
  inexistentes; corregida con medición.
- **`registry.json` con rutas de árboles retirados es historia legítima**: es
  append-only y las 36 entradas vigentes apuntan a `C:\dev\3`.

---

## Comparación histórica (ronda `audit-2026-09-18`)

Cada ID revalidado contra el código actual **después** de fijar las conclusiones
propias. Tabla completa en `claude/REPORT.md` §8.

| ID | Estado | Resumen de la evidencia |
|---|---|---|
| `AUD-001` (r18) | **CORREGIDO** | `gate_status.py` importa el criterio canónico; sin regla paralela |
| `AUD-002` (r18) | **CORREGIDO** | Ambos lectores comprueban `isinstance(payload, dict)` antes del `.get` |
| `AUD-003` (r18) | **CORREGIDO** | `mlb_h2h_pergame` fuera del registro live; degradación en `promotion_log.csv:102` |
| `AUD-004` (r18) | **PERSISTENTE** | `history_enabled = false` en `pipeline_health.json` (2026-09-21). La remediación añadió detección, no la habilitación (exige elevación) |
| `AUD-005` (r18) | **CORREGIDO** | `run_all.py` lee el veredicto del registro escrito, no de `decided` |
| `AUD-006` (r18) | **CORREGIDO** | `markets_for_family` devuelve `"h2h"` en tenis y la captura de cierre la usa |
| `AUD-007` (r18) | **CORREGIDO** | `_secret_literals._symbolic()` descarta asignaciones reflexivas; sin reincidencia |

**Balance:** 6 corregidos, 1 persistente, **0 regresiones**.

---

## Limitaciones de la consolidación

1. **Un solo auditor.** Se declara la ausencia de segunda opinión; no se ha
   inventado informe del auditor ausente ni se ha presentado coincidencia alguna
   como confirmación cruzada.
2. **Consolidar no autoriza correcciones.** Ninguna de las 7 IDs está autorizada
   para implementar. `AUD-001` además pertenece a la clase de **escalación**
   (parámetro de gate) según `CLAUDE.md`.
3. **Residuo de la ronda anterior en `latest`.** `openai/REPORT.md`,
   `openai/EVIDENCE.json` y `history/manifest-20260918T121551Z` pertenecen a
   `audit-2026-09-18`, están preservados íntegros en `audit/audit-2026-09-18/` y
   **no** forman parte de esta ronda. Retirarlos de `latest` es una eliminación y
   requiere autorización explícita: se registra como pendiente, no se ejecuta.
4. **Auditoría completa no significa código corregido**, ni pruebas no
   ejecutadas aprobadas, ni ventaja predictiva demostrada.
