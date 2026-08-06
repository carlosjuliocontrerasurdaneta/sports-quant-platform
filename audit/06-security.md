# 06 — Seguridad y manejo de secretos

Base: commit `7871bdb`. **No se modificó código de aplicación.**

**Limitación declarada de esta pasada:** la lectura de `.env.example` fue
**denegada por permisos** durante la auditoría. Ningún hallazgo de este documento
depende de su contenido, pero la verificación de la plantilla de variables de
entorno queda pendiente de autorización explícita.

No se inventó ninguna vulnerabilidad. Los controles que resultaron correctos se
documentan como tales, porque en una auditoría de seguridad la ausencia de
hallazgos solo es informativa si consta qué se buscó.

---

### [SEC-01] Todas las llamadas HTTP declaran timeout — verificado, sin hallazgos

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Fiabilidad de red / control verificado
- **Location:** `src/sqp/providers/odds_api.py:119` (30 s);
  `espn_results.py:99` (60 s); `espn_tennis.py:107` (60 s);
  `mlb_statsapi.py:24,59,86,96,130` (60–120 s)
- **Evidence:** Barrido sobre `src/sqp/providers/` de `requests.get|post`: las
  ocho invocaciones existentes llevan `timeout=` explícito. No hay ninguna
  llamada sin él.
- **Impact:** Cumple `.claude/rules/security-rules.md`. Un proveedor colgado no
  puede bloquear indefinidamente el run diario.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [SEC-02] La redacción de la clave del proveedor está implementada, no solo documentada

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Secretos en logs / control verificado
- **Location:** `src/sqp/providers/odds_api.py:114` (inyección de `apiKey`),
  `:122`, `:134`, `:138-143` (redacción en los dos caminos de error)
- **Evidence:** `params["apiKey"] = self.api_key` (`:114`); los mensajes de error
  se reconstruyen con `(query redacted)` (`:134`, `:143`) en lugar de propagar el
  `HTTPError` original, cuyo mensaje *"carries the full URL including
  apiKey=..."* según el comentario `:138-140`. La clave se toma de `Settings`, no
  hay literales en el código.
- **Impact:** Cierra el vector por el que la clave acabaría en `logs/`. El
  barrido de secretos de la auditoría previa sobre los 443 archivos trackeados no
  encontró coincidencias (`audit/latest/FINDINGS.md:139-143`).
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [SEC-03] El único uso de `subprocess` es seguro — verificado, sin hallazgos

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Ejecución de procesos / inyección
- **Location:** `scripts/claude_project_health.py:32-42` (`git_output`)
- **Evidence:** `subprocess.run(["git", *args], cwd=ROOT, text=True,
  capture_output=True, timeout=10, check=False)`. Lista de argumentos (no
  `shell=True`), timeout explícito, `cwd` fijado al repositorio, y los argumentos
  son literales del propio script, no entrada externa. No existe ningún
  `os.system`, `eval`, `exec` ni `shell=True` en `src/` ni en `scripts/`.
- **Impact:** No hay superficie de inyección de comandos.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [SEC-04] Deserialización de modelos con `joblib` desde el sistema de archivos

- **Severity:** Low
- **Confidence:** Confirmed (mecanismo) · **modelo de amenaza: Requires verification**
- **Category:** Deserialización insegura
- **Location:** `src/sqp/calibration/calibrator.py:50-54` (`_load_calibrator`,
  `joblib.load(path_str)`) y `src/sqp/models/ml_predict.py:17-21`
  (`joblib.load(str(path))`); escritura en `calibrator.py:92` y
  `ml_train.py:95`
- **Evidence:** `joblib.load` usa `pickle` por debajo: deserializar un archivo
  manipulado ejecuta código arbitrario. Las rutas provienen de `data/models/`
  (`calibrator.py:33`, `MODELS_DIR = ROOT / "data" / "models"`), un directorio
  local generado por el propio sistema y **no versionado**.
- **Impact:** El riesgo real depende enteramente de quién puede escribir en
  `data/models/`. En una instalación monousuario en Windows, el vector requiere
  que el atacante ya tenga escritura en el disco del operador, en cuyo caso hay
  problemas mayores. **No lo clasifico como vulnerabilidad explotable**; lo
  registro porque es la única ruta de ejecución de código por datos del proyecto,
  y porque el día que los modelos se compartan entre máquinas —o se restauren
  desde una copia— el supuesto cambia.
