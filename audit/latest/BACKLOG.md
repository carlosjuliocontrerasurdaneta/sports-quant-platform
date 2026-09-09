# Backlog — Auditoría 2026-09-08

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.

---

## B-1 · URGENTE: producción sigue parada. Un comando.

**Estado: pendiente, requiere al operador.**

El pipeline no genera picks desde el **2026-09-06 12:01**. Esta sesión corrigió
la **ceguera** (el informe de salud da `ERROR` y el tablero enciende el banner al
abrirlo) y dejó el árbol **limpio y al día**, así que el guard ya no bloquea:

```
DIARIO_COMPLETO.bat
```

**No se ejecutó** porque consume cuota de API de pago y escribe datos de
producción, y la sesión se cerró antes de llegar a ese paso. Verificación de que
el servicio volvió: `python scripts/health_check.py` debe dejar de emitir el
`ERROR` de liveness, y `data/predictions/predictions_*.csv` debe traer sello de
hoy.

Mientras siga parado, no se acumula muestra graduada — el recurso más escaso del
sistema, y el único que puede mover el gate del 0 de 41 actual.

---

## B-2 · CERRADO · Los commits están publicados

`origin/main` iba **8 commits por delante** (una sesión de remediación completa
del 2026-09-07 publicada desde otro clon, con cambios en `src/sqp/config.py`,
`markets/line_movement.py`, `pipeline/budget.py`, `pipeline/probabilities.py`,
los cuatro hooks `PostToolUse`, `.claude/settings.json` y `configs/default.yaml`).
Se trajeron con `git rebase` —`--ff-only` ya no era posible— resolviendo el único
conflicto, `known-issues.md`, conservando ambos bloques y renumerando los KI de
esta sesión a **039–043** para no pisar el KI-038 de aquella.

Los 9 commits de esta sesión se empujaron a `main` como `6c834e2`. Árbol
sincronizado: 0 por detrás, 0 por delante.

Con eso, **AUD-LOW-001 queda cerrado**: el `crossreview-on-stop.sh` corregido
(`c28ee6a`) ya está en el árbol que ejecuta producción.

**Nota de exactitud:** la fase de diagnóstico dijo «2 commits». Estaba mal
inferido de `git fetch --dry-run`, que imprime un rango de refs y no un conteo.
Eran 8.

---

## B-3 · AUD-INF-001 · Lock caducado sin heartbeat (POSIX)

`storage/lock.py` nunca refresca el `mtime` del `.lock`. Bajo semántica POSIX,
una sección crítica de más de `LOCK_STALE_S = 300 s` puede ser robada por un
segundo proceso, y al salir el primero borra el `.lock` del segundo, en cascada.
En Windows —el SO de producción— el `unlink` falla con `WinError 32` y degrada a
espera, que es el comportamiento correcto y ya está probado.

**No se corrigió**: es `INFERIDO`, no confirmado, y la skill prohíbe corregir
sobre inferencias.

**Qué falta para cerrarlo:** (1) medir el tiempo real **dentro** del `with
locked()` de `revalidate_candidates` —no de la función completa, que en
`capture_close.log` va de 38 s a 99 s—; (2) una reproducción en Linux con un
titular que duerma 301 s. Si la medición deja margen suficiente, la resolución
correcta puede ser documentar que no aplica, no añadir un heartbeat.

---

## B-4 · L-2 · Residuo de `.codex-tmp` con ACL denegada

Dos directorios `run-20260809T*` no se pudieron borrar: sus subdirectorios
`pytest/test_*` fueron creados por un proceso con otra ACL y esta sesión no
puede enumerarlos ni eliminarlos (`Permission denied`). Es la misma limitación
que la fase de diagnóstico ya declaró `NO_VERIFICABLE`.

**Cierre:** borrado manual por el operador con permisos suficientes, o
`takeown`/`icacls` sobre `.codex-tmp`. Impacto: ~21 MB de scratch ignorado.
No urgente.

