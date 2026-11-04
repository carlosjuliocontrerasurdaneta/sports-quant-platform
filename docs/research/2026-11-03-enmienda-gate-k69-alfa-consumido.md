# Enmienda al re-pre-registro K = 69: el α ya consumido se cuenta a su precio real (KI-078)

**Fecha:** 2026-11-03.
**Estado:** **VIGENTE desde su commit.** Redactada por el escalón Fable, que es quien asume el papel de pre-registro según `.claude/automation/MODEL_ROUTING.md`. El operador la aprobó el 2026-11-03 (§8).
**Enmienda:** `docs/research/2026-11-02-repreregistro-gate-k69.md`, solo en dos puntos: el valor de α_corte (§3.1) y el cálculo de la cota (§3.4). Todo lo demás sigue vigente: K = 69, el techo de 84, `n ≥ 300`, el test único de entrada, la salida diaria, el pestillo y lo enumerado en su §3.5.

---

## 1. Motivo

El re-pre-registro del 2026-11-02 fijó α_corte = 0,05/69. Comprobó el techo con la cota `n × 0,05/69` (§3.4), lo que supone que **todos** los tests de la familia se hacen a 0,05/69. No es así. Seis cortes gastaron su test único de entrada entre el 2026-09-25 y el 2026-10-11, con α = 0,05/52 (§2 de aquel documento): `mlb|h2h`, `mlb|spreads`, `mlb|totals`, `ncaaf|h2h`, `ncaaf|spreads` y `ncaaf|totals`.

Bonferroni acota el error de familia con la **suma de los α realmente usados**, no con los que se usarían hoy. Lo detectó la revisión cruzada de Codex del 2026-11-03 y se comprobó con fracciones exactas (KI-078).

La tabla compara la cota publicada con la cota real. La real cuenta los seis tests a 0,05/52 y el resto a 0,05/69:

| cortes | cota publicada (n × 0,05/69) | cota real 6·0,05/52 + (n−6)·0,05/69 |
|---:|---:|---:|
| 68 | 0,049275 | 0,050697 |
| 69 (= K) | 0,050000 | **0,051421** |
| 74 (registro del 2026-11-03) | 0,053623 | 0,055045 |
| 82 | 0,059420 | 0,060842 |
| 84 (techo) | 0,060870 | **0,062291** |

De aquí salen dos consecuencias:

- **A K = 69 la familia no está en 0,05.** Así lo declaraban §3.3.2 («con K = 69 la cota es exactamente 0,05 cuando entra») y §3.5 («α de familia 0,05»).
- **A 84 cortes la cota supera la máxima tolerada**, que es 50 × 0,05/41 = 5/82 = 0,060976 (segundo invariante de §3.4). Con α = 0,05/69, el techo real sería 82.

Lo que **no** ha ocurrido: ningún test se ha decidido con la cifra equivocada.

- Desde el 2026-10-11 ningún corte ha alcanzado n ≥ 300. El máximo vivo es n = 224, en `nhl|spreads` y `nhl|totals` (registro del 2026-11-03T23:52Z).
- La cota solo emite un mensaje de log y no decide ninguna entrada (AUD-009, que esta enmienda no toca).

Hay un segundo hueco de la misma clase. `release_prediction_gate_latch` devuelve el test de entrada borrando `entry_test_at`, así que el test gastado desaparece del registro. El nuevo test que la liberación permite gasta α otra vez sin que nadie lo cuente. Hasta hoy no ha habido ninguna liberación.

## 2. Opciones

**A. Mantener α_corte = 0,05/69.** Implica aceptar una cota de familia de 0,051421 a K = 69 y bajar el techo a 82 (82: 0,060842 ≤ 0,060976; 83: 0,061566). Se rechaza por tres motivos:

1. Incumple lo aprobado en §3.5 y §3.3.2 (familia 0,05 a K = 69). Aceptar un 5,14 % es **relajar** el α de familia.
2. Cambia una constante derivada, el techo, y rompe la regla de tolerancia relativa ⌊K × 50/41⌋ = 84. Se cambian dos cosas para reparar una.
3. El α de familia declarado en el registro (`family_alpha: 0.05`) quedaría desmentido por construcción.

**B. Se adopta.** Cobrar a los seis tests su α real y repartir el resto entre los 63 tests que quedan por gastar.

