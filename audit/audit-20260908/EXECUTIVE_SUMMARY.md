# Resumen ejecutivo — Auditoría integral y remediación, 2026-09-08

**Base:** `62108b1`. **Alcance:** repositorio completo. **Fases 0–5 completadas.**

## Lo que se encontró

El **código** estaba sano: 1.636 pruebas verdes, Ruff y MyPy limpios, CI verde
en las cinco patas con `pip-audit` bloqueante, los seis hallazgos de la
auditoría independiente de Codex (2026-09-06) cerrados con pruebas
discriminantes, los 16 calibradores live y de staging sin defecto estructural, y
el ledger íntegro y verificable (915,75 sobre 1.305 liquidaciones).

Lo que fallaba era **la operación y su instrumentación**:

> **Producción llevaba 48 horas sin generar un solo pick y ningún control lo
> decía.** El último run completo terminó el 2026-09-06 12:01. La tarea del
> 2026-09-07 falló con `0x1` **sin escribir una línea en ningún log**. El
> centinela de fallo no existía, así que el informe de salud decía
> `WARN, 0 errors` y el banner rojo del tablero estaba apagado. Y `logs/sqp.log`
> llevaba desde el 2026-09-06 23:30 congelado en su tope de 5 MB, **descartando
> cada registro** que intentaba escribirse.

Tres defectos HIGH, cuatro MEDIUM y dos LOW, todos confirmados por reproducción
o verificación estática. Ninguno es un defecto cuantitativo: son controles que
decían algo distinto de lo que medían — la enfermedad crónica que este
repositorio lleva meses documentando, esta vez en la capa que vigila al resto.

## Lo que se corrigió

Nueve de los diez IDs (el décimo, `AUD-LOW-001`, ya está corregido en
`origin/main` y su remedio es traer el commit, no editar el fichero):

1. **Rotación de logs** — un único `RotatingFileHandler` compartido en vez de
   uno por nombre de logger. Verificado en producción: `sqp.log` rotó y los
   tracebacks desaparecieron.
2. **Liveness del pipeline** — comprobación independiente del centinela, en el
   informe de salud y en el banner del tablero. Verificado: `health_check.py`
   pasó de `WARN, 0 errors` a `ERROR`, detectando la parada real.
3. **Integridad de los ajustes de banca** — una cabecera derivada ya no evapora
   una retirada e infla el capital sobre el que se dimensiona Kelly.
4. **Rastro del orquestador** — `DIARIO_COMPLETO.bat` ya escribe en un log
   propio, incluidas sus tres ramas de error.
5. **Aviso de árbol atrasado** — producción ya no ejecuta código desactualizado
   en silencio.
6. **Exclusión en `ServedStore`** — la carrera que se cerró para el fichero del
   dinero, cerrada también para el de la evidencia.
7. **Escritura atómica única** — los seis sitios que la reimplementaban a mano
   usan ya el helper canónico.
8. **Nombres de skills** alineados con sus directorios.
9. **Limpieza** de residuo ignorado (4 de 5 lotes; el quinto bloqueado por ACL).

Todo con **29 pruebas nuevas discriminantes** y validación final:
**1.665 passed, 1 skipped**, Ruff y MyPy limpios, sin regresiones atribuibles.
Los `.bat` se validaron aparte, en un banco git aislado, con cinco casos.

## Lo que queda

**Producción sigue parada.** Recuperarla exige dos comandos del operador
(`git commit` para desbloquear el guard de árbol limpio, y `DIARIO_COMPLETO.bat`),
porque relanzar el pipeline consume cuota de pago y escribe datos de producción,
y eso requiere una aprobación separada. Detalle en `BACKLOG.md` (B-1).

## Lo que esto no acredita

Una corrección validada arregla un defecto; **no acredita ventaja predictiva ni
rentabilidad**. El gate sigue en 0 de 41 cortes autorizados, con `n_max = 186`
frente a `min_n = 300`, y la octava medición del proyecto (2026-09-07) sigue sin
encontrar ventaja demostrada sobre el mercado.
