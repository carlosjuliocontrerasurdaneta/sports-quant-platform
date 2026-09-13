# Resumen ejecutivo — Auditoría integral 2026-09-10

**Resultado: DEGRADED.** Las correcciones aprobadas están aplicadas y validadas;
queda una validación operativa sin ejecutar que depende del operador.

## Lo que se encontró

4 HIGH, 19 MEDIUM y 24 LOW confirmados; **ningún CRITICAL**. El núcleo
cuantitativo está sano: `ruff` y `mypy` limpios, 1.929 de 1.931 tests verdes de
partida, y las rutas de dinero (odds, vig, Kelly, prediction gate, calibrador)
llevan capas de defensa documentadas *in situ* por auditorías previas.

**El riesgo no estaba en el cálculo, sino en la capa que lo orquesta y en la que
lo vigila.** Los cuatro HIGH del catálogo comparten causa: controles
inventariados pero nunca comprobados.

- `if errorlevel 1` significa «>= 1» en cmd.exe y **no ve códigos negativos**.
  Un crash de la liquidación (0xC000013A, documentado tres veces en los propios
  BAT) se leía como éxito, seguía a generación sobrescribiendo picks sin liquidar
  **y limpiaba su propio centinela**: el fallo apagaba su alarma. 26
  comprobaciones en 10 BAT, ninguna usaba `neq 0`.
- El informe de salud **no lo producía nada automático** desde el 2026-08-29, y
  el otro consumidor del centinela sólo se renderiza si el run llega al final.
  Por esa vía la puerta OOS llevaba **9 días fallada sin que nadie lo viera**.
- La invariante de frescura de cuotas se verificaba **buscando texto en el
  fuente**, no ejercitando el comportamiento.

## Dos cosas que aparecieron sin estar en el guion

1. **Incidente de producción.** El run diario falló hoy a las 12:00:01. El
   paquete de optimización se había desplegado sobre el directorio de producción
   y se llevó el estado no versionado: `data/` vacío y sin `.env`. El guard que
   debía impedirlo falla abierto y una extracción de ZIP no trae `.git`.
   Restaurado por el operador durante la sesión.
2. **Un dataset histórico contaminado.** `pitcher_confirmation_log_mlb.csv`
   contenía dos filas fabricadas por la suite de tests, presentes ya en la copia
   de respaldo. Evidencia inventada entrando como válida en el dataset de un
   experimento pre-registrado.

## Lo que se corrigió

**88 ficheros modificados, 3 de test nuevos, +35 tests.** Ni un parámetro de
riesgo, gate, calibrador, modelo o estrategia tocado. El único cambio sobre
datos fue retirar esas dos filas, con copia de seguridad.

Validación: `ruff` 0, `mypy` 0, vía rápida completa **1.741 passed / 0 failed**.
Los BAT se validaron aparte, ejecutando en `cmd.exe` **las líneas reales ya
parcheadas**; el techo de frescura se verificó **por mutación**.

## Lo que queda abierto

- **`VALIDATE_OOS.bat` sin ejecutar** (bloqueado por permisos de la sesión). Es
  la acción de mayor retorno y es del operador: `! cmd /c VALIDATE_OOS.bat`.
- Pin de acciones de CI a SHA (requiere red), estado del CI (requiere Git) y
  cobertura en 3.14 (dependencia). Detalle en `BACKLOG.md`.

## Lo que este informe NO dice

No se midió Brier, ECE, CLV, hit rate ni ROI, y no se afirma nada sobre ninguno.
Una suite verde acredita que los defectos corregidos no reaparecen; **no acredita
ventaja predictiva ni rentabilidad**.
