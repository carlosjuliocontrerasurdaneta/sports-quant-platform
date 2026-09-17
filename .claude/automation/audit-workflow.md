# Contrato de auditoría

Fuente canónica para skills, loops y prompts de auditoría. Los prompts de
`audits/prompts/` se generan con `python scripts/sync_agent_instructions.py --write`;
`--check` detecta deriva sin escribir. Las instrucciones aplicables del repositorio
y la petición del usuario tienen precedencia. Los informes históricos no se generan.

<!-- section: common -->
## Autoridad, alcance y evidencia

Leer `AGENTS.md` y las instrucciones aplicables; inspeccionar Git y separar los
cambios preexistentes. Registrar alcance, exclusiones, base Git y limitaciones.
El código/configuración actual es la fuente de verdad, los informes son evidencia
secundaria. No asumir que otro auditor, un test verde o una alerta de herramienta
demuestran corrección. No inventar ejecuciones, datos, umbrales ni resultados.

Diagnóstico, consolidación y verificación son de solo lectura del proyecto:
solo escribir los entregables de la fase, su histórico y el registro de tarea
cuando esté autorizado. No cambiar fuentes, tests, configuración, dependencias,
datos productivos ni credenciales para conseguir una validación satisfactoria.
Evaluar los efectos de comandos antes de ejecutarlos; usar temporales/aislamiento.
No instalar dependencias, consumir servicios de pago, efectuar escrituras externas,
commits, pushes, releases o despliegues sin autorización específica.
No mostrar secretos completos; registrar tipo y ubicación, nunca utilizarlos.

Validar primero lo más acotado. En este entorno usar pytest con
`-p no:cacheprovider --basetemp=.codex-tmp/pytest`; inspeccionar Make/BAT/builds
antes de ejecutarlos. Registrar comando, código de salida y evidencia, distinguiendo
`NEW_REGRESSION`, `PRE_EXISTING_FAILURE`, `ENVIRONMENTAL_FAILURE`, `NOT_VERIFIABLE`.
Un control configurado no demuestra que esté pasando: comprobar su estado actual
o declarar la limitación. No modificar ni eliminar datos para probar una hipótesis.

## Contrato de hallazgos

Usar la taxonomía de `AGENTS.md`:

- Evidencia: `REPRODUCED`, `STATICALLY_VERIFIED`, `TOOL_DETECTED`, `INFERRED`,
  `NOT_VERIFIABLE`, `DISMISSED`.
- Solo `REPRODUCED` y `STATICALLY_VERIFIED` son defectos confirmados.
  `TOOL_DETECTED` requiere revisión independiente; si falta evidencia,
  reclasificar como `INFERRED` o `NOT_VERIFIABLE`, sin fingir confirmación.
- Confianza: `HIGH`, `MEDIUM`, `LOW`; un candidato `LOW` no se confirma.
- Severidad por impacto demostrado: `CRITICAL` (sistémico/catastrófico),
  `HIGH` (considerable), `MEDIUM` (limitado/condicionado), `LOW` (menor).
  La frecuencia y la confianza no rebajan la severidad del impacto alcanzable.
  Comprobar controles compensatorios antes de afirmar ese impacto.
- Prioridad independiente: P0 inmediata, P1 urgente, P2 planificada,
  P3 mantenimiento, P4 opcional. Las observaciones informativas van aparte.

Cada hallazgo incluye ID, título, categoría, severidad, confianza, evidencia,
archivo/línea, activación, problema, evidencia concreta, esperado, observado,
causa raíz, consecuencia, corrección mínima, pruebas necesarias y limitaciones.
Añadir controles existentes, criterio de aceptación y prioridad para remediación.
Declarar explícitamente los campos no verificables. Agrupar por causa raíz;
separar solo problemas con impacto o solución materialmente distintos.
No convertir estilo, TODO, complejidad, antigüedad o baja cobertura en defectos
sin consecuencia demostrable. Conservar descartes relevantes y su explicación.

IDs estables dentro de una ronda: auditores `CLAUDE-001` / `OPENAI-001`,
consolidado `AUD-001`, regresiones `REG-001`. La identidad completa es
`round_id + ID`; no reiniciar ni renumerar dentro de la ronda ni cambiar IDs
cuando cambia la severidad. Registrar alias de origen en la consolidación.
Los IDs históricos (`AUD-MED-001`, etc.) se conservan tal como fueron emitidos.
Al leer informes legacy, normalizar etiquetas equivalentes sin elevar evidencia:
REPRODUCIDO → REPRODUCED, VERIFICADO_ESTÁTICAMENTE → STATICALLY_VERIFIED,
DETECTADO_POR_HERRAMIENTA → TOOL_DETECTED, INFERIDO → INFERRED,
NO_VERIFICABLE → NOT_VERIFIABLE, DESCARTADO → DISMISSED. Conservar la etiqueta
original como origen y revalidar el hallazgo; una etiqueta «confirmado» sin
evidencia suficiente no adquiere confirmación por la conversión.

