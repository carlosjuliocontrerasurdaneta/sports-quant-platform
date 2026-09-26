# SQP Claude Code Model Routing

El enrutamiento tiene tres capas independientes:

1. `.claude/settings.json` selecciona el modelo de la conversación principal.
2. El parámetro `model` de la herramienta `Agent` asigna el modelo de cada
   subagente en el momento de delegar, con precedencia sobre su frontmatter
   (ver la REGLA DE DESPACHO, abajo). Si no se pasa, rige el frontmatter.
3. `model-routing.json` mapea la solicitud a una skill (su cuerpo es el loop;
   hasta el 2026-09-18 la clave era `loop` y apuntaba a `.claude/loops/`) y a
   sus subagentes. Se
   consulta **bajo demanda** desde `/route-task`, con el clasificador
   `.claude/automation/route_classifier.py`. **No hay inyección automática**: el
   hook `UserPromptSubmit` que la hacía se **retiró el 2026-09-01**, porque
   nunca había estado cableado —cuando se retiró, `settings.json` sólo
   declaraba `PostToolUse` y `Stop`; hoy declara además `PreToolUse`
   (matcher `Agent`), así que la frase en presente quedó obsoleta y se pone
   en pasado (auditoría integral 2026-09-10). Nada de esto reabre el caso:
   `UserPromptSubmit` sigue sin declararse— y porque, aun cableado, solo inyecta texto consultivo: no asigna
   modelo. Consultar bajo demanda cuesta contexto únicamente cuando el enrutado
   importa, en vez de en cada turno.

## PRINCIPIO RECTOR

> **Priorizar siempre el modelo superior para las tareas que requieran el máximo
> nivel de razonamiento, y delegar las demás en función de su complejidad y de
> las áreas en las que cada modelo ofrezca mejor rendimiento.**

Orden de decisión del operador (2026-08-25), reiterada el 2026-09-01 y **el
2026-09-26 como principio fundamental**. **Gobierna toda esta política**: si
alguna regla concreta de abajo entra en conflicto con él, manda el principio y la
regla se corrige, no al revés.

**Reparto operativo por defecto** (fijado el 2026-09-26, tras un fallo real):

| Pieza de la tarea | Modelo |
|---|---|
| Inventario, búsqueda y resumen acotados | Haiku |
| Implementar scripts, tests y cambios bien especificados | Sonnet |
| Orquestar, integrar, ejecutar, commitear y comunicar | Opus (conversación principal) |
| Diseñar pre-registros, revisar e interpretar veredictos y cifras, y todo lo que caiga en las cinco clases de escalado | Fable |

**Fable revisa ANTES del commit, no después.** El 2026-09-26 se commiteó
`mlb.pitcher_bound 0.05` (parámetro de modelo y contradicción de una decisión
registrada) decidido enteramente en Opus. La revisión de Fable llegó después y
encontró un bloqueante (`starters_mlb.csv` congelado desde el 12/06). El
principio ya estaba escrito: faltaba que se cumpliera. El candado pre-commit
(`.claude/hooks/fable_gate.py`, en revisión) convierte esta regla en mecanismo
para las rutas sensibles.

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
- Jerarquía de capacidad **de Anthropic** (hecho, no política):
  `claude-fable-5-1` > `claude-opus-5-5` > `claude-sonnet-5` > `claude-haiku-4-5`.
  La documentación oficial lo dice explícitamente: *"start with Claude Opus 5.5
  for most workloads"*, y se sube a Fable 5.1 *"for demanding reasoning and
  long-horizon agentic work, or when your evals on Claude Opus 5.5 at higher
  effort still fall short"*.

  **Verificado en vivo el 2026-09-22** contra
  `platform.claude.com/docs/en/about-claude/models/overview` y `/pricing`, no
  contra la tabla cacheada de ninguna skill (ver más abajo la lección del
  2026-09-03). En esa misma página `claude-opus-5` figura ya entre los modelos
  **legacy** —sigue servido, pero fuera de la línea actual—, de modo que
  mantenerlo como punto de partida habría dejado el defecto del proyecto en un
  escalón retirado. Datos verificados de Opus 5.5: ID `claude-opus-5-5`, $4/$20
  por MTok, lectura de caché $0,20, contexto 1M, salida máxima 128K, `effort`
  por defecto `medium` (un escalón por debajo del `high` de Opus 5; este
  proyecto fija `effortLevel: max` en `settings.json`, así que el defecto del
  modelo no decide aquí), retirada no antes del 2027-09-22.

  **El ID lleva guiones: `claude-fable-5-1`.** `claude-fable-5.1` no es un
  identificador válido —el punto pertenece al NOMBRE, no a la API— y
  `claude-fable-5` (sin sufijo) es un modelo distinto, hoy **legacy**.

