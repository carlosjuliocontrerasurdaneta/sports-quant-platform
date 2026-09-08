@echo off
REM SQP - Orquestador diario COMPLETO: encadena liquidacion + run en el orden
REM correcto para que el run NUNCA sobrescriba picks sin liquidar.
REM
REM ORDEN GARANTIZADO:
REM   1) SETTLE_ALL.bat  (liquida los picks del dia anterior + auditoria)
REM   2) RUN_DIARIO_ALL.bat  (genera los picks del dia y sobrescribe candidates_*)
REM
REM Si la liquidacion falla, ABORTA antes del run para no perder picks. Como
REM respaldo, el pipeline ahora archiva data\predictions\archive\ antes de
REM sobrescribir, asi que un pick sin liquidar siempre queda recuperable.
REM
REM Usar ESTE bat en el programador de tareas en vez de los dos por separado.
setlocal
cd /d %~dp0
REM Mismo interprete fijo que los BAT que encadena (auditoria 2026-07-24, M-5).
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"

REM RASTRO PROPIO (AUD-MED-001, auditoria integral 2026-09-08). Este BAT no
REM escribia NADA en ningun log: todos sus echo iban a la consola, y bajo el
REM Programador de tareas no hay consola. Los unicos pasos redirigidos eran las
REM tres vistas de picks del [3/3]; el guard de arbol, los marcadores de etapa y
REM las TRES ramas de error se perdian enteros.
REM
REM Lo pago la incidencia del 2026-09-07: la tarea fallo a las 12:00 con 0x1 y no
REM dejo ni una linea en run_diario.log ni en settle_all.log, asi que la causa
REM raiz de dos dias de produccion parada es hoy indeterminable. La ausencia de
REM rastro no es un detalle de comodidad: es lo que convierte un fallo en un
REM fallo indiagnosticable.
REM
REM `call :log` escribe en la consola Y en el fichero, para no perder el eco
REM interactivo que ya existia.
if not exist logs mkdir logs
call scripts\rotate_log.cmd logs\diario_completo.log
call :log "=== SQP - DIARIO COMPLETO (%DATE% %TIME%) ==="

REM [0/3] GUARD DE ARBOL LIMPIO (KI-036, opcion (b), orden del operador 2026-09-06).
REM
REM La tarea programada apunta al ARBOL DE TRABAJO, asi que produccion ejecuta lo
REM que haya en disco, commiteado o no. El 2026-09-06 el run de las 12:00 corrio
REM con ocho ficheros de `src/` y los cuatro BAT ya modificados por una sesion de
REM remediacion en curso: codigo escrito una hora antes y validado tres horas
REM DESPUES. Y `run_all.py:331` llama a `auto_promote_calibrators`, asi que el
REM gate de promocion que se estaba editando ese mismo rato se ejercito en vivo.
REM Aquel dia no paso nada -- rc=0 y ninguna promocion registrada --, pero fue el
REM resultado, no el proceso. Era la SEGUNDA vez: el 2026-09-02 el run quedo
REM incompleto por lo mismo y la decision quedo pendiente.
REM
REM Ahora se aborta ANTES de liquidar, que es el unico momento en que abortar no
REM cuesta nada: no se ha tocado ningun dato todavia.
REM
REM Ambito: solo codigo que produccion EJECUTA. Los ficheros del operador
REM (NOTAS, informes, markdown suelto) quedan fuera a proposito -- estan casi
REM siempre modificados y bloquearian el run todos los dias, que es como se
REM aprende a saltarse un guard.
REM
REM Escape para recuperacion manual:  set SQP_SKIP_TREE_GUARD=1
set "SQP_TREE_DIRTY="
if defined SQP_SKIP_TREE_GUARD (
    call :log "[AVISO] SQP_SKIP_TREE_GUARD activo: se OMITE el guard de arbol limpio."
    goto :tree_ok
)
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    REM Falla ABIERTO a proposito: "no se puede comprobar" no es "esta sucio", y
    REM detener el pipeline del dinero porque falte git seria un modo de fallo
    REM nuevo que nadie pidio. Se avisa fuerte y se continua.
    call :log "[AVISO] git no disponible: NO se pudo comprobar el arbol. Se continua."
    goto :tree_ok
)
for /f "delims=" %%i in ('git status --porcelain -- src scripts configs *.bat 2^>nul') do set "SQP_TREE_DIRTY=1"
if defined SQP_TREE_DIRTY goto :error_arbol

REM [0b] ARBOL ATRASADO (AUD-MED-004, auditoria integral 2026-09-08).
REM
REM El guard de arriba comprueba que no haya cambios SIN COMMITEAR. No comprueba
REM que el arbol este AL DIA, y produccion ejecuta lo que hay en disco. El
REM 2026-09-08 este clon iba 2 commits por detras de origin/main sin que nada lo
REM dijera: uno de ellos, c28ee6a, era una CORRECCION de codigo publicada desde
REM otra sesion. Una correccion que no llega a la maquina que opera es una
REM correccion que no existe, y el mismo mecanismo dejaria fuera un arreglo de
REM src\sqp\risk sin aviso.
REM
REM AVISA, NO ABORTA. Detener el pipeline del dinero porque falte un commit de
REM documentacion seria un modo de fallo nuevo y desproporcionado; lo que hacia
REM falta era que dejara de ser invisible, y ahora el aviso queda ESCRITO gracias
REM a AUD-MED-001.
REM
REM El fetch es imprescindible: sin el se compararia contra una referencia remota
REM obsoleta, que es exactamente el estado que produjo el hallazgo (origin/main
REM local == HEAD mientras el remoto iba por delante). Toda la comprobacion falla
REM ABIERTO igual que el guard de arriba.
REM
REM EL FETCH VA CON PLAZO DE PARED Y SIN INTERACTIVIDAD (revision cruzada de
REM Codex, 2026-09-08). La primera version lo acotaba SOLO con
REM GIT_HTTP_LOW_SPEED_LIMIT/TIME, y eso limita la velocidad de TRANSFERENCIA
REM HTTP, no la espera de un gestor de credenciales ni la duracion total del
REM subproceso. Bajo el Programador de tareas no hay escritorio: un git que pida
REM credenciales se queda esperando a nadie y BLOQUEA la liquidacion y la
REM generacion de picks. Un aviso consultivo no puede parar el pipeline del
REM dinero.
REM
REM Tres candados, porque ninguno cubre al otro:
REM   GIT_TERMINAL_PROMPT=0  git falla en vez de preguntar por terminal
REM   GCM_INTERACTIVE=never  Git Credential Manager no abre su dialogo
REM   GIT_ASKPASS=echo       ningun askpass grafico se queda esperando
REM   + WaitForExit(plazo)   plazo de pared duro, y se MATA el proceso
REM Los limites de velocidad se conservan: abortan una transferencia estancada
REM DENTRO del plazo, que sigue siendo util.
set "GIT_HTTP_LOW_SPEED_LIMIT=1000"
set "GIT_HTTP_LOW_SPEED_TIME=15"
set "GIT_TERMINAL_PROMPT=0"
set "GCM_INTERACTIVE=never"
set "GIT_ASKPASS=echo"
if not defined SQP_FETCH_TIMEOUT_MS set "SQP_FETCH_TIMEOUT_MS=20000"
set "SQP_UPSTREAM="
for /f "delims=" %%i in ('git rev-parse --abbrev-ref "@{u}" 2^>nul') do set "SQP_UPSTREAM=%%i"
if not defined SQP_UPSTREAM (
    call :log "[INFO] sin rama upstream: no se comprueba si el arbol esta atrasado."
    goto :tree_ok
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process git -ArgumentList 'fetch','--quiet' -WorkingDirectory '%CD%' -NoNewWindow -PassThru; if (-not $p.WaitForExit(%SQP_FETCH_TIMEOUT_MS%)) { try { $p.Kill() } catch {}; exit 124 }; exit $p.ExitCode" >nul 2>&1
if errorlevel 124 (
    call :log "[AVISO] git fetch excedio su plazo de %SQP_FETCH_TIMEOUT_MS% ms y se ABORTO; se continua. La comparacion usa la referencia remota local, que puede estar obsoleta."
) else if errorlevel 1 (
    call :log "[AVISO] git fetch fallo: la comparacion usa la referencia remota local, que puede estar obsoleta."
)
REM SE CUENTA LO QUE FALTA, NO SE COMPARAN SHA. La primera version comparaba
REM `HEAD` con `@{u}` por igualdad, y eso confunde dos situaciones opuestas:
REM
REM   POR DETRAS  el remoto trae commits que esta maquina NO ejecuta  -> AVISO
REM   POR DELANTE hay commits locales sin publicar                    -> normal
REM
REM Ir por delante es el estado NORMAL entre un arreglo y su push, y produccion
REM esta ejecutando codigo mas nuevo, no mas viejo: avisar ahi seria una alarma
REM diaria y falsa, y una alarma que suena sin motivo es una alarma que se
REM aprende a ignorar -- el modo de fallo que esta auditoria lleva todo el dia
REM documentando. Se cuenta `HEAD..@{u}`, que son exactamente los commits que
REM le FALTAN a esta maquina.
set "SQP_DETRAS="
for /f "delims=" %%i in ('git rev-list --count HEAD.."@{u}" 2^>nul') do set "SQP_DETRAS=%%i"
if not defined SQP_DETRAS goto :tree_ok
if "%SQP_DETRAS%"=="0" goto :tree_ok
set "SQP_HEAD_SHA="
set "SQP_UP_SHA="
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "SQP_HEAD_SHA=%%i"
for /f "delims=" %%i in ('git rev-parse "@{u}" 2^>nul') do set "SQP_UP_SHA=%%i"
call :log "[AVISO] EL ARBOL ESTA %SQP_DETRAS% COMMIT(S) POR DETRAS de %SQP_UPSTREAM%."
call :log "[AVISO]   HEAD local  = %SQP_HEAD_SHA%"
call :log "[AVISO]   upstream    = %SQP_UP_SHA%"
call :log "[AVISO] Produccion ejecuta el ARBOL DE TRABAJO, asi que esas"
call :log "[AVISO] correcciones NO se estan ejecutando en esta maquina."
call :log "[AVISO] Revisar con: git log --oneline HEAD..%SQP_UPSTREAM%"
call :log "[AVISO] Se CONTINUA: esto avisa, no aborta."
:tree_ok

call :log "[1/2] Liquidando picks del dia anterior..."
call "%~dp0SETTLE_ALL.bat"
if errorlevel 1 goto :error_settle

call :log "[2/2] Ejecutando run diario multi-liga..."
call "%~dp0RUN_DIARIO_ALL.bat"
if errorlevel 1 goto :error_run

REM [3/3] REGLA FUNDAMENTAL (operador 2026-08-26, SACROSANTA E INAMOVIBLE):
REM "generar picks para todos los deportes y mercados, priorizando aquellos con
REM las mayores probabilidades". Dos vistas sobre lo que el run acaba de
REM escribir: la lista COMPLETA y la de margen positivo. Solo LEEN el stream
REM servido -- no generan nada, no tocan stakes ni gates, no gastan cuota.
REM BEST-EFFORT a proposito: son vistas, y no deben poder tumbar el flujo que ya
REM produjo los picks y el reporte.
call :log "[3/3] Generando la lista diaria de picks..."
set PYTHONPATH=src
"%SQP_PYTHON%" scripts\daily_picks.py --top 0 >> logs\run_diario.log 2>&1
if errorlevel 1 echo [AVISO] daily_picks.py fallo (no bloqueante) >> logs\run_diario.log

REM Segunda vista: solo las lineas cuya probabilidad estimada supera su punto de
REM equilibrio (margen = prob_est - 1/precio > 0). NO es una lista de apuestas:
REM sigue sin llevar stake. Los margenes mas grandes concentran el riesgo -- ocho
REM de los diez mayores del 2026-08-26 eran ncaaf/brasileirao con handicaps de
REM +31/+38.5, justo el perfil que el cap de plausibilidad marca y que rinde
REM -22.6% frente al -5.6% de lo que el cap deja pasar.
"%SQP_PYTHON%" scripts\daily_picks.py --min-margin 0 --top 0 --out data\predictions\picks_margen_positivo.md >> logs\run_diario.log 2>&1
if errorlevel 1 echo [AVISO] daily_picks --min-margin fallo (no bloqueante) >> logs\run_diario.log

REM Tercera vista: el CRITERIO DEL OPERADOR (2026-08-26) -- probabilidad >= 0.60
REM Y ROI esperado > 0. Es la lista corta del dia: 8 de 105 partidos el
REM 2026-08-26. Nota: `--min-roi 0` y `--min-margin 0` son el MISMO filtro
REM (p*cuota-1 > 0 <=> p > 1/cuota); se usa la forma de ROI porque es como el
REM operador lo pidio. Sigue sin llevar stake.
"%SQP_PYTHON%" scripts\daily_picks.py --min-prob 0.60 --min-roi 0 --top 0 --out data\predictions\picks_seleccion.md >> logs\run_diario.log 2>&1
if errorlevel 1 echo [AVISO] daily_picks --min-prob/--min-roi fallo (no bloqueante) >> logs\run_diario.log

REM Cuarta vista: clasificacion del TIPSTER (AGENTS Tipster.md) -- tiers
REM A/B/C/NO BET con cuota justa, EV, edge sobre el mercado sin vig y aviso de
REM correlacion. DETERMINISTA a proposito: un agente LLM no puede dispararse
REM desde el Programador de tareas, vive dentro de una sesion de Claude. El
REM dashboard resalta los A en verde y los B en ambar.
"%SQP_PYTHON%" scripts\tipster_report.py >> logs\run_diario.log 2>&1
if errorlevel 1 echo [AVISO] tipster_report.py fallo (no bloqueante) >> logs\run_diario.log

REM Run correcto: limpia el centinela de las DOS etapas que este bat arregla,
REM una por una (auditoria 2026-07-29, S-1).
REM
REM NO se usa `--clear` a secas, que borra el fichero ENTERO. Eso era correcto
REM cuando solo existian `settle` y `run` y este bat ejecutaba las dos; desde que
REM el centinela cubre seis etapas (AUD-MED-003, 2026-09-06) borraria tambien las
REM CUATRO que este bat no arregla. Un run diario correcto habria apagado en
REM silencio la alarma de `validate_oos` -- que lleva fallada desde el 2026-09-01
REM y no se reintenta hasta el 2026-10-01 --, o la del backfill, o la de la
REM captura de cierre. Es decir: la alarma nueva habria durado hasta el dia
REM siguiente. Encontrado al implementar KI-036, el mismo dia que se creo.
"%SQP_PYTHON%" scripts\run_status.py --clear --only-stage settle
"%SQP_PYTHON%" scripts\run_status.py --clear --only-stage run
"%SQP_PYTHON%" scripts\run_status.py --clear --only-stage guard_arbol

call :log "=== DIARIO COMPLETO: OK ==="

REM Flujo terminado: abre el dashboard automaticamente.
REM - Sesion interactiva (SESSIONNAME definido): abre directo via open_dashboard.ps1 -Force.
REM - Bajo el Programador de tareas (sin escritorio): abrir el navegador desde ESTE
REM   proceso terminaba con 0xC000013A, asi que se dispara la tarea interactiva
REM   SQP_Dashboard_Cdev (scripts\register_dashboard_task.ps1), que el Programador
REM   lanza en la sesion del usuario. Si nadie esta logueado, el trigger de logon
REM   de esa tarea abre el dashboard al iniciar sesion (gateado por frescura+marcador).
if defined SESSIONNAME (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open_dashboard.ps1" -Force
) else (
    schtasks /Run /TN SQP_Dashboard_Cdev >nul 2>&1 || echo [INFO] No se pudo disparar SQP_Dashboard_Cdev; el dashboard abrira al iniciar sesion.
)

endlocal
goto :eof

REM Escribe en la consola Y en logs\diario_completo.log (AUD-MED-001). Se usa
REM `call :log "texto"`: las comillas protegen parentesis y simbolos de
REM redireccion dentro del mensaje, y `%~1` las quita al imprimir.
REM La redireccion va DELANTE del echo a proposito. Con `echo %~1>> fichero`,
REM si el mensaje termina en un digito cmd lee ese digito como descriptor
REM (`...1>>` = redirigir stdout) y se lo COME del texto. Las lineas del aviso de
REM arbol atrasado terminan en un SHA, que acaba en digito la mitad de las veces.
:log
echo %~1
>>logs\diario_completo.log echo %~1
goto :eof

:error_arbol
call :log "*** ABORTADO ANTES DE LIQUIDAR: hay cambios SIN COMMITEAR en codigo que  ***"
call :log "*** produccion ejecuta (src\, scripts\, configs\ o *.bat).               ***"
call :log "*** No se ha tocado ningun dato. Commitea los cambios y vuelve a lanzar. ***"
call :log "*** Si de verdad hace falta correr sobre el arbol sucio (recuperacion):  ***"
call :log "***     set SQP_SKIP_TREE_GUARD=1                                        ***"
git status --porcelain -- src scripts configs *.bat >> logs\diario_completo.log 2>&1
git status --porcelain -- src scripts configs *.bat
"%SQP_PYTHON%" scripts\run_status.py --fail --stage guard_arbol --exit-code 1 >> logs\diario_completo.log 2>&1
endlocal
exit /b 1

:error_settle
call :log "*** ERROR EN LA LIQUIDACION: se ABORTA el run diario para no perder picks. ***"
call :log "*** Revisa logs\settle_all.log, corrige y vuelve a ejecutar este bat.      ***"
"%SQP_PYTHON%" scripts\run_status.py --fail --stage settle --exit-code 1 >> logs\diario_completo.log 2>&1
endlocal
exit /b 1

:error_run
call :log "*** ERROR EN EL RUN DIARIO (la liquidacion si termino). ***"
call :log "*** Revisa logs\run_diario.log.                         ***"
"%SQP_PYTHON%" scripts\run_status.py --fail --stage run --exit-code 1 >> logs\diario_completo.log 2>&1
endlocal
exit /b 1