La antigua puntuación ponderada es solo información histórica de riesgo:
no convertirla en severidad ni exigir recalcularla en rondas nuevas. Un impacto
catastrófico demostrado sigue siendo CRITICAL aunque su activación sea rara.

## Rondas, archivos y compatibilidad

Para nuevas rondas, usar `audit/latest/` y un `round_id` único registrado en
`MANIFEST.json`. El coordinador inicializa el manifest antes del diagnóstico;
en una ejecución individual el mismo agente puede preparar la ronda sin leer
conclusiones históricas (preservación mediante copia/hashes). Antes de iniciar
una ronda distinta, un único coordinador copia
íntegramente la ronda anterior a `audit/<round_id-anterior>/`, comprueba igualdad
de archivos/contenidos y solo después reemplaza los entregables de `latest`.
No sobrescribir históricos. Si el ID es ambiguo, hay un escritor activo o falla
la preservación, no sobrescribir: registrar bloqueo. Un segundo auditor de la
misma ronda no reinicia ni archiva la ronda que está evaluando.

| Fase | Entradas | Entregables dentro de `audit/latest/` |
|---|---|---|
| Diagnóstico independiente | Repositorio y alcance | `claude/REPORT.md` o `openai/REPORT.md`, más `EVIDENCE.json` en ese subdirectorio |
| Consolidación | Informes de los auditores de la misma ronda | `FINDINGS.md`, `BACKLOG.md`, `MANIFEST.json` |
| Remediación autorizada | Hallazgos y alcance aprobado | `CHANGES.md`, `VALIDATION.md`, `STATUS.md`; actualización del manifest |
| Verificación independiente | Hallazgos, cambios y evidencia actual | `VERIFICATION.md`, `STATUS.md`; actualización del manifest |

El manifest registra `round_id`, fecha UTC, alcance, base/working tree, rutas y
hashes de informes fuente, auditores disponibles, `tests_initial`, `tests_final`,
`files_modified`, `final_result`, `final_result_rationale` y campos no disponibles.
Los auditores escriben únicamente su subdirectorio y anotan allí comandos,
códigos de salida, base y cobertura en `EVIDENCE.json`; el coordinador integra
estos registros en el manifest sin permitir escrituras concurrentes sobre él.
Con un solo auditor autorizado, consolidar tras su diagnóstico y declarar que
no hubo segunda opinión; nunca inventar un informe del auditor ausente.

`FINDINGS.md` es la línea base de diagnóstico: remediación/verificación no borran
ni reescriben hallazgos para simular su cierre. `STATUS.md` relaciona ID, estado
de remediación, estado de verificación, evidencia y próxima acción. La fase que
lo actualiza preserva las columnas/evidencia de las fases anteriores.
Antes de reemplazar un entregable de la misma ronda, guardar su versión previa
en `history/<fase>-<fecha-UTC-unica>/` dentro de la ronda y verificar la copia.

Compatibilidad: aceptar como entrada explícita los informes existentes en
`audits/claude/`, `audits/openai/`, `audits/consolidated/`, `audits/remediation/`,
`audits/verification/` y el antiguo `audit/latest/`. Registrar ruta, hash e IDs
originales; no mover, renombrar ni modificar esos históricos. Si se continúa
una ronda legacy, usar sus IDs y dejar los nuevos entregables en una ronda
canónica preservada por el procedimiento anterior. No seleccionar por mtime ni
mezclar automáticamente informes de distinta base/alcance: pedir identificar
la fuente si no puede resolverse de la solicitud. Campos ausentes son
`NOT_VERIFIABLE`, nunca una razón para inventar evidencia o cerrar un hallazgo.
<!-- endsection -->

<!-- section: review -->
## Diagnóstico independiente

1. Inventariar el alcance y construir matriz con componentes, criticidad,
   método, evidencia y estado: revisado, parcial, no aplicable, no verificable
   o excluido con motivo. No prometer cobertura total sin demostrarla.
2. Durante el análisis principal no leer informes del otro auditor ni
   consolidados/estados históricos. Si el contexto ya contiene sus conclusiones,
   declarar la contaminación o iniciar una revisión independiente nueva.
