# Backlog — tras la remediación del 2026-09-10

El plan de 12 filas de la Fase 3 se ejecutó completo salvo lo que aquí queda
abierto. Nada de esto se cierra sin decisión o acción del operador.

## B-01 — Cerrar el ciclo de la puerta OOS (deriva de AUD-HIGH-002)

**Estado**: pendiente del operador. **Prioridad**: alta, y con caducidad.

`SQP_Validate_OOS_Cdev` sigue con `Último resultado: 1` del 2026-09-01 y su
próxima ejecución programada es el **2026-10-01**. La causa raíz (KI-034: liga
con cuotas pero sin resultados almacenados → `IndexError` en el corte temporal)
ya está corregida en `scripts/validate_oos.py:225-237`, pero **esa corrección
lleva sin verificarse una sola vez**. Ejecutar la puerta a mano cierra el ciclo
y limpia el centinela; no ejecutarla deja tres semanas más sin saber si los
parámetros siguen generalizando.

No consume cuota de API (verificado: ni `validate_oos.py` ni
`model_vs_market_report.py` construyen `OddsAPIClient` ni llaman a `requests`).
La ejecución quedó bloqueada por el clasificador de permisos de la sesión.

```
! cmd /c VALIDATE_OOS.bat
```

Si sale 0, el centinela queda limpio. Si vuelve a fallar, el log
(`logs/validate_oos.log`) trae ahora la causa, que en septiembre no existía.

## B-02 — Pin de las acciones de CI a SHA

**Estado**: abierto por falta de red. **Prioridad**: baja.

`actions/checkout@v4` y `actions/setup-python@v5` siguen ancladas a etiqueta
móvil. Pinar a SHA exige obtener los digests, y no se inventan. Riesgo real bajo
(acciones de primera parte de GitHub) y acotado además porque
`BUILD_INFO.json` declara `published_to_github: false`. Ya se aplicó lo que sí
era verificable: `permissions: contents: read` a nivel de workflow e
instalaciones con `-c requirements.lock`.

## B-03 — Estado real del CI

**Estado**: NO_VERIFICABLE. El árbol no tiene `.git`, así que no hay remoto que
consultar ni este directorio dispara el workflow. El fichero `ci.yml` está bien
construido; eso es una afirmación sobre el fichero, no sobre la puerta. Se
resuelve solo cuando el parche se integre en un checkout con Git.

## B-04 — Cobertura no medible en el intérprete de producción

**Estado**: documentado, no corregible aquí. `pytest --cov` aborta con
`ImportError: cannot load module more than once per process` (numpy 2.4.4 +
Python 3.14.4). El CI la mide en 3.12, donde funciona. Cerrarlo de verdad exige
una versión de numpy/coverage compatible con 3.14, que es una actualización de
dependencia y no una corrección de auditoría.

## B-05 — `data/predictions/archive/` como única copia, con caducidad de 90 días

**Estado**: abierto, es una decisión de política. `prune_stale_candidates` puede
dejar el archivo como única copia de una liga podada, y `purge_old_artifacts` lo
borra a los 90 días. Cada política es correcta por separado; su interacción no
está documentada como ventana de recuperación finita. Con AUD-HIGH-001 corregido
el escenario que lo hacía probable (sobrescribir sin liquidar) es mucho menos
frecuente.

## B-06 — `AGENTS Tipster.md` duplica `.claude/agents/tipster.md`

**Estado**: mitigado, no resuelto. Se marcó la fuente canónica y la dirección de
propagación en la cabecera. Consolidar de verdad exige actualizar 5 referencias
por nombre y eliminar un fichero, y sin Git un borrado no es reversible.

## B-07 — Las 5 tareas del Programador son «Solo interactivo»

**Estado**: abierto, decisión del operador. Un día sin sesión iniciada no produce
picks, ni error, ni rastro. Con AUD-HIGH-003 corregido el informe de salud ya se
emite en las cuatro salidas del orquestador, pero eso sólo ayuda **si el
orquestador llega a ejecutarse**. Cambiar el modo de inicio de sesión toca el
Programador de tareas, que no se toca sin orden explícita.

## B-08 — `record_run_failure` / `clear_run_status` sin lock

**Estado**: heredado de KI-044, sigue abierto y sigue siendo del operador: poner
`locked()` significa que un timeout impediría registrar un fallo, que es peor que
perderlo raramente.
