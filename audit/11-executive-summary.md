# 11 — Resumen ejecutivo

Auditoría integral · commit `7871bdb` · 2026-08-05 · **sin modificar código de
aplicación**. 56 hallazgos: **0 críticos, 11 altos, 19 medios, 14 bajos,
12 informativos** (8 de ellos controles verificados sin hallazgos).

---

## Salud general: BUENA en ingeniería, NO DEMOSTRADA en su propósito

Hay que separar dos juicios que este proyecto invita constantemente a mezclar.

**Como software, el proyecto está sano.** 637 tests verdes, `ruff` y `mypy`
limpios, `pip-audit` sin vulnerabilidades, sin secretos en el repositorio, todas
las llamadas HTTP con timeout, escrituras atómicas, capas de riesgo múltiples y
por defecto denegatorias. La calidad es claramente superior a la media de un
proyecto personal de este tamaño.

**Como sistema de apuestas, no ha demostrado nada.** El gate de CLV sigue
**vacío**: ningún (liga, mercado) alcanza mediana positiva con n≥30. El ROI
realizado es **−8.4% de banca** sobre 431 apuestas graduadas y el OOS de la regla
edge/Kelly es **−5.32%** (`audit/latest/QUANT_REVIEW.md:18-25`). Ninguno de los
56 hallazgos de esta auditoría cambia eso, y ninguna de sus correcciones lo
cambiaría: son de corrección, integridad y observabilidad.

**Ningún hallazgo es crítico hoy** porque `shadow_mode: true` pone todos los
stakes a 0 y tiene precedencia sobre el resto de flags (`daily.py:389-392`). Esa
es también la razón por la que el sistema puede permitirse los defectos que
siguen: el coste actual de un error es evidencia corrupta, no dinero. **Cuatro de
los hallazgos altos se convierten en críticos el día que el shadow mode se
levante.**

## Los diez riesgos principales

| # | ID | Riesgo | Por qué importa |
|---|---|---|---|
| 1 | [COR-01]/[COR-02] | Una línea `NaN` fabrica el resultado de la apuesta: en totals, Under **siempre** gana y Over **siempre** pierde; en spreads, siempre pierde | Verificado por ejecución. Corrompe a la vez ROI realizado, etiquetas de calibración y hit rate. Un `win` fabricado es peor que una fila perdida: entra como evidencia válida |
| 2 | [QNT-04] | Un solo CLV `inf` aprueba un mercado en el gate que gobierna el stake real | Verificado por ejecución: `median` no ignora `inf`, e `inf > 0` es `True`. Es la regla de salida del shadow mode: un precio corrupto puede levantarla |
| 3 | [QNT-03] | `NaN` atraviesa los dos guards de de-vig y anula el mercado completo en silencio | Pipeline **vivo**. Eventos que desaparecen de los picks sin contador ni aviso correcto |
| 4 | [OPS-06] | El estado se declara sin verificarlo: 3 afirmaciones falsas en 3 días | No es de código y degrada todo lo demás. Una suite verde cuya bitácora puede afirmar lo contrario no es un sistema verificado |
| 5 | [DAT-01]/[ARCH-02] | El backtest evalúa precios que producción descarta | La cifra OOS con la que se decide desplegar mide **otra política** |
| 6 | [TST-01] | La prueba que protege el shadow mode se auto-salta si el shadow mode se apaga | Control invertido: el escenario que más importa detectar es el que desactiva la detección |
| 7 | [QNT-01] | La penalización de incertidumbre opera al 0.175, la mitad del 0.35 configurado | Verificado por ejecución. El control mejor documentado del sistema no hace lo que su documentación dice |
| 8 | [DAT-04] | 54 filas servidas que nunca se gradúan | Sesgo de supervivencia sistemático si la falta de graduación se correlaciona con la liga |
| 9 | [QNT-05] | Hasta 6 selecciones del mismo partido dimensionadas como independientes | Kelly presupone independencia; los caps son agregados, no por evento. Post-shadow, un resultado adverso pega varias veces |
| 10 | [COR-04]/[PRF-02] | El lock puede girar sin pausa ni deadline si `stat()` falla | Cuelgue del run diario al 100% de CPU, sin que `timeout_s` rescate |

## Bloqueantes inmediatos

