# 03 — Corrección y lógica de negocio

Base: commit `7871bdb`. **No se modificó código de aplicación.**

Flujo trazado extremo a extremo: cuotas → consenso → no-vig → probabilidad de
decisión → edge → Kelly → capas de stake 0 → persistencia → liquidación →
ROI realizado.

---

### [COR-01] Una línea `NaN` en totals fabrica el resultado: Under siempre gana, Over siempre pierde

- **Severity:** High
- **Confidence:** Confirmed (comportamiento verificado por ejecución) · **reachability: Requires verification**
- **Category:** Corrección / liquidación / integridad de etiquetas
- **Location:** `src/sqp/settlement/settle.py:42-44` (`_grade`, rama `totals`)
- **Evidence:** Ejecutado contra el código actual con marcador home 5 – away 4
  (total 9):

  | Caso | Resultado devuelto |
  |---|---|
  | `market=totals, selection=Under, line=NaN` | **`win`** |
  | `market=totals, selection=Over, line=NaN` | **`loss`** |
  | `market=totals, selection=Under, line=8.5` (control) | `loss` (correcto) |

  Mecánica: `total == line` es `False` con `NaN`, así que no se grada `push`;
  después `(total > line)` es `False`, y `False == (sel == "Over")` es `True`
  cuando la selección es `Under`. El resultado **no depende del marcador**.
- **Impact:** Contamina simultáneamente las tres métricas rectoras: ROI
  realizado (`settle.py:60-61` calcula `pnl` a partir de `result`), las
  etiquetas de entrenamiento del calibrador
  (`calibration/data.py:110` entrena sobre `settled_*.csv`) y el hit rate por
  segmento. Un `win` fabricado es peor que una fila perdida: entra en los
  agregados como evidencia válida.
- **Failure scenario:** Un snapshot con `point` vacío en totals produce filas de
  Under graduadas como ganadoras con independencia del partido. El ROI de totals
  sube, el calibrador aprende que sus probabilidades de Under eran acertadas, y
  el monitor de degradación (`risk/degradation.py:81`) deja de pausar el mercado
  justo cuando debería.
- **Recommendation:** `_grade` debe devolver `void` cuando `line` no es finita en
  `spreads`/`totals`, en vez de caer por las comparaciones. **No** convertirlo en
  `push` sin decidirlo: `push` devuelve el stake y afirma que la apuesta existió;
  `void` afirma que no se pudo graduar, que es lo cierto.
- **Suggested validation:** Antes de tocar código, medir la exposición real:
  contar filas de `spreads`/`totals` con `line` no finita en
  `data/bets/settled_*.csv` (requiere autorización para leer `data/`). Si el
  conteo es 0, el defecto es latente y la corrección es preventiva; si no lo es,
  hay que re-liquidar y republicar las métricas afectadas.
- **Estimated remediation scope:** Small (el fix), Medium (si hay que re-liquidar)

---

### [COR-02] Una línea `NaN` en spreads se grada siempre como pérdida

- **Severity:** High
- **Confidence:** Confirmed (comportamiento verificado por ejecución) · **reachability: Requires verification**
- **Category:** Corrección / liquidación
- **Location:** `src/sqp/settlement/settle.py:39-41` (`_grade`, rama `spreads`)
- **Evidence:** Misma corrida: `market=spreads, selection=A, line=NaN` → `loss`.
  `adj = margin + line` es `NaN`; `adj > 0` y `adj == 0` son ambos `False`, así
  que el `else` devuelve `loss` incondicionalmente.
- **Impact:** Sesgo unidireccional: al contrario de [COR-01], aquí el error
  siempre perjudica al sistema. Deprime el ROI de spreads y enseña al calibrador
  que sus probabilidades de cobertura eran demasiado altas.
- **Failure scenario:** El monitor de degradación pausa `spreads` por ROI bajo
  (`roi_pause: -0.15`, `configs/default.yaml:131`) por un artefacto de
  liquidación, retirando un mercado sano de la evidencia.
- **Recommendation:** Igual que [COR-01]: `void` explícito. Ambas ramas comparten
  el mismo guard, así que es una sola corrección.
- **Suggested validation:** Test parametrizado sobre `_grade` con `line` en
  `{NaN, inf, -inf}` para `spreads` y `totals`.
- **Estimated remediation scope:** Small

---

### [COR-03] `books_count` cuenta líneas que el consenso descartó

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Corrección / consistencia interna
- **Location:** `src/sqp/pipeline/probabilities.py:37-43` (`_consensus_counts`)
  frente a `:17-34` (`_consensus_lines`); consumido en
  `src/sqp/pipeline/daily.py:586,635,662,722`
