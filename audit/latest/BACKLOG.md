# Backlog — Auditoría 2026-09-08

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.

---

## B-1 · URGENTE: producción sigue parada, y estos cambios la bloquean

**Estado: requiere acción del operador. Dos comandos.**

El pipeline no genera picks desde el **2026-09-06 12:01**. Esta sesión ha
corregido la **ceguera** (ahora el informe de salud da `ERROR` y el tablero
enciende el banner), pero **no ha relanzado el pipeline**: hacerlo consume cuota
de API de pago y escribe datos de producción, y `audit-remediation` exige para
eso una aprobación humana separada de la aprobación de la corrección.

Además, el árbol está **sucio** con las correcciones de esta sesión, así que
`DIARIO_COMPLETO.bat` **abortará en el guard KI-036** hasta que se commiteen.
El guard funciona: es el comportamiento correcto, no un efecto secundario.

Secuencia para recuperar el servicio:

```
git add -A && git commit          # desbloquea el guard de árbol limpio
DIARIO_COMPLETO.bat               # settle -> run, en ese orden
```

Después conviene `git pull --ff-only` (ver B-2). Verificación de que el servicio
volvió: `python scripts/health_check.py` debe dejar de emitir el `ERROR` de
liveness.

---

## B-2 · AUD-LOW-001 · Traer los 2 commits de `origin/main`

`origin/main` va por delante en **8 commits**: una sesión de remediación
completa del 2026-09-07 publicada desde otro clon (AUD-MED-001..003,
AUD-LOW-001..005 de *aquel* informe, más su KI-038), que toca `src/sqp/config.py`,
`markets/line_movement.py`, `pipeline/budget.py`, `pipeline/probabilities.py`,
los cuatro hooks `PostToolUse`, `.claude/settings.json` y `configs/default.yaml`.
El árbol de producción no los tiene.

**Nota:** la fase de diagnóstico dijo «2 commits». Estaba mal inferido de
`git fetch --dry-run`, que imprime un rango de refs y no un conteo.

**No se aplicó** porque `git pull` es un merge, y la skill `audit-remediation`
excluye expresamente commits, pushes y merges de la autorización de corrección.
Editar el hook a mano sería peor: crearía una divergencia con el remoto.

**Cierre:** `git pull --ff-only` (o `--rebase` si ya hay commits locales), y
después la suite. Riesgo bajo: avance rápido sobre un árbol que, una vez
commiteado B-1, no diverge en esos ficheros.

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