3. Reconstruir flujos y revisar las áreas aplicables:
   arquitectura/contratos; lógica, unidades y casos límite; seguridad/secretos;
   integridad, migraciones, atomicidad y concurrencia; APIs, errores, reintentos
   y cuota; recursos/rendimiento demostrable; pruebas discriminantes; dependencias;
   CI, infraestructura, observabilidad y estado efectivo de los controles.
4. En cuantitativo: leakage temporal/target, splits, información disponible
   al cutoff de predicción, timestamps y frescura canónica, probabilidades finitas
   y normalizadas, calibración OOS, incertidumbre, selección de muestras y
   backtesting con costos/voids/ejecución realistas. Separar ROI esperado,
   ROI realizado y acierto; no afirmar rentabilidad por aprobar tests.
5. Revisar skills/loops/prompts/routing como contratos: consumidores, referencias,
   autoridad, entradas/salidas y estados. Para retirar archivos comprobar imports,
   carga dinámica, entrypoints, scripts, empaquetado, documentación y compatibilidad;
   ausencia de referencias textuales no demuestra que sean eliminables.
6. Revalidar cada candidato mediante evidencia adicional independiente: callers,
   tests, configuración, controles compensatorios o reproducción segura. Una
   segunda opinión aporta evidencia, no confirma automáticamente el hallazgo.
7. Tras fijar conclusiones propias, comparar el histórico cuando exista:
   nuevo, persistente, corregido, regresión o no verificable; revalidar cada ID.
8. Entregar informe con resumen, alcance, inventario/cobertura, hallazgos confirmados,
   inferidos/no verificables, descartes, validaciones y comandos, plan priorizado,
   criterios de aceptación, pruebas, riesgos residuales y limitaciones.

Para auditoría focalizada aplicar los mismos criterios al diff/módulos pedidos;
no expandir a todo el repositorio ni reportar defectos ajenos al alcance.
Para una auditoría integral ampliar con las referencias especializadas de
`.claude/skills/full-audit/references/`, según el stack y área encontrada.
No corregir durante el diagnóstico. Informar al terminar ruta, conteos por
severidad, P0/P1 y limitaciones; no emitir PASS incondicional con evidencia crítica ausente.
<!-- endsection -->

<!-- section: consolidate -->
## Consolidación independiente

Leer los informes fuente completos, comprobar ronda/base/alcance y preservar sus
IDs y hashes. No asumir equivalencia por título ni confirmación por coincidencia.
Contrastar con el código actual discrepancias, críticos/altos, P0/P1 y exclusivos
relevantes. Si el código cambió, registrar base y revalidar la afirmación.

Clasificar origen: ambos, exclusivo Claude, exclusivo OpenAI, coincidencia parcial,
falso positivo o no verificable. Mantener esta dimensión separada del estado de
evidencia. Agrupar por causa raíz, documentar discrepancias y por qué se descartan.
Asignar IDs consolidados estables y mapear todos sus IDs fuente; no promediar
severidad/confianza. Mantener observaciones y deuda separadas de defectos.

Producir `FINDINGS.md` y backlog por prioridad, impacto, dependencias y riesgo:
ID, cambio mínimo, archivos, pruebas, criterio de aceptación y autorización
pendiente. Incluir métricas de confirmados, descartados y no verificables, cobertura,
validaciones, limitaciones y comparación histórica. No medir la calidad de los
auditores por número de hallazgos. Consolidar no autoriza correcciones.
<!-- endsection -->

<!-- section: remediate -->
## Remediación autorizada

La petición del usuario debe identificar el informe y el alcance a corregir
(IDs, grupo inequívoco o todos los confirmados). La autorización ya concedida
en la sesión sigue siendo válida para ese alcance; no exigir que se repita.
Si no hay fuente o el alcance es ambiguo, resolverlo antes de editar. Una
auditoría por sí sola no autoriza correcciones ni operaciones externas.

1. Leer hallazgos/backlog (o fuente legacy explícita); registrar base Git, cambios
   locales y validaciones iniciales antes de corregir. No pisar trabajo existente.
2. Revalidar cada ID: confirmado, ya corregido, parcial, no reproducible,
   no aplicable o requiere información. No modificar código por un falso positivo.
3. Preparar lotes pequeños por causa/solución. Aplicar el parche mínimo autorizado;
   preservar interfaces, datos históricos y comportamiento correcto. No mezclar
   refactors, limpieza o actualizaciones de dependencias ajenas al defecto.