---

## B-5 · Causa raíz del fallo del 2026-09-07: irrecuperable

`DIARIO_COMPLETO.bat` no escribía en ningún log, así que la evidencia de aquel
`0x1` se perdió en una consola inexistente. **AUD-MED-001 impide que vuelva a
pasar, no recupera lo perdido.** Lo que sí se acotó: `settle_all.log` no tiene
cabecera del 2026-09-07, y `SETTLE_ALL.bat` escribe la suya como primera acción,
así que el aborto ocurrió **antes o durante** el `call SETTLE_ALL.bat`.

Queda **abierto como incógnita**, no como tarea: si vuelve a ocurrir, el nuevo
`logs\diario_completo.log` lo dirá.

---

## B-6 · Cobertura de ramas y `.bat` en CI

Ninguna de las puertas cubre los `.bat`. Esta sesión los validó en un banco git
aislado (5 casos) y con pruebas de contrato sobre el texto, pero **CI no los
ejecuta** y no puede hacerlo (corre en Linux salvo una pata Windows que sólo
lanza pytest). Mejora posible, no urgente: un test que ejecute
`DIARIO_COMPLETO.bat` con stubs en la pata Windows del CI.

---

## No es backlog: es el estado de la evidencia

El gate sigue en **0 de 41 cortes autorizados**, con `n_max = 186` contra
`min_n = 300`. La parada de 48 h ha detenido la acumulación de esa muestra, que
es el recurso más escaso del sistema. Ninguna corrección de esta sesión cambia
la conclusión de la octava medición (2026-09-07): sin ventaja predictiva
demostrada, ROI OOS −23,71 %, ROI realizado −15,26 %,
`corr(edge declarado, PnL) = −0,105`.

---

# Añadido por la SEGUNDA auditoría integral del 2026-09-08

Los ítems B-1 a B-6 de arriba siguen vigentes tal cual. Lo que sigue es lo que
esta segunda pasada deja abierto. Los hallazgos que sí se corrigieron están en
`.claude/memory/known-issues.md`, KI-044.

## B-7 · Decisión del operador: ¿lock en el centinela de fallo?

`record_run_failure` y `clear_run_status` (`src/sqp/monitoring/run_status.py`)
hacen **read-modify-write sin exclusión** sobre `logs/run_status.json`. Cinco
tareas programadas pueden solaparse —`CAPTURE_CLOSE` cada 30 min contra
`DIARIO_COMPLETO` a las 12:00—, y un intercalado pierde la etapa del otro: una
alarma vigente se borra en silencio.

La regla del proyecto desde AUD-002 es "no se entra sin exclusión". Aquí choca
con algo peor: si `locked()` agota su espera, `record_run_failure` **aborta y el
fallo no se registra**. Perder un fallo siempre es peor que perderlo raramente.

**No se implementa.** Es una elección entre dos modos de fallo y le corresponde
al operador. Opciones, por si sirve: (a) lock con `except LockNoAdquiridoError`
en `scripts/run_status.py` que escriba igualmente y lo diga en el log —degrada,
que es lo que AUD-002 prohíbe, pero aquí la dirección segura es la contraria—;
(b) lock estricto asumiendo el aborto; (c) un fichero por etapa, que elimina el
read-modify-write de raíz y es probablemente la respuesta correcta, a costa de
cambiar el formato del centinela y sus lectores.

- **Archivos**: `src/sqp/monitoring/run_status.py`, `scripts/run_status.py`.
- **Riesgo de no hacer nada**: bajo pero real; el peor caso es una alarma
  perdida, que es exactamente lo que este centinela existe para impedir.
- **Validación**: una prueba de intercalado con dos procesos (el lock no es
  reentrante, así que un solo proceso no reproduce la carrera).

## B-8 · `SQP_Validate_OOS_Cdev` lleva fallado desde el 2026-09-01