- **Evidence:** `_consensus_lines` salta las líneas con
  `price_decimal is None or <= 1.0` (`:27-28`). `_consensus_counts` recorre
  `eo.lines` **sin ningún filtro** (`:41-42`). El mismo evento produce, para la
  misma clave, un precio calculado sobre *k* casas y un conteo sobre *k + d*.
- **Impact:** Dos efectos, ambos en la dirección insegura:
  1. `low_book_penalty` (`configs/default.yaml:29`) deja de aplicarse cuando el
     conteo inflado alcanza `min_books_for_consensus: 2` — un mercado con una
     sola casa utilizable y una degenerada pasa como mercado con dos casas.
  2. `books_count` se persiste en el served stream (`daily.py:662`) y en el
     candidato (`:722`), así que cualquier análisis posterior por profundidad de
     mercado usa un denominador equivocado.
- **Failure scenario:** Un mercado fino con una cuota corrupta pierde su
  penalización por poca profundidad y produce un stake mayor del debido.
- **Recommendation:** `_consensus_counts` debe aplicar el mismo predicado que
  `_consensus_lines`. Ver [ARCH-02]: lo correcto es un predicado compartido, no
  copiar el `if`.
- **Suggested validation:** Test con un `EventOdds` que mezcle una línea válida y
  una con `price_decimal = 1.0`, afirmando `books_count == 1`.
- **Estimated remediation scope:** Small

---

### [COR-04] El lock puede entrar en bucle infinito sin dormir si `stat()` falla de forma persistente

- **Severity:** Medium
- **Confidence:** Confirmed (por lectura; no reproducido)
- **Category:** Concurrencia / disponibilidad
- **Location:** `src/sqp/storage/lock.py:41-52` (`locked`)
- **Evidence:**
  ```python
  except FileExistsError:
      try:
          if time.time() - lock.stat().st_mtime > stale_s:
              lock.unlink(missing_ok=True)
              continue
      except OSError:
          continue            # <-- salta el deadline Y el sleep
      if time.monotonic() >= deadline:
          ... break
      time.sleep(0.25)
  ```
  El `continue` de la línea 47 salta tanto la comprobación de `deadline`
  (`:48`) como `time.sleep(0.25)` (`:52`). Si `lock.stat()` falla de forma
  **persistente** (permisos, disco, ruta en un recurso de red caído), el bucle
  gira sin pausa y sin salida: `os.open` → `FileExistsError` → `stat` falla →
  `continue` → repetir.
- **Impact:** El comentario justifica el `continue` para el caso transitorio
  ("el otro proceso lo libero entre exists y stat"), que es correcto. Lo que no
  cubre es el caso persistente. `locked` envuelve `_finalize`
  (`daily.py:358`) y `apply_global_exposure_cap` (`daily.py:263`): un bucle
  infinito ahí cuelga el run diario **consumiendo CPU al 100%**, y `timeout_s`
  no lo rescata porque nunca se evalúa.
- **Failure scenario:** El run de las 11:00 no termina, `CAPTURE_CLOSE.bat` se
  acumula cada hora sobre un lock que nadie libera, y la liquidación del día
  siguiente aborta.
- **Recommendation:** Comprobar el deadline **antes** del `continue`, y dormir en
  esa rama igual que en la normal. Es una reordenación de tres líneas.
- **Suggested validation:** Test con `Path.stat` parcheado para lanzar `OSError`
  siempre, afirmando que `locked` retorna (degradado) en ≤ `timeout_s`. Hoy ese
  test colgaría — lo cual es exactamente la demostración.
- **Estimated remediation scope:** Small

---

### [COR-05] Cualquier advertencia de fiabilidad elimina el evento entero del stream de calibración

- **Severity:** Medium
- **Confidence:** Requires verification
- **Category:** Corrección / sesgo de selección
- **Location:** `src/sqp/pipeline/daily.py:581-584` y `:616`
- **Evidence:** `warn = adapter.reliability_warning(eo.event)` (`:581`); si el
  evento ya empezó se le concatena un mensaje (`:582-584`). Después, en el bucle
  de mercados: `if price is None or p_model is None or warn: continue` (`:616`).
  `warn` es una cadena, así que **cualquier** advertencia no vacía salta el
  `continue` y el evento no produce ni candidatos **ni filas del served stream**
  (`:650-664`, que está después del `continue`).