- **Failure scenario:** Un `.joblib` restaurado desde un respaldo no confiable, o
  sincronizado desde otra máquina, ejecuta código al promover un calibrador.
- **Recommendation:** No cambiar nada hoy. Si algún día los artefactos de modelo
  cruzan una frontera de confianza, añadir verificación de integridad (hash
  firmado en el registro) antes de `joblib.load`.
- **Suggested validation:** Confirmar que `data/models/` no se sincroniza ni se
  restaura desde ninguna fuente externa. Requiere conocimiento del operador, no
  del repositorio.
- **Estimated remediation scope:** Small (si algún día aplica)

---

### [SEC-05] Cinco manejadores amplios descartan la excepción sin registrarla

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Fallo silencioso / observabilidad
- **Location:** `src/sqp/audit/html_report.py:208-209` (→ `pd.DataFrame()` vacío)
  y `:395-396` (→ `False`); `src/sqp/features/common.py:36-37` (→ `3.0`);
  `src/sqp/storage/feature_store.py:122`;
  `scripts/capture_closing_odds.py:70`
- **Evidence:** Patrón `except Exception:` seguido de un valor por defecto sin
  `log.*`. El resto del proyecto usa `except Exception as exc:` con registro —de
  hecho la auditoría previa verificó **0 `except:` desnudos** y clasificó los
  manejadores amplios como "fallan al lado seguro y con log"
  (`audit/latest/FINDINGS.md:150-154`). Estos cinco son la excepción a esa
  afirmación.
- **Impact:** El caso más relevante es `html_report.py:208`: un fallo al
  construir la tabla de segmentos produce un DataFrame vacío, y el dashboard
  —la superficie por la que el operador lee el estado del sistema— muestra una
  sección vacía indistinguible de "no hay datos todavía". `features/common.py:36`
  devuelve un `3.0` de días de descanso por defecto que se propaga al modelo
  como si fuera un dato observado.
- **Failure scenario:** Un cambio de esquema rompe el cálculo de segmentos; el
  dashboard sigue renderizando, en verde y vacío, durante días.
- **Recommendation:** Añadir `log.warning` con la excepción en los cinco puntos.
  No cambiar el valor de retorno: la degradación es deliberada y correcta; lo que
  falta es que sea audible.
- **Suggested validation:** Provocar el fallo con un CSV malformado y comprobar
  que aparece en `logs/`.
- **Estimated remediation scope:** Small

---

### [SEC-06] La plantilla de variables de entorno no pudo verificarse

- **Severity:** Informational
- **Confidence:** Requires verification
- **Category:** Gestión de secretos
- **Location:** `.env.example` (raíz del repositorio)
- **Evidence:** El intento de lectura fue **denegado por la política de permisos
  del entorno** durante esta auditoría. No dispongo de evidencia propia sobre su
  contenido. La auditoría previa verificó que `.env` **no** está trackeado y que
  solo lo está `.env.example` (`audit/latest/FINDINGS.md:144-146`), pero eso es
  una afirmación sobre el índice de git, no sobre el contenido de la plantilla.
- **Impact:** Ninguno conocido. Se registra para que no se lea la ausencia de
  hallazgos como una verificación.
- **Recommendation:** Repetir la comprobación con autorización explícita,
  confirmando que la plantilla contiene nombres de variables y ningún valor real.
- **Estimated remediation scope:** Small

---

## Resumen de la superficie revisada

| Vector | Resultado |
|---|---|
| Secretos en código | Sin literales; clave solo vía `Settings` — **verificado** |
| Secretos en logs | Redacción implementada en ambos caminos de error — **verificado** |
| Timeouts HTTP | 8 de 8 llamadas — **verificado** |
| Inyección de comandos | Sin `shell=True`, `eval`, `exec` ni `os.system` — **verificado** |
| Deserialización | `joblib`/pickle desde ruta local — [SEC-04] |
| Manejo de rutas | Todas las rutas derivan de `ROOT`; sin entrada externa en rutas — **verificado** |
| Dependencias | `pip-audit` sin vulnerabilidades (`audit/01-baseline-results.md:46`) — **verificado** |
| Fallo silencioso | 5 manejadores sin registro — [SEC-05] |
| Plantilla `.env` | **No verificable en esta pasada** — [SEC-06] |