`LastTaskResult = 0x1` el 2026-09-01, y es **mensual**: el próximo intento es el
2026-10-01. El centinela de la etapa `validate_oos` se añadió el 2026-09-06
(AUD-MED-003), *después* del fallo, así que ese `0x1` nunca llegó a ninguna capa
de monitorización y **su causa raíz sigue sin diagnosticar**.

**Reproducción ejecutada: NO falla.** `python scripts/validate_oos.py`, el
comando exacto del BAT, terminó con **exit 0** tras **1 h 40 min** de CPU:
*«32 liga(s) validada(s) de 33; 0 sin cuotas, 1 sin resultados, 0 con error»*.
Así que el defecto **no está en el camino normal del script** con los datos de
hoy.

Lo que deja abierto y lo que acota:

- La causa del `0x1` del 2026-09-01 sigue **sin diagnosticar**, y ahora sabemos
  que no es un fallo determinista del script.
- Candidatos que la reproducción no descarta: el paso `model_vs_market_report.py`
  (best-effort, no bloqueante, así que no explicaría un `0x1`), una interrupción
  del entorno, o que la máquina se suspendiera a mitad.
- **Dato nuevo y accionable por sí mismo: el job mensual dura más de hora y
  media.** Una ventana así es superficie de fallo por sí misma, y ninguna alarma
  vigila su duración.
- El centinela de la etapa `validate_oos` existe desde el 2026-09-06, así que el
  próximo fallo **sí** llegará al health check. Queda como incógnita, no como
  tarea ciega.

- **Archivos**: `scripts/validate_oos.py`, `VALIDATE_OOS.bat`.
- **Acción**: reproducir y corregir, o forzar una ejecución manual antes del
  2026-10-01.

## B-9 · CERRADO · El aviso sin dueño es ahora informativo

El informe de salud emite `WARN: <liga>: features stale (15.5d)` para mlb, nba,
nfl y nhl —**4 de sus 6 avisos**— en cada ejecución. Pero el refresco de esas
features lo hacía `SQP_Refresh_ML_Cdev`, **retirada por orden del operador el
2026-08-29** (AUD-LOW-003) porque la inferencia ML no tiene ningún llamador en
el camino de picks: `feature_store` solo lo importan `evaluation/compare.py`,
`scripts/build_features.py` y `scripts/train_models.py`.

Es decir: el control avisa de la caducidad de un artefacto que, por decisión
registrada, ya no tiene quien lo refresque **ni consumidor en el camino del
dinero**. Un aviso que lleva 15 días encendido y que nadie puede accionar
entrena a ignorar los otros dos.

**Resuelto el 2026-09-09 por orden del operador: degradado a INFO.**

Medido sobre producción: el informe pasó de **5 avisos a 1**. Los cuatro
degradados salen ahora en una sola línea informativa que dice la cifra *y* el
motivo — «la tarea que los refrescaba se retiró el 2026-08-29 por orden del
operador y el artefacto no tiene consumidor en el camino de picks». El aviso que
queda (`mls`, 49 filas pendientes) sí es accionable.

**No es un silenciamiento.** La antigüedad se conserva por liga en
`leagues[<lg>]["features_age_days"]` y agregada en la clave nueva
`features_stale` del informe, así que sigue siendo auditable y su tendencia
visible.

**Y la degradación está atada al hecho que la justifica**, no a una preferencia:
`test_el_camino_de_picks_no_depende_del_feature_store` recorre el grafo de
imports desde `pipeline/daily.py` —38 módulos— y falla el día que
`storage/feature_store` reaparezca en el camino de picks, porque ese día la
caducidad vuelve a ser accionable y el aviso tiene que volver a WARNING. El
detector no es vacío: la misma búsqueda partiendo de `evaluation/compare.py` sí
encuentra la dependencia.

4 pruebas nuevas, 3 de ellas verificadas discriminantes contra el árbol previo.

- **Archivos**: `src/sqp/monitoring/health.py`, `tests/test_health.py`.

