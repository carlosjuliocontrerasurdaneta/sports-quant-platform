# 09 — Operación, configuración y documentación

Base: commit `7871bdb`. **No se modificó código de aplicación.**

---

### [OPS-01] Se opera sobre una versión de Python que nadie prueba

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Riesgo de configuración / entorno
- **Location:** `.github/workflows/ci.yml:19-21` (matriz `["3.11","3.12","3.13"]`);
  `pyproject.toml:7` (`requires-python = ">=3.11"`); runtime local verificado:
  `python --version` → **Python 3.14.4**; intérprete de producción fijado en los
  `.bat` (`CAPTURE_CLOSE.bat`, `RUN_DIARIO_ALL.bat`, etc.:
  `SQP_PYTHON=...\Python314\python.exe`)
- **Evidence:** Los `.bat` que ejecutan el sistema en el Programador de tareas
  apuntan explícitamente a **Python 3.14**, y la suite local corre en 3.14.4. El
  CI valida 3.11, 3.12 y 3.13. **La versión con la que se opera no está en la
  matriz.** El propio comentario de `ci.yml:17-18` lo reconoce: *"3.13 added to
  narrow the gap with the dev runtime (3.14). Bump to 3.14 here once
  setup-python ships it stably."*
- **Impact:** Una regresión específica de 3.14 —cambio de comportamiento de
  `pandas`/`numpy` compilados para esa versión, o de la propia librería
  estándar— pasaría el CI y fallaría solo en producción. El proyecto ya sufrió un
  incidente de esta familia: `Makefile:1-3` documenta que *"un joblib/scikit-learn
  distinto puede des-serializar mal los artefactos .joblib"*.
- **Failure scenario:** Un `.joblib` de calibración escrito bajo 3.14 con una
  versión de `scikit-learn` resuelta localmente no se carga —o carga mal— en
  cualquier entorno validado. El CI no lo detecta porque nunca corre en 3.14.
- **Recommendation:** Añadir 3.14 a la matriz de CI (aunque sea en modo
  `continue-on-error` mientras `setup-python` lo estabiliza), **o** fijar el
  intérprete de producción a una versión de la matriz. La situación actual —
  operar fuera de la matriz sin ninguna de las dos— es la peor de las tres.
- **Suggested validation:** Correr la suite completa en 3.13 y en 3.14 y comparar.
  Hoy solo consta la de 3.14 (`audit/01-baseline-results.md:41`, local) y las de
  3.11/3.13 (CI).
- **Estimated remediation scope:** Small

---

### [OPS-02] La puerta agregada documentada no es ejecutable en el entorno de trabajo

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Documentación vs realidad operativa
- **Location:** `Makefile:15` (`check: lint types test`);
  `audit/01-baseline-results.md:50`
- **Evidence:** `Makefile` define `make check` como el comando único que aplica
  las tres puertas del CI en local. La verificación de línea base lo registra
  como **no ejecutado: "`make` executable unavailable"**. El entorno es Windows y
  no tiene `make`.
- **Impact:** El único atajo documentado para validar antes de committear no
  funciona en la máquina donde se desarrolla. En la práctica se ejecutan los tres
  comandos a mano, lo que invita a omitir alguno — y omitir `mypy` o `ruff` es
  exactamente cómo entran las regresiones que el CI luego rechaza.
- **Recommendation:** Añadir un equivalente ejecutable en Windows (un `.bat` o un
  script de PowerShell con los mismos tres comandos), o documentar en
  `README.md` la secuencia literal.
- **Estimated remediation scope:** Small

---

### [OPS-03] La configuración documenta valores nominales que no son los efectivos

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Documentación / riesgo de configuración
- **Location:** `configs/default.yaml:18-26` (`uncertainty_penalty: 0.35`) y
  `:11-16` (`max_plausible_edge: 0.075`)
- **Evidence:** Ocho líneas de comentario justifican el `0.35` con evidencia OOS
  detallada (1654 apuestas, ROI agregado −0.74% → +0.37%). Ninguna menciona que
  el coeficiente opera sobre una probabilidad **ya encogida al 50%** por
  `market_shrink`, de modo que el efecto sobre el desacuerdo real del modelo es
  **0.175** — verificado por ejecución en [QNT-01]. Lo mismo aplica al tope de
  edge implausible ([QNT-02]).
- **Impact:** La documentación de configuración es, en este proyecto, el registro
  de decisiones cuantitativas: es donde consta por qué cada número vale lo que
  vale. Que describa un parámetro con el doble de su efecto real convierte el
  registro en engañoso justo donde más se consulta.
- **Failure scenario:** Un ajuste futuro de `uncertainty_penalty` produce la
  mitad del efecto esperado y se interpreta como que el control "no funciona",
  llevando a desactivarlo.
- **Recommendation:** Documentar el acoplamiento en el propio YAML, junto a los
  dos parámetros. **No cambiar los valores**: están validados OOS tal como se
  componen hoy.
- **Estimated remediation scope:** Small

---

### [OPS-04] Cuatro archivos residuales de la shell sin trackear en la raíz

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Higiene del repositorio
- **Location:** raíz del repositorio: `rc` (4.077 B), `t` (2.750 B),
  `tatus` (2.625 B), `observaciones bloqueantes e importantes que sean válidas.`
- **Evidence:** Inspeccionados: `rc` contiene la ayuda del paginador `less`; `t`
  y `tatus` contienen salidas capturadas de `git diff` (nombres compatibles con
  un `git s > tatus` mal tecleado y una redirección `> t`). Son accidentes de
  shell, no artefactos del sistema.
