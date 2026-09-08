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