## No es backlog: dos observaciones

- **`pip-audit` corre en las 4 patas de la matriz** auditando el mismo
  `requirements.lock`, que no depende de la versión de Python. Es redundante,
  **y aun así se deja como está**: reducir una puerta de seguridad de cuatro
  entornos a uno para ahorrar minutos de CI es un mal cambio aunque el análisis
  diga que el resultado es idéntico.
- **`data/odds/` son 810 MB en CSV mensuales** y crecen. Las correcciones de
  KI-044 quitan el 76 % de la lectura y la evitan del todo cuando no hay
  trabajo, pero el mes en curso —147 MB— se sigue leyendo entero cuando sí lo
  hay. La solución de fondo (partición diaria, o Parquet con predicado sobre
  `captured_at`) es un cambio de contrato de un artefacto persistido: requiere
  decisión explícita y una migración, no una optimización de paso.

## B-10 · Decisión de contrato: `full-audit` → `audit-remediation`

`audit-remediation` exige como **requisito de entrada** un paquete en
`audit/latest/` —`FINDINGS.md`, `BACKLOG.md`, IDs resueltos, y lee
`MANIFEST.json`/`tests_initial`—. `full-audit` **no produce ese paquete ni lo
menciona** en ninguna de sus nueve referencias, incluida `reporting.md`, que
define el informe consolidado sin nombrar rutas ni esquema.

Consecuencia: una auditoría entregada como informe único cumple `full-audit` y
**bloquea** a `audit-remediation` por falta de un paquete que nadie le pidió al
productor. Lo viví en esta sesión: entregué el informe en conversación y añadí
al backlog existente en vez de sobrescribir el paquete del turno anterior.

**No lo corrijo**: elegir qué lado cambia es una decisión de contrato, no una
corrección. Las dos salidas son legítimas y excluyentes:

- **(a)** `full-audit` emite el paquete cuando el usuario autorice escribirlo.
  Choca con que las fases 0–3 son de **solo lectura**, y obligar a crear ficheros
  en un diagnóstico es justamente lo que esa restricción existe para impedir.
- **(b)** `audit-remediation` acepta un informe único con IDs aprobados, y el
  paquete pasa a ser opcional. Más simple, pero pierde el `MANIFEST.json` como
  ancla de baseline y trazabilidad.

Hallazgo H04 de `analisis-skills-codex.md`. Mi recomendación es **(b)** con el
`MANIFEST.json` degradado a opcional-pero-recomendado, pero es tuya.

## B-11 · Tres defectos en el paquete vendorizado Superpowers

`analisis-skills-codex.md` confirma tres MEDIUM que viven en
`.claude/skills/superpowers-main/`, **paquete de terceros**. Un parche local se
pierde en la siguiente actualización, así que **no los toco**:

- **H07 · `requesting-code-review`**: la plantilla compara `BASE_SHA..HEAD_SHA`
  derivando BASE de `HEAD~1`, así que en una tarea de varios commits el primero
  queda fuera del diff y una revisión parcial se presenta como revisión de la
  feature completa. El propio `subagent-driven-development` prohíbe `HEAD~1`
  precisamente por esto.
- **H08 · `finishing-a-development-branch`**: pierde el worktree original antes
  de ejecutar el cleanup.
- **H09 · `subagent-driven-development`**: el ledger no identifica el plan, así
  que puede omitir tareas de una ejecución distinta.

Salidas posibles: fijar la versión del paquete y llevar el parche aguas arriba,
o documentar la desviación en una nota propia que sobreviva a la actualización.

## Nota sobre `analisis-skills-codex.md`

El informe está **sin versionar** (217 KB, 1.775 líneas, 2026-09-08 22:11). Es la
base de evidencia de KI-045 y de estos dos ítems, así que tiene valor permanente:
**debería commitearse**. No lo hago yo — es un entregable de Codex por encargo
del operador, y la regla vigente es no tocar sus informes sin autorización.
