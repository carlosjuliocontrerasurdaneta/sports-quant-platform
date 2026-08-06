# 08 — Calidad de tests y cobertura ausente

Base: commit `7871bdb`. **No se modificó código de aplicación.**
Estado verificado: **637 tests, 0 fallos, 0 saltados** en 62–65 s
(`audit/01-baseline-results.md:41`); 81 archivos de test, 8.800 líneas.

El criterio de este informe no es "cuánta cobertura hay" sino **si los tests
cubren los riesgos de producción reales**. La respuesta corta: cubren muy bien
las regresiones ya vividas y muy mal los estados degradados que nadie ha vivido
todavía.

---

### [TST-01] La prueba que protege el shadow mode se auto-anula si el shadow mode se apaga

- **Severity:** High
- **Confidence:** Confirmed
- **Category:** Test que no puede fallar / control de seguridad
- **Location:** `tests/test_audit_2026_07_29.py:142-152`
  (`test_b08_production_yaml_shadow_survives_unrecognized_env`)
- **Evidence:**
  ```python
  cfg = load_yaml(CONFIG_DIR / "default.yaml")
  if not cfg.get("shadow_mode"):
      pytest.skip("default.yaml ya no declara shadow_mode: true")
  ```
  El propósito declarado del test es que *"un SHADOW_MODE vacio NO debe poder
  desactivar el shadow mode"* (`:143-144`). Pero su primera acción es **saltarse
  a sí mismo** si `configs/default.yaml` deja de declarar `shadow_mode: true`.
- **Impact:** El control está invertido. El escenario que más importa detectar
  —que alguien desactive el shadow mode— es exactamente el que hace que el test
  deje de ejercerse, y `pytest -q` lo reporta como suite verde. La suite actual
  informa **0 saltados**, lo que confirma que hoy `shadow_mode` sigue en `true`;
  el día que cambie, nadie se enterará por aquí.
- **Failure scenario:** Una edición de `default.yaml` desactiva el shadow mode
  como efecto colateral. Los 637 tests siguen verdes, el test que existe para
  impedirlo se salta en silencio, y el sistema pasa a stake real sin decisión
  humana.
- **Recommendation:** Invertir el guard: si `default.yaml` **no** declara
  `shadow_mode: true`, el test debe **fallar** con un mensaje explícito
  ("el shadow mode se desactivó; esto requiere decisión humana registrada"), no
  saltarse. Si se quiere permitir la desactivación deliberada, que sea un
  segundo test que exija la entrada correspondiente en el registro de decisiones.
- **Suggested validation:** Cambiar temporalmente `shadow_mode` a `false` en una
  copia y comprobar que la suite falla. Hoy pasaría.
- **Estimated remediation scope:** Small

---

### [TST-02] Ningún test cubre el grading con línea no finita — el defecto de [COR-01]/[COR-02]

- **Severity:** High
- **Confidence:** Confirmed
- **Category:** Cobertura ausente sobre riesgo confirmado
- **Location:** `tests/settlement/test_settle_grade.py` (7 tests)
- **Evidence:** El helper del propio archivo declara
  `def _row(market, selection, line=float("nan"))` (`:13`) — **la línea `NaN` es
  el valor por defecto del fixture**. Los cinco tests de `h2h` la usan
  (correctamente: `h2h` ignora `line`). El único test de `spreads` pasa una línea
  explícita (`line=-1.5`, `:43`). **No hay ningún test de `totals`** en el
  archivo, ni ninguno que ejercite `spreads`/`totals` con línea no finita.
- **Impact:** El riesgo confirmado por ejecución en `03-correctness.md` —Under
  siempre gana, Over siempre pierde, spread siempre pierde— vive en el hueco
  exacto que el fixture normaliza como valor por defecto. La suite verde no dice
  nada sobre él.
- **Failure scenario:** El defecto entra en producción indefinidamente porque los
  637 tests verdes se leen como cobertura del módulo de liquidación.
- **Recommendation:** Test parametrizado sobre `_grade` con
  `line ∈ {NaN, inf, -inf}` × `market ∈ {spreads, totals}` × selección de ambos
  lados. **Escribirlo antes de la corrección y verlo fallar**: hoy documenta el
  comportamiento defectuoso; después fija el correcto.
- **Estimated remediation scope:** Small

---

### [TST-03] No existe medición de cobertura disponible ni bloqueante

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Instrumentación de pruebas
- **Location:** `audit/01-baseline-results.md:47`; `.github/workflows/ci.yml:58-62`
- **Evidence:** Localmente `pytest-cov` **no está instalado**, así que el comando
  de cobertura falla (`--cov` no reconocido). En CI la cobertura corre en una
  sola pata de la matriz, declarada explícitamente *"informational"* y **sin
  umbral** (`ci.yml:58-62`).
- **Impact:** Ninguna afirmación sobre cobertura del proyecto —incluidas las de
  este informe— se apoya hoy en líneas ejecutadas. Lo mejor disponible es el
  análisis de imports de [TST-04], que es un proxy débil.
- **Recommendation:** Instalar `pytest-cov` en el entorno local y añadirlo a las
  dependencias `dev` de `pyproject.toml:20`. Sobre el umbral en CI: decidirlo
  explícitamente. Un umbral bajo pero real detecta caídas; ninguno no detecta
  nada.
- **Suggested validation:** `pip install pytest-cov` y una corrida de línea base
  por módulo.