4. Añadir una prueba discriminante cuando el defecto sea automatizable. Demostrar
   fallo antes y éxito después, o registrar motivo y evidencia equivalente si no
   es seguro. No debilitar assertions, validaciones o seguridad para obtener verde.
5. Validar por lote: caso del defecto, componente, regresión y checks pertinentes.
   Inspeccionar los comandos Make/BAT por separado; una suite Python no los cubre.
   Ejecutar la suite global solo cuando aporte evidencia relevante y sea segura.
6. Revisar diff y efectos de hooks/autofixes realmente observados; registrar
   cambios relacionados, comandos/códigos, criterios cumplidos y fallos preexistentes.
7. Detener el ID bloqueado, documentar qué falta y continuar con los demás IDs
   independientes autorizados. No marcar resuelto algo sin evidencia.

Cambios de riesgo/modelo/promoción, producción, credenciales, cuota de pago,
migraciones irreversibles y eliminaciones requieren el alcance específico
autorizado por el usuario y las reglas del repositorio. No inferirlo del backlog.
Para eliminar, volver a comprobar rutas, consumidores y ausencia de cambios
preexistentes no autorizados; nunca retirar un elemento ambiguo/no verificable.

En `CHANGES.md` registrar por ID: estado inicial, causa, archivos, cambio,
prueba, aceptación, riesgos residuales y estado final (pendiente de verificación,
parcial, bloqueado o no aplicable). En `VALIDATION.md` registrar evidencia real.
Actualizar estado sin alterar la línea base. Cumplir el bookkeeping aplicable
de `CLAUDE.md`/Obsidian y registrar limitaciones. La implementación validada queda
pendiente de verificación independiente; no declarar el proyecto libre de errores.
<!-- endsection -->

<!-- section: verify -->
## Verificación independiente

No asumir corrección por un commit, un diff o un test verde. No editar código,
tests ni configuración para hacer pasar esta fase. Contrastar hallazgos y
remediación con el código actual, especialmente todos los IDs declarados corregidos
o pendientes de verificación; revisar bloqueados/no aplicables según evidencia.

Por ID: reconstruir causa/activación original, inspeccionar parche y callers,
reproducir cuando sea seguro, ejecutar tests relevantes y verificar explícitamente
cada criterio. Buscar regresiones, bypass, síntomas ocultados y fallos trasladados.
En seguridad revisar rutas alternativas; en datos, compatibilidad e integridad;
en concurrencia, corrección estructural además de reproducciones; en rendimiento,
medidas pertinentes o límites claros. Validación global razonable al finalizar.

Estados: verificado-corregido, verificado-mitigado (riesgo residual explícito),
reabierto, regresión, no verificable o no aplicable con evidencia. Solo cerrar
como corregido si se resolvió la causa, el escenario ya no falla, se cumplen
criterios y pruebas relevantes, sin regresión relacionada conocida ni traslado.
Nuevas regresiones reciben `REG-###` y relación con el ID original.

Evaluar el backlog completo de la ronda, incluidos bloqueados originales y
regresiones. Declarar exclusiones sin convertirlas en cierres. Elegir la primera
regla aplicable:

1. **NO APTO**: P0/P1 material abierto, original o introducido, regresión grave
   o evidencia de corrección importante inválida. Prevalece aunque también falte
   evidencia en otras áreas; informar esas limitaciones.
2. **VERIFICACIÓN INCOMPLETA**: sin bloqueo confirmado anterior, falta evidencia
   de algún hallazgo o validación relevante del alcance.
3. **APTO CON PENDIENTES**: evidencia suficiente, validaciones satisfactorias,
   sin bloqueos anteriores, pero con hallazgos menores o riesgos por seguir.
4. **APTO**: evidencia suficiente, validaciones satisfactorias y ningún hallazgo
   o riesgo residual pendiente de seguimiento dentro del alcance evaluado.

Casos: P1 original bloqueado + tests verdes → NO APTO; P1 nuevo → NO APTO;
P1 confirmado + validación incompleta → NO APTO con limitaciones; sin bloqueo
confirmado + evidencia faltante → VERIFICACIÓN INCOMPLETA; solo P2 pendiente
con evidencia suficiente → APTO CON PENDIENTES; todo cerrado con evidencia → APTO.

`VERIFICATION.md` incluye alcance, metodología, estado/evidencia por ID, regresiones,
validación global, P0/P1 abiertos, limitaciones y próxima acción. Actualizar
`STATUS.md` y manifest preservando historia. APTO solo califica la remediación
evaluada, no garantiza ausencia absoluta de defectos ni rentabilidad.
<!-- endsection -->