**Para seguir operando en shadow: ninguno.** El sistema puede seguir acumulando
evidencia hoy mismo.

**Para levantar el shadow mode, cuatro bloqueantes absolutos:**

1. **[QNT-04]** — el gate que autoriza el dinero real puede aprobarse con un
   precio corrupto. Mientras esto siga, el gate no es una garantía.
2. **[COR-01]/[COR-02]** — la liquidación puede fabricar resultados. Toda la
   evidencia sobre la que se decidiría levantar el shadow pasa por ahí.
3. **[DAT-01]** — no hay una cifra OOS que describa la política desplegada.
4. **[QNT-05]** — no existe límite de exposición por evento.

Ninguno es grande. Los cuatro suman menos de un día de trabajo bien dirigido.

## Fortalezas

No son concesiones: son razones concretas por las que esta auditoría pudo ser
específica en vez de genérica.

- **Cada defecto vivido tiene su prueba de regresión, con la fecha y el
  identificador del incidente en el docstring** ([TST-06]). La suite creció de
  424 a 637 tests en seis semanas sin volverse ruido.
- **Los comentarios del código registran por qué cada número vale lo que vale**,
  con la evidencia OOS que lo respalda (`configs/default.yaml:11-30`). Es
  documentación de decisiones, no de mecánica.
- **Las capas de riesgo son múltiples y por defecto denegatorias**: shadow, gate
  de CLV con default-deny, monitor de degradación con histéresis, tope de edge
  implausible, dos capas de exposición.
- **El lenguaje obligatorio está implementado en el código**, no solo en la
  documentación: el backtest incorpora en su propio resultado *"never infer
  profitability from calibration alone"* (`engine.py:78`) ([OPS-08]).
- **El condicionamiento de empates en el backtest de calibración es correcto**
  ([QNT-07]) — el error clásico que sobreestima la calibración está evitado
  explícitamente.
- **La honestidad sobre la ausencia de edge es sistemática** y sobrevivió a un
  cambio de estrategia que la contradecía (el modo `accuracy`, revertido con su
  razonamiento registrado).

## Temas de deuda técnica

Los 56 hallazgos se agrupan en cinco patrones. Corregir el patrón vale más que
corregir sus instancias.

1. **Guards que no filtran `NaN`/`inf` (7 hallazgos).** El patrón es siempre el
   mismo: una comparación (`<= 1.0`, `>= 1`, `<= 0`, `> 0`) que devuelve `False`
   ante `NaN` y deja pasar el valor. Recorre `probabilities.py`, `vig.py`,
   `settle.py`, `clv.py` y `clv_gate.py`. **Un solo predicado compartido cierra
   [QNT-03], [QNT-04], [COR-01], [COR-02], [COR-03] y [DAT-01] a la vez.**
2. **Lógica de precios triplicada (4 hallazgos).** Producción, backtest y
   auditoría implementan el mismo camino con reglas distintas. Ya divergieron una
   vez (B-13) y hoy siguen divergidas.
3. **Composición de controles invisible (3 hallazgos).** `run_league` aplica el
   shrink de mercado antes de los controles que deberían mirar el desacuerdo
   crudo, lo que reduce a la mitad la penalización y el tope de edge sin que nada
   lo indique.
4. **Tests que miran hacia atrás (4 hallazgos).** Excelentes en regresiones
   vividas, ausentes en estados degradados: sin propiedades, sin cobertura
   medible, con un test de seguridad invertido.
5. **Verificación por documentación (3 hallazgos).** El estado se afirma en notas
   en vez de derivarse de artefactos. Es el único patrón que no es de código y el
   que más contamina a los demás.

## Orden de remediación recomendado

El criterio es **evidencia primero**: mientras la liquidación pueda fabricar
resultados y el backtest medir otra política, cualquier otra corrección se
valida contra números en los que no se puede confiar.

| Orden | Qué | IDs | Por qué antes que lo siguiente |
|---|---|---|---|
| 1 | Tests que documenten el defecto, en rojo | [TST-02], [TST-05] | Fijan el comportamiento actual antes de tocarlo. Las propiedades deberían fallar de inmediato: es la confirmación independiente de [QNT-03] |
| 2 | Predicado único de valor finito y utilizable | [QNT-03], [COR-01], [COR-02], [COR-03] | Cierra el patrón nº 1. **Re-liquidar y republicar** las métricas afectadas |
| 3 | Guard de finitud en el gate de CLV | [QNT-04] | Depende de 2. Sin esto el gate no autoriza nada de forma fiable |
| 4 | Invertir el test del shadow mode | [TST-01] | Trivial, y hasta que se haga la red de seguridad tiene un agujero conocido |
| 5 | Unificar precios backtest↔producción y re-correr | [ARCH-02], [DAT-01], [DAT-02] | Depende de 2. Produce la primera cifra OOS que describe la política real |
| 6 | Cap de exposición por evento | [QNT-05] | Decisión de política de riesgo: **requiere al operador**, no es una corrección |
| 7 | Control automático de evidencia | [OPS-06] | Impide que la sesión que arregla todo lo anterior lo declare sin verificarlo |
| 8 | Lock, cobertura, entorno | [COR-04], [TST-03], [OPS-01] | Infraestructura; no bloquea evidencia |
| 9 | Documentar acoplamientos | [QNT-01], [QNT-02], [OPS-03] | **Documentar, no cambiar**: los valores están validados OOS tal como se componen |
| 10 | Duplicación y mantenibilidad | [ARCH-01], [ARCH-03], [ARCH-04], [ARCH-05] | Sin urgencia; hacerlo después reduce el riesgo de conflicto con 1–5 |

## Plan a 30 / 60 / 90 días

Con una restricción declarada por delante: **nada de esto aumenta la
probabilidad de que el sistema gane dinero.** El objetivo de los 90 días no es
rentabilidad, es llegar a poder confiar en las cifras con las que algún día se
decidirá si la hay.

### 30 días — que la evidencia sea confiable

- Órdenes 1 a 4 completos: propiedades y tests en rojo, predicado único de valor
  finito, guard del gate de CLV, test del shadow mode invertido.
- Re-liquidación y republicación de las métricas afectadas por [COR-01]/[COR-02],
  **con el delta explícito** respecto de las cifras actuales.
- Cerrar [DAT-04] (las 54 filas): requiere autorización del operador por consumo
  de cuota.
- Instalar `pytest-cov` y fijar una línea base de cobertura ([TST-03]).
- **Criterio de salida:** `health_check.py` en OK, y ninguna métrica publicada
  depende de una fila con valor no finito.

### 60 días — que el backtest describa el sistema real

- Órdenes 5 y 7: unificar precios entre backtest y producción, re-correr el OOS y
  publicar el delta; control automático de evidencia ([OPS-06]).
- Resolver las 8 verificaciones pendientes del índice, empezando por [DAT-07]
  (solapamiento entre ajuste de parámetros y ventana OOS), que es la que puede
  invalidar la cifra OOS entera.
- Añadir Python 3.14 a la matriz de CI ([OPS-01]).
- **Criterio de salida:** existe una cifra OOS reproducible, verificada
  independiente del ajuste de parámetros, sobre la política desplegada.

### 90 días — que la decisión de salir del shadow sea defendible

- Orden 6: decisión del operador sobre el cap por evento ([QNT-05]).
- Alinear el gate de CLV con el criterio de test de signo que ya se adoptó para
  el gate intradía ([QNT-06]) — es coherencia interna, no una idea nueva.
- Órdenes 8–10: infraestructura, documentación de acoplamientos, duplicación.
- **Criterio de salida:** el gate de CLV puede consultarse y su respuesta —sea
  cual sea— es defendible. Si sigue vacío, esa también es una respuesta válida y
  probablemente la correcta.

---

## Lo que esta auditoría no establece

- **Si el sistema gana dinero.** Ninguna fase lo midió. El hecho dominante sigue
  siendo la ausencia de ventaja predictiva demostrada.
- **La ausencia de leakage.** Se encontraron rutas de riesgo y un precedente
  confirmado y reparado (KI-019); no se puede demostrar que no queden más.
- **El contenido de `data/`, `historical/`, `logs/`, `exports/`.** No escaneados
  por regla permanente del proyecto. La frecuencia real de [COR-01]/[COR-02]
  queda por medir.
- **El contenido de `.env.example`.** Lectura denegada por permisos ([SEC-06]).
- **El estado del Programador de tareas de Windows.** Fuera del repositorio
  ([OPS-05]).