- **Estimated remediation scope:** Small

---

### [TST-04] Seis módulos sin import directo en ningún test, dos de ellos de infraestructura crítica

- **Severity:** Medium
- **Confidence:** High confidence (por análisis de imports, no de líneas)
- **Category:** Cobertura ausente
- **Location:** Medido sobre `src/sqp/**/*.py` (72 módulos) y `tests/**/test_*.py`:

  | LOC | Módulo | Comentario |
  |---|---|---|
  | 58 | `sqp.storage.lock` | Único mecanismo de concurrencia; sede de [COR-04] y [PRF-01] |
  | 54 | `sqp.sports.base` | Clase base abstracta, ejercida vía adaptadores |
  | 43 | `sqp.models.ml_predict` | Ruta ML, no en producción |
  | 37 | `sqp.providers.base` | Interfaces |
  | 22 | `sqp.storage.atomic` | `atomic_write_csv`, usado en todo el pipeline |
  | 19 | `sqp.logging_config` | — |
- **Evidence:** Ninguno de los seis nombres de módulo aparece en el texto de
  ningún archivo `tests/**/test_*.py`.
- **Impact:** "No importado" **no es** "no ejercitado": `locked` y
  `atomic_write_csv` se ejecutan indirectamente desde `daily.py`, que sí está
  cubierto. Lo que falta es cobertura **dirigida** de sus rutas degradadas —
  timeout de lock, lock huérfano, `stat()` fallando, `to_csv` a mitad—, que son
  precisamente las que [COR-04] y [PRF-01] señalan como defectuosas. Que el
  defecto del bucle infinito lleve ahí desde el 2026-07-24 sin detectarse es la
  consecuencia observable.
- **Failure scenario:** Una corrección en `lock.py` rompe el camino feliz y solo
  se descubre en producción, porque ningún test apunta al módulo.
- **Recommendation:** Tests dirigidos a `storage/lock.py` (los tres caminos:
  adquisición, lock huérfano, timeout) y a `storage/atomic.py` (fallo a mitad de
  escritura). Los otros cuatro módulos no lo justifican.
- **Suggested validation:** Confirmar por líneas, no por imports, en cuanto
  [TST-03] esté resuelto.
- **Estimated remediation scope:** Small

---

### [TST-05] No hay tests de propiedad sobre las funciones puras de mercado y riesgo

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Estrategia de pruebas
- **Location:** `tests/test_kelly.py` (6 tests), `tests/test_vig.py` (5),
  `tests/test_edge.py` (6); `hypothesis` no aparece en ningún test ni en
  `pyproject.toml:20`
- **Evidence:** Los módulos `markets/odds.py`, `markets/vig.py`,
  `markets/edge.py` y `risk/kelly.py` suman ~150 líneas de funciones **puras y
  sin E/S** —los candidatos de libro para pruebas basadas en propiedades— y se
  verifican con 17 tests de ejemplo.
- **Impact:** Las invariantes que de verdad importan no están fijadas por ningún
  test: que `remove_vig_*` devuelva probabilidades que sumen 1 y estén en (0,1);
  que `kelly_fraction_stake` **nunca** devuelva stake > `max_stake_pct · bankroll`
  ni negativo, para ningún input; que `adjusted_edge` nunca aumente el edge. Los
  hallazgos [QNT-03] (`NaN` atravesando dos guards) y [QNT-01] (penalización
  efectiva a la mitad) habrían caído en la primera ejecución de un test de
  propiedad.
- **Failure scenario:** Un refactor de las capas de riesgo pasa los 17 tests de
  ejemplo y rompe una invariante que nadie escribió.
- **Recommendation:** Añadir `hypothesis` a `dev` y escribir cuatro o cinco
  propiedades sobre esos módulos. Es la intervención de mayor rendimiento por
  esfuerzo de todo este informe.
- **Suggested validation:** Ejecutar las propiedades contra el código **actual**:
  se espera que al menos las de `NaN` fallen de inmediato, lo que confirmaría
  [QNT-03] por una segunda vía independiente.
- **Estimated remediation scope:** Medium

---

### [TST-06] La suite está fuertemente orientada a regresiones históricas

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Estrategia de pruebas
- **Location:** `tests/test_audit_2026_07_29.py` (256 líneas),
  `tests/test_breakeven.py`, `tests/test_clv.py` (248), `tests/test_intraday_gate.py`,
  `tests/settlement/test_settle_history_fallback.py` (253)
- **Evidence:** Múltiples archivos y tests están nombrados por el hallazgo de
  auditoría que los motivó (`test_b08_...`, `test_q01_...`, `test_audit_2026_07_29`).
  Los docstrings citan la fecha y el identificador del incidente.
- **Impact:** Es una **fortaleza**, no un defecto: cada defecto vivido tiene su
  prueba de regresión con contexto, y eso explica por qué la suite ha crecido de
  424 a 637 tests en seis semanas sin volverse ruido. Se registra aquí para
  equilibrar el informe: el sesgo no es "malos tests", es "tests que miran hacia
  atrás". Los hallazgos [TST-02], [TST-04] y [TST-05] son todos del mismo tipo —
  estados degradados aún no vividos.
- **Recommendation:** Ninguna sobre lo existente. La inversión marginal debe ir a
  propiedades e invariantes, no a más ejemplos.
- **Estimated remediation scope:** —