- Reparto **operativo de este proyecto** (decisión del operador, 2026-08-30;
  techo actualizado a Fable 5.1 el 2026-09-04; punto de partida actualizado a
  Opus 5.5 el 2026-09-22):
  - **`claude-opus-5-5` es el modelo por defecto**, y el punto de partida de
    todo (decisión del operador 2026-09-22; antes `claude-opus-5`).
  - **`claude-fable-5-1` se reserva para máxima capacidad de razonamiento**: es
    el destino del disparador de escalado, no el punto de partida.

  Punto de partida y techo son cosas distintas, y aquí están separados a
  propósito. Empezar en Fable 5.1 costaría 2,5x ($10/$50 frente a $4/$20 por
  MTok) sin que la mayoría del volumen lo necesite; no tenerlo disponible
  dejaría el principio rector sin destino al que escalar. Por eso Opus 5.5 abajo
  y Fable 5.1 arriba.

  La actualización del 2026-09-22 movió el **punto de partida**, no el techo:
  Opus 5.5 sustituye a Opus 5 en el escalón de abajo y Fable 5.1 sigue siendo el
  destino del escalado. La separación entre los dos no se toca — es lo único que
  hace accionable al principio rector.

  El principio rector queda intacto y **accionable**: "el modelo superior para
  lo que exige máximo razonamiento" apunta a `claude-fable-5-1`, que es de hecho
  el escalón superior de la jerarquía de arriba. Ante la duda, se sube a Fable
  5.1 y se registra el escalado en `current-task.md`.
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

- **Conversación principal:** `claude-opus-5-5`, por decisión humana explícita
  del 2026-09-22 (orden del operador: "actualizar el modelo a claude 5.5").
  Supersede a `claude-opus-5` (2026-08-30), que había superseduo a
  `claude-fable-5` (2026-08-24), este a `sonnet` (2026-08-18), este a
  `claude-opus-5` (2026-08-04) y este a `claude-fable-5` ese mismo día. Afecta
  solo al modelo interactivo de `settings.json`; el escalón de las rutas sigue
  en `sonnet` para el trabajo normal (abajo). El hook no debe afirmar que cambia
  este modelo.

  **Editar `settings.json` no cambia el modelo de una sesión ya en marcha**: la
  sesión que aplicó este cambio siguió corriendo en `claude-opus-5`. El valor
  nuevo rige en la siguiente sesión, o antes con `/model claude-opus-5-5`.

  `claude-opus-5-5` es el **punto de partida**, no el techo. El techo es
  `claude-fable-5-1`, reservado para máxima capacidad de razonamiento (ver el
  reparto operativo del principio rector, arriba). Punto de partida y techo
  están separados a propósito y **no deben volver a fundirse**: sin un escalón
  por encima, el principio rector se queda sin destino al que escalar y deja de
  ser accionable.

  **El punto de partida pasó de `claude-opus-5` a `claude-opus-5-5` el
  2026-09-22**, por decisión del operador, verificada en vivo contra la
  documentación de modelos y de precios el mismo día (ver el bloque de datos
  verificados en el principio rector). El techo no se movió. Las menciones a
  `claude-opus-5` que siguen en esta sección son REGISTRO HISTÓRICO de las
  decisiones de agosto y septiembre y no se reescriben, por la misma razón que
  las de `claude-fable-5`.

  **El techo pasó de `claude-fable-5` a `claude-fable-5-1` el 2026-09-04**, por
  decisión del operador. Fable 5.1 es el modelo actual y Fable 5 quedó legacy.
  Las menciones a `claude-fable-5` que siguen más abajo en esta sección son
  REGISTRO HISTÓRICO de decisiones de agosto y no se reescriben: cambiar lo que
  se decidió entonces para que encaje con lo de hoy es justo lo que este archivo
  existe para impedir.

  Cómo llegó aquí, porque la lección importa más que el cambio: el 2026-09-03 la
  auditoría **revirtió** un cambio del operador que introducía Fable 5.1,
  «tras verificar contra el catálogo», y además endureció el test a token
  completo para que no pudiera reentrar. La verificación era contra una tabla
  cacheada. Fable 5.1 existía. Un candado construido sobre una premisa no
  verificada en vivo no protege: bloquea la corrección. La regla operativa que
  queda es la de `docs/CLAUDE-CODEX-INTEGRATION.md` aplicada a los modelos —
  cualquier dato de ID, precio o estado se comprueba contra la documentación
  viva antes de afirmarlo, y nunca de memoria.

  Esta decisión se tomó en dos tiempos para cerrar `KI-021`. Primero el modelo
  principal: el cambio llevaba desde antes del 2026-08-29 aplicado a medias
  —`settings.json` y `docs/MODEL-ROUTING.md` en Opus 5, esta política y el
  literal del test en Fable 5— y el candado de tres puntas mantuvo la suite en
  rojo hasta que se decidiera. Después el techo: durante unas horas se retiró
  `claude-fable-5` de la jerarquía y se escribió aquí que Opus 5 era "a la vez
  el punto de partida y el techo". El operador lo revirtió el mismo día
  (`b3f9cfb`), pero **ese párrafo sobrevivió en esta sección** y estuvo
  contradiciendo al reparto operativo de arriba hasta el 2026-09-01, cuando la
  auditoría integral lo detectó. Se deja anotado porque es el modo de fallo
  exacto que este archivo existe para impedir: la política se corrigió en un
  sitio y no en el otro, y ningún test cubría la contradicción entre secciones.
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

## REGLA DE DESPACHO: el mecanismo que aplica esta política

Todo lo de arriba dice *qué* modelo corresponde a cada clase de tarea; esta
sección fija *por qué mecanismo* se aplica, porque una política sin mecanismo no
se ejecuta nunca. Auditado el 2026-09-01: 26 de 27 subagentes declaraban
`model: opus` en su frontmatter, nadie pasaba nunca un modelo al delegar, y
"delegar por complejidad" simplemente no ocurría.

**El mecanismo es el parámetro `model` de la herramienta `Agent`.** Acepta
`sonnet | opus | haiku | fable` y tiene **precedencia sobre el frontmatter** del
subagente. Es el único punto del harness donde la sesión asigna modelo de verdad
al delegar; la tabla, el hook y el frontmatter son valores por defecto que este
parámetro sobreescribe cuando la política lo exige.

Reglas de despacho, en orden de precedencia:

1. **Las cinco clases del disparador de escalado van a `claude-fable-5-1`.** Si
   la tarea delegada cae en cualquiera de las cinco clases, se despacha con
   `model: "fable"`, diga lo que diga la ruta, la tabla o el frontmatter, y el
   escalado se registra en `current-task.md`. `fable` no aparece — a propósito —
   ni en `model-routing.json` ni en ningún frontmatter: las cinco clases no son
   léxicas y ningún clasificador por palabras clave puede asignarlas; **solo
   esta regla despacha a Fable 5.1**, y por eso sin ella el techo de la política
   era inalcanzable en la práctica.

   El parámetro que se pasa sigue siendo el alias corto `"fable"`, no el ID
   completo: el `model` de la herramienta `Agent` es un **enum**
   (`sonnet | opus | haiku | fable`) y no admite un identificador de modelo.

   **El alias entrega Fable 5.1 — VERIFICADO POR OBSERVACIÓN el 2026-09-04.**
   No por inferencia: se despachó una consulta mínima con `--model fable` y se
   leyó qué modelo respondió en el transcript de esa sesión. Resultado:
   `claude-fable-5-1`.

   Hubo brecha ese mismo día y conviene saber por qué, porque es la condición
   que hay que revisar si vuelve a aparecer. La documentación de Claude Code
   dice que `fable` resuelve a Fable 5.1 *"unless you set
   `ANTHROPIC_DEFAULT_FABLE_MODEL`"*, y añade: ***"Before v2.1.255, it resolved
   to Fable 5"***. La máquina corría **2.1.179**, por debajo del umbral, así que
   el techo declarado aquí era **inalcanzable por la vía de la delegación**: el
   `model` de la herramienta `Agent` es un enum (`sonnet | opus | haiku | fable`)
   y no admite un ID, de modo que no había forma de pedir `claude-fable-5-1` al
   despachar. Se actualizó a **2.1.261** por orden del operador y la brecha
   cerró.

   Las dos condiciones que la reabrirían, en orden de comprobación:

   - `claude --version` por debajo de **2.1.255**;
   - `ANTHROPIC_DEFAULT_FABLE_MODEL` definido apuntando a otro modelo.

   Lo que NO se hizo, y es deliberado: bajar el techo a `claude-fable-5` para
   que encajara con lo que la máquina entregaba. Faltaba una actualización del
   entorno, no sobraba política. Ajustar la política al nivel de la herramienta
   invierte la relación que este archivo existe para sostener.

   No hay test que fije esto: dependería de la versión del binario instalado y
   saldría verde en CI y rojo en la máquina que opera, o al revés. Se re-verifica
   a mano con los dos comandos de arriba.
2. **Trabajo normal delegado**: se pasa `model` con el escalón de la ruta
   aplicable de `model-routing.json` (`opus` solo full-audit/incident/
   quant-incident; `haiku` solo documentation; `sonnet` el resto). Pasar el
   modelo de la propia ruta no es la "excepción" del párrafo anterior y no
   requiere registro; registrar aplica cuando el modelo pasado diverge de la
   ruta (los escalados de la regla 1).
3. **Sin ruta aplicable ni disparador**: `sonnet` (la ruta `default`). La tabla
   sigue siendo el suelo, nunca el techo.

Estado de los otros dos artefactos, dicho sin ambigüedad para que no vuelvan a
leerse como reglas paralelas:

- La columna `model` de `model-routing.json` no la aplica ningún componente
  automáticamente: es la **entrada de la regla 2**, que ejecuta quien delega.
- El clasificador `route_classifier.py` es consultivo y ya no es un hook (ver
  arriba: retirado el 2026-09-01). Tuvo
  un downgrade oculto `opus`→`sonnet` por prioridad, no documentado en ninguna
  parte, que se eliminó el 2026-09-01: el hook lee `route["model"]` y **no lo
  reinterpreta**. La tabla es la única fuente de modelo por ruta y el candado de
  `tests/test_claude_model_routing.py` fija ambas cosas.

Este archivo es la fuente única de la política de modelos. `ORCHESTRATOR.md` y
`decision-engine.md` enlazan aquí en lugar de repetirla. Cambiar el modelo
principal o la política de subagentes requiere aprobación humana explícita y una
actualización deliberada de las pruebas de routing.

La clasificación por palabras clave es una ayuda determinista. El decision
engine, la semántica real de la solicitud y las reglas permanentes conservan
precedencia.
