# Re-pre-registro: el prediction gate pasa a K = 52

**Fecha:** 2026-09-25.
**Estado:** **VIGENTE.** Ordenado por el operador el 2026-09-25 («Re-pre-registra el gate para K=52») e implementado el mismo día en `src/sqp/risk/prediction_gate.py`.
**Modifica:** `docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md`, §3.1 (el valor de K y el techo de re-pre-registro). El resto de ese documento sigue vigente sin cambios.

---

## 1. Por qué

El pre-registro del 2026-09-04 fijó K = 41 y dejó escrita la regla para cuando el universo creciera (§3.1):

> «si el número de cortes evaluados supera **50** (un 22 % sobre 41), este criterio se **re-pre-registra antes** de que ningún corte nuevo sea elegible. No se re-divide α sobre la marcha».

El registro de producción evalúa ahora **52 cortes**. Desde la verificación de la ronda `audit-2026-09-22-r2`, el run diario emite el ERROR «RE-PRE-REGISTRAR». Con K = 41 y 52 cortes, la cota real del error de familia es 52 × 0,05/41 = **0,0634**, un 27 % por encima del 0,05 declarado.

## 2. Estado medido antes de fijar nada

Fuente: `data/bets/prediction_gate.json`, generado el 2026-09-24T15:01Z. Leído sin escribir nada.

```
52 cortes evaluados · los 52 en muestra_insuficiente · 0 permitidos
ningún corte con n >= 300 · ningún test de entrada gastado (entry_test_at vacío en todos)
```

| corte | n | p (test de signo) | ev_flat |
|---|---:|---:|---:|
| `mlb\|h2h` | 293 | 0,9999 | −0,0312 |
| `mlb\|spreads` | 293 | 0,5000 | −0,0493 |
| `mlb\|totals` | 287 | 0,2775 | −0,0503 |
| siguiente (`ncaaf\|*`) | ≤ 151 | — | — |

**Ningún corte es elegible todavía**, así que la condición de §3.1 («antes de que ningún corte nuevo sea elegible») se cumple. Pero el margen es de días: los tres cortes de MLB pueden alcanzar n = 300 en el run del 2026-09-25 o en el siguiente. Por eso este documento se escribe y se implementa antes del run de las 12:00.

## 3. Criterio re-pre-registrado

### 3.1 Bonferroni sobre K = 52

```
α_corte = 0,05 / K        con K = 52 fijado hoy
α_corte = 0,000962
```

- **K = 52 no es espiar los datos**, por la misma razón que K = 41 no lo era: es el número de cortes que evalúa el pipeline, un hecho de diseño. Los 52 están en `muestra_insuficiente`, así que el cambio no favorece ni perjudica a ninguno en concreto.
- **Solo endurece.** α baja de 0,00122 a 0,000962. Ningún corte que el criterio anterior rechazaba pasa a aceptarse.

### 3.2 Techo para el próximo re-pre-registro: 63 cortes

Se aplica la misma tolerancia relativa que fijó el pre-registro del 2026-09-04: 50/41, es decir, +22 % sobre K. Con K = 52, el techo es ⌊52 × 50/41⌋ = **63**.

- Así la cota máxima tolerada del error de familia se mantiene prácticamente igual: 63 × 0,05/52 = 0,0606, frente a 50 × 0,05/41 = 0,0610 hasta hoy.
- Entre 53 y 63 cortes se informa la cota real (INFO) y el criterio se aplica tal cual.
- Por encima de 63, ERROR y re-pre-registro antes de que ningún corte nuevo sea elegible. Es la misma regla, con los números nuevos.

### 3.3 Lo que NO cambia

- α de familia 0,05.
- `n ≥ 300` no empatadas.
- La definición de `d`, el modelo puro y la exclusión de empates.
- La condición 2 (`EV > 0`).
- La ventana fuera de muestra desde el 2026-08-16.
- **Un solo test de entrada por corte** (§3.2 del pre-registro del 2026-09-04).
- La salida diaria y el pestillo.

## 4. El precio

Victorias pareadas necesarias con el test de signo unilateral:

| n | α = 0,00122 (K = 41) | α = 0,000962 (K = 52) |
|---:|---:|---:|
| 300 | 177 (59,0 %) | 178 (**59,3 %**) |
| 500 | 285 (57,0 %) | 286 (57,2 %) |
| 1000 | 549 (54,9 %) | 550 (55,0 %) |

Una victoria más a cualquier n. El precio es pequeño porque Bonferroni escala con 1/K y el cambio de K es de 41 a 52.

## 5. Predicción registrada

Este documento no cambia la predicción del pre-registro del 2026-09-04 (§6 y §9), que sigue en vigor con sus propias palabras: `mlb|totals`, `mlb|spreads` y `mlb|h2h` «fallarán la condición 2 (EV > 0) antes incluso de llegar al test de signo». Hoy sus `ev_flat` siguen siendo negativos (−0,0503, −0,0493 y −0,0312). Dos precisiones que no la modifican:

- **Fecha.** Aquel documento esperaba que MLB alcanzara n = 300 hacia el 2026-09-20. No se cumplió: hoy están en n = 287–293.
- **Cómo se verá en el registro.** `_decide` evalúa el test de signo ANTES que el EV. Con p entre 0,28 y 0,9999, el `reason` que anote el gate será `no_bate_al_mercado`, no `ev_no_positivo`. Fallar la condición 2 se comprobará leyendo `ev_flat < 0` en la entrada del registro, no en `reason`.

Si alguno pasara, habrá superado un listón del 59,3 % a n = 300.

## 6. Decisión del operador

- [x] **ORDENADO** el 2026-09-25: K = 52.
- [x] **Techo de 63 cortes: CONFIRMADO por el operador el 2026-09-25** («Confirmo el techo de 63»). Es un valor derivado. El pre-registro del 2026-09-04 fija qué pasa por encima de 50, pero no cómo se calcula el techo en un re-pre-registro futuro. El 63 sale de mantener los dos invariantes de aquella aprobación: la misma tolerancia relativa (50/41, +22 %) y una cota tolerada que no empeora (0,0606 ≤ 0,0610; con 64 cortes serían 0,0615). Es el máximo que no relaja lo aprobado.

Implementado el mismo día:

| Regla | Dónde |
|---|---|
| `α_corte = 0,05/52`, derivado y no escrito a mano | `PREDICTION_GATE_K = 52` |
| Techo de 63 cortes | `PREDICTION_GATE_K_REPREGISTRO = 63` |
| Umbral citado en la documentación operativa | `configs/default.yaml`, `scripts/gate_status.py` y `.claude/skills/clv-shadow-exit/SKILL.md` (lo fija `test_ningun_documento_presenta_el_alpha_de_familia_como_umbral_por_mercado`) |

## Addendum 2026-09-26 — cambio de régimen del modelo MLB (antes de ejecutar)

Desde el run del 2026-09-26, MLB sirve con `pitcher_bound: 0.05` (commit `49a6181`, orden del operador); hasta el 25/09 era 0.0. Las filas MLB servidas desde el 26/09 salen de ese modelo. Se registra **antes** de mirar ningún resultado del test. **No altera ningún criterio de este documento** y queda prohibido usarlo después para recortar o re-segmentar la ventana: el test evalúa el sistema tal como operó. Revisión independiente (Fable, 2026-09-26): no invalida el test; en `mlb|totals`, como mucho ~13 de 300 filas vendrán del modelo nuevo.

## Addendum 2026-09-26 (2) — descanso NBA activado (antes de ejecutar)

Desde el commit que activa `nba.rest_points_per_day: 0.795` (2026-09-26), el modelo NBA suma 0,795 puntos por día de diferencia de descanso (tope de 4) al margen esperado. Hasta entonces era 0. Pre-registro y resultado: `docs/research/2026-09-26-preregistro-descanso-basket.md` y `docs/research/2026-09-26-resultado-descanso-basket.md` (ACEPTA, dictamen de Fable: APTO CON CONDICIONES). Las filas NBA servidas desde ese commit salen de este modelo; hoy el gate no tiene cortes NBA y la temporada empieza a finales de octubre. Se registra **antes** de mirar ningún resultado del test. **No altera ningún criterio**, y queda prohibido usarlo después para recortar o re-segmentar la ventana.