- **Impact:** Bajo, pero con precedente: la auditoría 2026-08-04 registró
  exactamente este riesgo con un parche residual de ~1.800 líneas
  (`audit/latest/FINDINGS.md:103-110`, B-2) y lo mitigó añadiendo `*.patch` a
  `.gitignore`. Estos cuatro no encajan en ningún patrón ignorado y aparecen en
  cada `git status`, lo que erosiona la señal de ese comando.
- **Failure scenario:** Un `git add -A` los incorpora al repositorio.
- **Recommendation:** Borrarlos. **No los borré**: no los creé, son untracked
  —por tanto irrecuperables— y la instrucción de esta auditoría es no modificar
  archivos. Requiere confirmación del operador.
- **Estimated remediation scope:** Small

---

### [OPS-05] El estado del Programador de tareas no es verificable desde el repositorio

- **Severity:** Informational
- **Confidence:** Requires verification
- **Category:** Preparación operativa
- **Location:** `Obsidian/Estado del proyecto.md` (6 tareas documentadas);
  `DIARIO_COMPLETO.bat`, `CAPTURE_CLOSE.bat`, `BACKFILL_ALL.bat`,
  `REFRESH_ML.bat`, `VALIDATE_OOS.bat`
- **Evidence:** Los `.bat` existen y su encadenamiento es coherente con lo
  documentado (verificado en `00-audit-plan.md` §2). Que estén **registrados y
  activos** en el Programador de tareas de Windows no puede comprobarse desde el
  repositorio. La auditoría previa llegó a la misma conclusión
  (`audit/latest/FINDINGS.md:161-164`).
- **Impact:** Toda afirmación sobre "el sistema corre a diario a las 11:00" es,
  desde el repositorio, indemostrable.
- **Recommendation:** `Get-ScheduledTask` filtrado por el prefijo `SQP_`, con la
  salida pegada en la bitácora. Es la única forma de cerrar este punto.
- **Estimated remediation scope:** Small

---

### [OPS-06] Fallo de proceso recurrente: declarar estado sin verificarlo

- **Severity:** High
- **Confidence:** High confidence (heredado, no re-medido en esta pasada)
- **Category:** Proceso / fiabilidad de la documentación
- **Location:** `audit/latest/FINDINGS.md:30-44` (A-1);
  `.claude/automation/runtime/current-task.md`; `.claude/automation/STATES.md`
- **Evidence:** La auditoría del 2026-08-04 documentó **tres afirmaciones falsas
  de estado en tres días**: la deriva del `pick_mode` del 07-31 sin documentar; y
  el mismo 08-04, una bitácora que afirmaba "Suite completa verde" (real: 5
  failed) y "Ruff y Mypy no instalados" (real: instalados y limpios). Agravante:
  `current-task.md` cerró con `Result: PASS` violando la regla explícita de
  `STATES.md` que prohíbe declarar `PASS` sin evidencia observable.
- **Impact:** Es el hallazgo de mayor severidad estructural del proyecto y **no
  es de código**. Cualquier auditoría, decisión o loop autónomo que lea la
  documentación opera sobre un estado potencialmente falso. Degrada el valor de
  todo lo demás: un sistema con 637 tests verdes cuya bitácora puede afirmar lo
  contrario no es un sistema verificado.
- **Failure scenario:** Un agente autónomo lee "gate de CLV aprobado" en una nota
  no verificada y actúa en consecuencia.
- **Recommendation:** B-1 de `audit/latest/BACKLOG.md`: un control automático que
  haga fallar la suite si `current-task.md` declara `PASS` sin un bloque de
  comandos ejecutados con su código de salida. La regla ya existe; lo que falta
  es que algo la haga cumplir. **Sigue abierto.**
- **Suggested validation:** El propio test: un `current-task.md` con `PASS` y sin
  evidencia debe romper `pytest`.
- **Estimated remediation scope:** Medium

---

### [OPS-07] Documentación y configuración están hoy sincronizadas — verificado

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Documentación
- **Location:** `README.md:109-112` y `:114-123`; `configs/default.yaml:71-73`
- **Evidence:** `README.md` declara `pick_mode: edge` como modo activo desde
  2026-07-31 y describe `accuracy` como disponible pero no activo;
  `configs/default.yaml:72` dice `mode: edge`. **Coinciden.** La sección del
  README sobre el modo precisión conserva las tres advertencias verificadas
  (umbral sobre probabilidad no calibrada, hit rate ≠ rentabilidad, sin backtest
  propio), coherentes con `daily.py:415-436` (`_warn_if_uncalibrated_accuracy`),
  que efectivamente emite ese aviso.
- **Impact:** Ninguno pendiente. Se registra porque la deriva documentación↔
  configuración fue un hallazgo real el 08-02 y hoy está cerrada.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [OPS-08] El lenguaje de las salidas respeta las reglas del proyecto — verificado

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Documentación / cumplimiento
- **Location:** `README.md:8-10`; `src/sqp/backtesting/engine.py:75-78` (`note`);
  `src/sqp/pipeline/daily.py` (`DISCLAIMER` en `_finalize:369`)
- **Evidence:** El backtest incorpora en su propio resultado la advertencia
  *"never infer profitability from calibration alone"* (`engine.py:78`), y el run
  diario emite un `DISCLAIMER` en cada cierre de liga. `README.md:8-10` encabeza
  con la separación entre probabilidad estimada y garantía.
- **Impact:** Ninguno. El requisito de `.claude/rules/betting-output-rules.md`
  está implementado en el código, no solo en la documentación — que es la
  diferencia entre una regla y un deseo.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —
