# 07 — Rendimiento, concurrencia y fiabilidad

Base: commit `7871bdb`. **No se modificó código de aplicación.**
No se ejecutó perfilado en esta pasada; las cifras de tiempo proceden de la
corrida de la suite y de `audit/01-baseline-results.md`.

---

### [PRF-01] El lock se degrada a "sin lock" y continúa escribiendo

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Concurrencia / consistencia de estado
- **Location:** `src/sqp/storage/lock.py:48-51`; consumidores en
  `src/sqp/pipeline/daily.py:263` (`apply_global_exposure_cap`) y `:358`
  (`_finalize`)
- **Evidence:** Al agotarse `LOCK_TIMEOUT_S = 30.0` (`lock.py:21`) el
  contextmanager registra un warning y hace `break` **sin adquirir el lock**,
  cediendo el control al bloque protegido igualmente (`:49-51`). La decisión está
  documentada: *"bloquear el pipeline diario seria peor que el riesgo de
  intercalado que este lock mitiga"* (`:32-33`).
- **Impact:** Es un intercambio deliberado y defendible, pero deja abierta
  exactamente la condición que el lock existe para evitar: el run diario y la
  revalidación horaria haciendo read-modify-write simultáneo sobre
  `candidates_*.csv`. El resultado sería una revocación perdida (`stake` que
  vuelve a ser positivo) o unos candidatos recién generados sobrescritos.
- **Failure scenario:** El run de las 11:00 tarda más de 30 s en el cap global
  mientras `CAPTURE_CLOSE` revalida; una revocación por `stale_edge_revoked` se
  pierde y el pick queda staked pese a haber perdido su edge. Bajo `shadow_mode`
  el stake es 0 y el coste es evidencia corrupta, no dinero.
- **Recommendation:** Registrar la degradación en `monitoring/run_status.py`
  —no solo en el log— para que sea visible en el dashboard. La alternativa
  (bloquear) sigue siendo peor; lo que falta es que el operador sepa que ocurrió.
- **Suggested validation:** Test que fuerce el timeout y afirme que el estado
  degradado queda registrado en un artefacto, no solo emitido por logger.
- **Estimated remediation scope:** Small

---

### [PRF-02] Bucle de adquisición sin pausa ante fallo persistente de `stat()`

- **Severity:** Medium
- **Confidence:** Confirmed (por lectura; no reproducido)
- **Category:** Disponibilidad
- **Location:** `src/sqp/storage/lock.py:41-52`
- **Evidence:** Detallado como [COR-04] en `03-correctness.md`: el `continue` de
  la línea 47 salta la comprobación de `deadline` (`:48`) y el `time.sleep(0.25)`
  (`:52`).
- **Impact:** Consumo de CPU al 100% y cuelgue indefinido del run diario, sin que
  `timeout_s` pueda rescatarlo.
- **Recommendation:** Ver [COR-04].
- **Estimated remediation scope:** Small

---

### [PRF-03] `load_closing_odds` carga todo el histórico de la liga por invocación

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Escalabilidad
- **Location:** `src/sqp/backtesting/roi_engine.py:63-66`
- **Evidence:** Ver [DAT-08] en `05-data-and-backtesting.md`. Abierto desde la
  auditoría 2026-07-12.
- **Impact:** Crece linealmente con el histórico capturado, que es el activo que
  el proyecto acumula deliberadamente. La restricción se hará vinculante justo
  cuando la muestra empiece a ser estadísticamente útil.
- **Recommendation:** Filtrar por rango de meses relevante.
- **Suggested validation:** Medir tiempo y memoria pico actuales como línea base
  antes de optimizar.
- **Estimated remediation scope:** Medium

---

### [PRF-04] Monte Carlo a 20.000 simulaciones por evento en el camino diario

- **Severity:** Informational
- **Confidence:** Requires verification
- **Category:** Rendimiento
- **Location:** `configs/default.yaml:43-45` (`n_sims: 20000`, `seed: 42`);
  `src/sqp/simulation/monte_carlo.py:11,32`
- **Evidence:** El parámetro está configurado a 20.000. **No verifiqué** si
  `run_league` invoca la simulación por evento o si esta solo se usa como
  cross-check de las fórmulas analíticas, que es lo que declara `README.md:41`
  (*"Monte Carlo (cross-check de las fórmulas analíticas)"*). En la lectura de
  `run_league` (`daily.py:476-740`) no aparece ninguna llamada a `simulate_*`.
- **Impact:** Si es solo cross-check, no hay impacto en el run diario. Se registra
  para cerrar la duda, no como defecto.
- **Recommendation:** Ninguna hasta confirmar el camino de invocación.
- **Suggested validation:** `grep -rn "simulate_normal_game\|simulate_poisson_game" src/ scripts/`.
- **Estimated remediation scope:** —

---

### [PRF-05] La suite tarda 62–65 s y no hay medición de cobertura

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Fiabilidad del ciclo de desarrollo
- **Location:** `audit/01-baseline-results.md:41,47`; `.github/workflows/ci.yml:58-62`
- **Evidence:** 637 tests en 62–65 s (aceptable). Pero `pytest-cov` **no está
  instalado** en el entorno local (`01-baseline-results.md:47`) y en CI la
  cobertura corre **sin umbral**, declarada informativa (`ci.yml:58-62`).
- **Impact:** No existe hoy ninguna medición de cobertura disponible, ni local ni
  bloqueante. Las afirmaciones sobre qué está cubierto —incluidas las de este
  informe— se apoyan en análisis de imports, no en líneas ejecutadas. Ver
  [TST-01].
- **Recommendation:** Instalar `pytest-cov` en el entorno local. Sobre el umbral
  en CI, decidir explícitamente: un umbral bajo pero real vale más que ninguno.
- **Estimated remediation scope:** Small

---

### [PRF-06] La orquestación diaria tiene un punto de fallo total documentado

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Fiabilidad operativa
- **Location:** `DIARIO_COMPLETO.bat` (cabecera); `scripts/settle_all.py`;
  `src/sqp/pipeline/cleanup.py:103` (`unsettled_completed_picks`)
- **Evidence:** `DIARIO_COMPLETO.bat` aborta el run si la liquidación falla, por
  diseño: *"Si la liquidacion falla, ABORTA antes del run para no perder picks"*.
  El alcance del abort se acotó el 2026-08-04 (M-1 de `audit/latest/FINDINGS.md:63-76`)
  para que solo dispare cuando una liga fallida retenga picks comenzados sin
  liquidar. El respaldo es `_archive_existing` (`daily.py:307-334`).
- **Impact:** Riesgo residual bajo y bien razonado. Se documenta como control
  verificado: la cadena SETTLE → RUN, el guard por liga y el archivado previo a
  sobrescribir son tres capas coherentes.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [PRF-07] La caché de cuotas evita re-persistir snapshots — control verificado

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Caché / idempotencia
- **Location:** `src/sqp/pipeline/daily.py:561-567`;
  `src/sqp/providers/odds_cache.py:16` (`FileCache`)
- **Evidence:** `if events and not client.last_response_cached:` persiste el
  snapshot; en caso contrario registra que *"odds served from cache; snapshot
  already persisted on the originating fetch, not re-appending"*. El served
  stream se deduplica por `(evento, mercado, selección, línea, DÍA del run)`
  (`daily.py:574-577`), lo que hace idempotente re-ejecutar el mismo día.
- **Impact:** Ninguno pendiente. La idempotencia del run diario está bien
  resuelta.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —
