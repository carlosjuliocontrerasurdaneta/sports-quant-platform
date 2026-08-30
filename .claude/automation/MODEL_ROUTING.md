# SQP Claude Code Model Routing

El enrutamiento tiene dos capas independientes:

1. `.claude/settings.json` selecciona el modelo de la conversación principal.
2. `UserPromptSubmit` clasifica la solicitud e inyecta una recomendación de loop y
   subagente. Cada subagente usa el modelo declarado en su frontmatter.

## PRINCIPIO RECTOR

> **Priorizar siempre el modelo superior para las tareas que requieran el máximo
> nivel de razonamiento, y delegar las demás en función de su complejidad y de
> las áreas en las que cada modelo ofrezca mejor rendimiento.**

Orden de decisión del operador (2026-08-25). **Gobierna toda esta política**: si
alguna regla concreta de abajo entra en conflicto con él, manda el principio y la
regla se corrige, no al revés.

**Relación con la tabla de rutas, dicha sin ambigüedad.** El principio y el
`default: sonnet` de `model-routing.json` **no** se contradicen, y conviene que
conste por qué: el principio dice "el modelo superior para lo que exige máximo
razonamiento", no "el modelo superior para todo". La tabla codifica el reparto
del trabajo **de razonamiento medio**, que es la mayoría del volumen. Lo que la
tabla **no** puede codificar es el disparador de abajo, porque clasifica por
palabras clave y las cinco clases de escalado no son léxicas. Por tanto:

- La tabla es el **suelo** por defecto, no el techo.
- El disparador de escalado tiene **precedencia sobre la ruta asignada**: si una
  tarea cae en cualquiera de las cinco clases, se sube aunque la ruta diga
  `sonnet` y aunque la clasificación por palabras clave no la haya detectado.
- Ese escalado se **registra** en `current-task.md`, igual que la excepción de
  `CLAUDE_CODE_SUBAGENT_MODEL`.

Por qué este principio y no "el modelo más barato que pase las pruebas": porque
**en este dominio los tests no detectan el modo de fallo dominante**. Un
`NameError` lo caza `ruff`. Un juicio cuantitativo plausible-pero-equivocado
—"esta correlación es señal", "este bucket con p<0,05 vale", "esta referencia no
es endógena"— pasa la suite entera, entra en producción y contamina las cifras
con las que se decide si el sistema gana dinero.

Consecuencias vinculantes:

- La pregunta correcta ante una tarea **no** es "¿cuál es el modelo más barato
  que probablemente baste?" sino **"¿cuánto razonamiento exige de verdad?"**. El
  coste es una restricción, no el criterio.
- Ante la duda entre dos escalones en una tarea de razonamiento alto, **se sube**.
  Infra-asignar el modelo en trabajo cuantitativo crítico —calibración, detección
  de fuga, diseño de experimentos, decisiones de riesgo— sale más caro que el
  modelo, porque el error entra en producción y contamina las cifras con las que
  se decide.
- Delegar hacia abajo es legítimo y esperado **cuando la tarea lo es**: lookups
  acotados, resúmenes, extracción mecánica y trabajo repetitivo bien definido.
- Jerarquía de capacidad vigente en este proyecto:
  `claude-fable-5` > `claude-opus-5` > `sonnet` > `haiku`.
- Un modelo inferior **no revierte unilateralmente** trabajo o decisiones
  producidas por uno superior. Si detecta un problema, lo **reporta**.

### Disparador de escalado: por CLASE de tarea, no por dificultad percibida

"Máximo nivel de razonamiento" no puede evaluarlo el propio modelo que va a
ejecutar la tarea: hace falta razonamiento para saber cuánto razonamiento hace
falta, y un modelo más débil **subestima sistemáticamente** la dificultad porque
no ve lo que no ve. Registrado con un caso real: el 2026-08-25 se clasificó
"alinear el candado de modelo" como trámite mecánico cuando era una decisión de
gobernanza sobre trabajo de un modelo superior; el clasificador era el propio
modelo que se equivocaba.

Por eso el disparador es **observable *ex ante*** y no admite juicio. Es de
máximo razonamiento, por definición y sin evaluar su dificultad aparente, toda
tarea que:

1. sea **irreversible** o difícil de revertir;
2. toque **parámetros de riesgo, modelo, estrategia, umbrales o gates**;
3. produzca **cifras publicables** (ROI, calibración, hit rate, edge, CLV);
4. **contradiga una decisión previa registrada** en la bitácora, `Tareas.md` o el
   registro de decisiones;
5. modifique el **contrato de un artefacto persistido** (esquemas, streams,
   ledger, settlement).

Que una de estas parezca trivial es irrelevante — y es precisamente la señal de
alarma.

### Subordinación a la medición

**Ningún escalón de modelo sustituye una medición.** Si la pregunta es
empíricamente resoluble con los datos ya guardados, **se mide antes de razonar**,
con el modelo que sea.

No es retórica: en este proyecto la restricción vinculante nunca ha sido la
capacidad de razonamiento sino la disciplina de medición. Las seis mediciones
negativas acumuladas salieron de *ejecutar algo*, no de pensar más fuerte — el
hallazgo de la escalera de `min_edge` (2026-08-25) esperaba en un módulo que
nadie había ejecutado nunca, y la señal fantasma de totals NBA (2026-08-24) la
destapó una contraprueba, no un argumento.

Un modelo superior es **más** peligroso aquí, no menos: produce narrativas más
convincentes sobre datos que no ha medido. La capacidad se aplica a **diseñar la
medición y a interpretarla**, nunca a sustituirla.

Corolario: "superior" ≠ "correcto". Un modelo inferior **con la medición delante
puede tener razón** contra un modelo superior sin ella. La cláusula de no
reversión de arriba es una regla de **proceso** (no revertir por iniciativa
propia), jamás un argumento de autoridad sobre el fondo.

## Política autorizada

- **Conversación principal:** `claude-opus-5`, por decisión humana explícita del
  2026-08-30. Supersede a `claude-fable-5` (2026-08-24), que había superseduo a
  `sonnet` (2026-08-18), este a `claude-opus-5` (2026-08-04) y este a
  `claude-fable-5` ese mismo día. Afecta solo al modelo interactivo de
  `settings.json`; el escalón de las rutas sigue en `sonnet` para el trabajo
  normal (abajo). El hook no debe afirmar que cambia este modelo.

  Que el modelo por defecto no sea el más capaz de la jerarquía **no contradice
  el principio rector**: `claude-fable-5` sigue siendo el escalón superior y
  sigue siendo el destino de las tareas de máximo razonamiento por el disparador
  de escalado. Lo que cambia es el punto de partida, no el techo. El principio
  exige subir ante la duda, no arrancar arriba siempre.

  Esta decisión se tomó para cerrar `KI-021`: el cambio llevaba desde antes del
  2026-08-29 aplicado a medias —`settings.json` y `docs/MODEL-ROUTING.md` en Opus
  5, esta política y el literal del test en Fable 5— y el candado de tres puntas
  mantenía la suite en rojo hasta que se decidiera.
- **Escalón de las rutas** (`model-routing.json`), el lever de coste:
  - `opus` — **solo** `full-audit`, `incident` y `quant-incident`: auditorías
    exhaustivas e incidentes críticos.
  - `haiku` — **solo** `documentation`: consulta y resumen acotados.
  - `sonnet` — todo lo demás, incluida la ruta `default`. Es el trabajo normal:
    modelado, calibración, backtesting, arquitectura, providers, bugfix,
    seguridad y release.
- **Frontmatter de subagentes:** política **independiente y sin cambios**. Un
  subagente declara `opus` o `haiku`, nunca `sonnet`: cuando se delega
  explícitamente a un especialista es porque el trabajo lo justifica. La ruta
  puede pasar un modelo que tiene precedencia sobre el frontmatter (ver abajo).

Una variable `CLAUDE_CODE_SUBAGENT_MODEL` o un modelo indicado explícitamente al
invocar un subagente puede tener precedencia sobre su frontmatter. Esa excepción
debe registrarse en `current-task.md`.

Este archivo es la fuente única de la política de modelos. `ORCHESTRATOR.md` y
`decision-engine.md` enlazan aquí en lugar de repetirla. Cambiar el modelo
principal o la política de subagentes requiere aprobación humana explícita y una
actualización deliberada de las pruebas de routing.

La clasificación por palabras clave es una ayuda determinista. El decision
engine, la semántica real de la solicitud y las reglas permanentes conservan
precedencia.