## 3. Cálculo exacto (opción B)

```
α consumido heredado = 6 × 0,05/52 = 3/520           = 0,005769231
α_corte vivo         = (0,05 − 3/520) / (69 − 6)
                     = (1/20)·(46/52) / 63 = 23/32760 = 0,000702076
cota a K = 69        = 3/520 + 63 × 23/32760 = 189/32760 + 1449/32760 = 1638/32760 = 1/20   (exacta)
```

Comparación: 0,000702076 < 0,05/69 = 0,000724638 < 0,05/52 = 0,000961538. **Solo endurece.**

**Techo**, con los dos invariantes de §3.4:

- Tolerancia relativa 50/41: ⌊69 × 50/41⌋ = ⌊84,15⌋ = **84**.
- La cota máxima tolerada no empeora (5/82 = 0,060976). La cota es cota(n) = 1/20 + (n − 69) × 23/32760:
  - con 84 cortes: 0,060531 ≤ 0,060976. **Cumple.**
  - con 85 cortes: 0,061233. No cumple.

**Techo = 84, sin cambios.** Los dos invariantes vuelven a coincidir.

**Precio** (victorias pareadas necesarias, test de signo unilateral):

| n | α = 0,000725 (0,05/69) | α = 0,000702 (enmienda) |
|---:|---:|---:|
| 300 | 179 (59,7 %) | 179 (59,7 %) |
| 500 | 287 (57,4 %) | 287 (57,4 %) |
| 1000 | 551 (55,1 %) | 551 (55,1 %) |

Entre n = 300 y n = 2000, el umbral sube una victoria en 260 de los 1701 valores de n. Por ejemplo, con n = 309 pasa de 183 a 184, y con n = 333 de 196 a 197. En los demás valores no cambia.

Las predicciones de §5 del 2026-11-02 para `nhl|spreads` y `nhl|totals` siguen igual, porque el listón a n = 300 sigue en 179.

## 4. Decisión

1. **α_corte = (0,05 − Σ α consumido) / (K − tests consumidos) = 23/32760 = 0,000702**, para todo test de entrada hecho desde el commit de esta enmienda.
   - Es una constante **derivada en el código** a partir de sus factores: 0,05, 6 tests, K_heredado = 52 y K = 69. No se escribe a mano.
   - **No se recalcula sola** cuando se gasta otro test: cada test futuro ya tiene su parte del presupuesto.
2. **La cota publicada (`fwer_bound`) es la suma de los α realmente consumidos**, más α_corte por cada corte con el test pendiente. El α consumido de cada entrada del registro se obtiene así:
   - Si la entrada lo tiene guardado (`entry_test_alpha`), ese valor.
   - Si no lo tiene pero sí tiene `entry_test_at`, el α vigente en ese instante según los commits:
     - antes del 2026-09-05T01:23:46Z, o si el instante es ilegible: 0,05, el α previo a Bonferroni. Es una sobreestimación, pero queda visible en el log;
     - del 2026-09-05T01:23:46Z al 2026-09-25T10:37:13Z: 0,05/41;
     - del 2026-09-25T10:37:13Z al 2026-11-02T15:13:22Z: 0,05/52;
     - desde el 2026-11-02T15:13:22Z: 0,05/69, el mayor de los dos α posteriores.
   - Además, el α de los tests ya devueltos por una liberación (`alpha_gastado_previo`).

   La inferencia se usa una sola vez: la primera escritura tras el commit guarda `entry_test_alpha` en cada entrada consumida.
3. **Liberar no borra el α gastado.** Antes de anular `entry_test_at`, `release_prediction_gate_latch` traslada el α del test devuelto a `alpha_gastado_previo`. Un nuevo test tras liberar cuenta como un test más de la familia.
4. **Franjas del candado** (siguen siendo solo log, AUD-009):
   - sin aviso: mientras n ≤ 69 y la cota ≤ 0,05;
   - INFO: si n > 69 o la cota > 0,05;
   - ERROR y re-pre-registro: si n > 84 **o** la cota > 5/82 = 0,060976. La segunda condición cubre las liberaciones: con 84 cortes, una sola liberación con su nuevo test da 0,061233.