- **Impact:** El served stream existe precisamente para entrenar el calibrador
  sobre la distribución completa servida y evitar el sesgo de selección
  (`daily.py:646-649`). Excluir los eventos con advertencia reintroduce un sesgo
  de selección por la puerta de atrás: el calibrador se entrena solo sobre los
  eventos que el modelo consideraba fiables.
- **Failure scenario:** En una liga con pocos resultados acumulados, la mayoría
  de eventos llevan advertencia; el calibrador se entrena sobre la minoría no
  advertida y su ECE fuera de muestra no describe la población servida.
- **Recommendation:** Decidir explícitamente si la exclusión debe aplicarse al
  *staking* (razonable) o también al *registro* (cuestionable). No cambiar nada
  antes de medir.
- **Suggested validation:** Leer `sports/adapters.py` y `sports/base.py` para
  enumerar cuándo `reliability_warning` devuelve no vacío, y contar en un run
  real qué fracción de eventos queda fuera del served stream por esta vía. **Sin
  esa medición no se puede afirmar que el sesgo sea material.**
- **Estimated remediation scope:** Small (el cambio), Medium (la medición previa)

---

### [COR-06] `remove_vig_power` solo captura `ValueError` de `brentq`

- **Severity:** Low
- **Confidence:** Requires verification
- **Category:** Manejo de errores
- **Location:** `src/sqp/markets/vig.py:36-42`
- **Evidence:** `try: k = brentq(f, 0.5, 5.0) except ValueError:`. `brentq`
  señala con `ValueError` el caso de bracket con signos iguales, pero puede
  elevar `RuntimeError` por no convergencia dentro de `maxiter`. Esa rama no
  está cubierta y propagaría.
- **Impact:** Una excepción no capturada en el camino del no-vig aborta
  `run_league` para la liga entera, en vez de degradar al método proporcional
  como hace el resto de la función.
- **Failure scenario:** Un mercado patológico interrumpe el run de una liga; bajo
  shadow el coste es un día de evidencia, no dinero.
- **Recommendation:** Ampliar a `except (ValueError, RuntimeError)`. Antes,
  confirmar contra la versión de SciPy pineada en `requirements.lock` que
  `RuntimeError` es alcanzable con `full_output=False`.
- **Suggested validation:** Revisar la firma de `scipy.optimize.brentq` en la
  versión instalada y, si es alcanzable, un test con una función sin raíz en
  `[0.5, 5.0]` que además no dispare el guard de la línea 28.
- **Estimated remediation scope:** Small

---

### [COR-07] `atomic_write_csv` no sincroniza a disco antes del `replace`

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Integridad de datos
- **Location:** `src/sqp/storage/atomic.py:16-22`
- **Evidence:** `df.to_csv(tmp)` seguido de `os.replace(tmp, out)` sin
  `flush()`/`os.fsync()` sobre el descriptor del temporal.
- **Impact:** `os.replace` es atómico respecto a *otros procesos*, que es lo que
  el docstring promete y lo que cubre el caso de uso declarado. No es atómico
  frente a un corte de energía: el rename puede persistir antes que los datos,
  dejando un archivo válido para el sistema y vacío o truncado en contenido.
- **Failure scenario:** Corte eléctrico durante el run diario; al reiniciar,
  `results_*.csv` existe y es legible pero le faltan filas — y el docstring dice
  que estos archivos "se reconstruyen solo mediante re-fetches lentos".
- **Recommendation:** `fsync` del temporal antes de `os.replace`. Coste
  despreciable en estos volúmenes.
- **Suggested validation:** No hay test razonable de corte de energía; basta
  revisión del diff.
- **Estimated remediation scope:** Small

---

### [COR-08] La comprobación de temporada falla-abierto hacia el gasto de cuota

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Manejo de errores / coste
- **Location:** `src/sqp/pipeline/daily.py:513-517`
- **Evidence:** `except Exception as exc: active = True  # status check is
  best-effort`. Ante cualquier fallo de `/sports` se asume liga activa y se
  procede al fetch, que **sí** consume cuota.
- **Impact:** Un fallo del endpoint de estado convierte ligas fuera de temporada
  en llamadas pagadas. Está mitigado por el guard de presupuesto
  (`pipeline/budget.py:37`), que acota el daño pero no lo evita.
- **Failure scenario:** Una caída parcial del proveedor consume la cuota mensual
  en ligas sin eventos.
- **Recommendation:** Mantener el fail-open (bloquear el run sería peor) pero
  registrar el evento en `monitoring/run_status.py` para que sea visible en el
  dashboard, no solo en el log.
- **Estimated remediation scope:** Small