5. **Regla de contabilidad para futuros re-pre-registros:** α_corte = (0,05 − Σ α consumido) / (K − tests consumidos), y el techo se verifica con la cota mixta. La regla se aplica al redactar cada re-pre-registro, nunca automáticamente.

## 5. Por qué no es la re-división prohibida (§3.2 b del 2026-09-04; §6 del 2026-11-02)

Lo prohibido es repartir 0,05 entre los supervivientes **como si los seis tests no se hubieran hecho**: 0,05/63 = 0,000794. Eso relaja el umbral precisamente porque esos seis salieron rechazados. Aquí ocurre lo contrario:

- A los seis tests se les cobra su α **real**, sin rebaja.
- El resultado no depende de sus p-valores. El cálculo sería idéntico si los seis hubieran pasado: gastar α no depende de pasar.
- El umbral baja, de 0,000725 a 0,000702.
- Los seis siguen contando en K = 69 y en el registro, como exige §3.2 b.

Conocer los p intermedios de los cortes no elegibles no da ventaja, por los dos motivos de §3.2 c del 2026-11-02: el cambio solo endurece, y sus factores son recuentos y fechas de diseño, no resultados.

## 6. Qué no cambia

- K = 69 (los 68 cortes del 2026-11-02 más `mlb|team_totals`) y el techo de 84.
- El α de familia 0,05, que esta enmienda **restaura**.
- `n ≥ 300`, la definición de `d`, `model_probability`, la exclusión de empates, la condición 2 (EV > 0) y la ventana desde el 2026-08-16.
- Un solo test de entrada por corte, la salida diaria y el pestillo.
- **Las seis decisiones ya tomadas** (`agotado_test_unico`): no se recalculan. Solo cambia cómo se contabiliza su α.
- Los cortes que entran por calendario siguen dentro de la tolerancia. El registro tenía 74 el 2026-11-03: 68 vivos y 6 agotados, con tenis nuevo. Cota real a 74 cortes: 1/20 + 5 × 23/32760 = 0,053510.
- AUD-009: el candado sigue siendo un mensaje de log, no una decisión.

## 7. Implementación

En `src/sqp/risk/prediction_gate.py`:

- Constantes nuevas: `PREDICTION_GATE_K_HEREDADO = 52`, `PREDICTION_GATE_TESTS_HEREDADOS = 6`, `PREDICTION_GATE_ALPHA_HEREDADO` y `PREDICTION_GATE_FWER_MAX_TOLERADA = 50·0,05/41`.
- `PREDICTION_GATE_ALPHA` pasa a derivarse según §3.
- Tres funciones: `alpha_del_test`, `fwer_bound` (cota de diseño) y `fwer_bound_registro` (cota del registro).
- Dos campos nuevos en cada entrada: `entry_test_alpha` y `alpha_gastado_previo`.
- La liberación conserva el α gastado.
- Las franjas de §4.4.

Tests en `tests/test_prediction_gate.py`: migración de un registro con los seis tests a K = 52, fronteras 69/84/85 y liberación seguida de un nuevo test.

Referencias operativas que pasan a citar `0,000702`: `configs/default.yaml`, `scripts/gate_status.py` y `.claude/skills/clv-shadow-exit/SKILL.md`.

**Plazo:** debe estar en `main` antes del primer run en que `nhl|spreads` o `nhl|totals` (n = 224 el 2026-11-03) lleguen a n ≥ 300. Si un test se ejecutara antes del commit, se habría hecho a 0,05/69, más laxo que lo aquí registrado. En ese caso:

- se registra como incidente;
- su α (0,05/69) se contabiliza por la regla de §4.2;
- la decisión no se usa para abrir la puerta.

## 8. Decisión del operador

- **Base de la orden.** El 2026-11-03 se presentó al operador (Carlos) la propuesta de corregir KI-078, con las opciones A y B. Su respuesta textual fue: **«Sí, házlo»**.
- [x] Corregir KI-078: la cota cuenta el α realmente consumido y la liberación conserva el α gastado.
- [x] Opción B, α_corte = 23/32760 = 0,000702. Es una decisión de diseño tomada bajo esa orden: de las dos opciones, es la única que restaura el α de familia 0,05 sin relajar nada.
- [x] Techo de 84, re-verificado con la cota mixta (0,060531 ≤ 0,060976). No cambia respecto del 2026-11-02, cuya confirmación expresa sigue pendiente y no es bloqueante.
