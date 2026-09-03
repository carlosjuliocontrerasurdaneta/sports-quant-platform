---
name: full-audit
description: >
  Auditar exhaustivamente repositorios y proyectos de software sin modificar archivos
  durante el diagnóstico. Usar cuando el usuario solicite una auditoría completa,
  revisión integral, full audit, full system audit, detección general de bugs, riesgos,
  vulnerabilidades, problemas de arquitectura, dependencias, configuración, pruebas,
  scripts, datos, modelos cuantitativos, integraciones externas o sistemas de Skills e
  instrucciones del proyecto. Inventariar primero
  el proyecto, documentar evidencia reproducible, validar de forma independiente cada
  candidato, clasificar los hallazgos por severidad, confianza y estado de evidencia,
  preparar un plan de corrección y esperar aprobación explícita antes de implementar
  cualquier cambio. La activación de esta skill autoriza únicamente diagnóstico,
  validación y planificación; nunca autoriza por sí sola la modificación de archivos.
---

# Full Audit

## Objetivo

Analizar exhaustivamente el proyecto para detectar:

- defectos funcionales;
- errores lógicos;
- riesgos de ejecución;
- vulnerabilidades;
- problemas de datos;
- deuda técnica;
- inconsistencias arquitectónicas;
- fallos de configuración;
- problemas de dependencias;
- deficiencias de pruebas;
- riesgos en integraciones externas;
- defectos en código cuantitativo o de machine learning cuando corresponda;
- defectos del sistema de Skills, instrucciones, routing u orquestación cuando exista;
- archivos, directorios, recursos o artefactos obsoletos, redundantes, huérfanos o innecesarios cuando exista evidencia suficiente.

Distinguir siempre entre:

- candidatos de auditoría;
- hallazgos confirmados;
- hallazgos inferidos;
- hallazgos detectados por herramientas;
- elementos no verificables en el entorno;
- falsos positivos descartados.

No modificar archivos durante las fases de descubrimiento, auditoría, validación y planificación.

## Principio de autorización

La activación de esta skill autoriza únicamente:

1. descubrimiento;
2. inventario;
3. auditoría;
4. validación;
5. planificación.

No autoriza automáticamente:

- editar archivos;
- aplicar parches;
- actualizar dependencias;
- ejecutar migraciones;
- modificar datos;
- efectuar escrituras externas;
- cambiar configuración;
- hacer commits;
- hacer pushes;
- hacer merges;
- desplegar;
- liberar versiones.

La fase de corrección requiere una autorización posterior, explícita y separada.

---

# Reglas de autoridad y seguridad

Antes de auditar:

1. Leer `AGENTS.md` y cualquier instrucción específica del repositorio.
2. Inspeccionar el estado de Git cuando esté disponible.
3. Identificar cambios preexistentes.
4. No sobrescribir, revertir ni descartar modificaciones del usuario.
5. Respetar las instrucciones más específicas aplicables a cada directorio.
6. Determinar qué acciones están autorizadas por la solicitud del usuario.
7. Interpretar solicitudes de auditar, revisar, analizar, diagnosticar o buscar errores como autorización de solo lectura.
8. No tratar una solicitud de auditoría como autorización para modificar código.
9. No instalar, actualizar ni eliminar dependencias salvo autorización expresa.
10. No ejecutar operaciones destructivas.
11. No operar sobre producción, servicios de pago, datos reales o recursos externos con efectos persistentes.
12. No ejecutar pruebas, scripts, builds o herramientas sin evaluar previamente si pueden:
    - escribir archivos;
    - modificar bases de datos;
    - crear recursos;
    - consumir APIs;
    - enviar mensajes;
    - desplegar;
    - cambiar configuración;
    - alterar servicios externos.
13. Preferir modos de ejecución de solo lectura, dry-run, no-write, sandbox, temporales o aislados cuando estén disponibles.

## Política de comandos

### Preferidos durante la auditoría

Cuando sean aplicables y seguros:

- `git status`
- `git diff`
- `git log`
- `git show`
- `rg`
- `grep`
- `find`
- `cat`
- `head`
- `tail`
- inspección de manifiestos;
- linters en modo no-write;
- type checkers;
- analizadores estáticos;
- dependency scanners en modo de solo lectura;
- comandos de descubrimiento o colección que no ejecuten lógica de negocio.

### Requieren evaluación previa de efectos

Antes de ejecutarlos, determinar su comportamiento real:

- suites de tests;
- builds;
- scripts del repositorio;
- package managers;
- generadores;
- contenedores;
- `docker compose`;
- tareas Make;
- herramientas de infraestructura;
- notebooks;
- jobs de ML;
- scripts de base de datos.

### Prohibidos durante la auditoría salvo autorización expresa

Entre otros:

- `git clean`
- `git reset`
- restauraciones destructivas;
- eliminación de archivos;
- formatters con escritura;
- migraciones;
- escrituras a bases de datos reales;
- despliegues;
- releases;
- llamadas externas mutativas;
- rotación o modificación de credenciales;
- cambios en producción.

---

---

# Arquitectura modular y carga progresiva

`SKILL.md` es el controlador de la auditoría. El detalle operativo vive en `references/` y debe cargarse únicamente cuando corresponda.

Todos los archivos de referencia están enlazados directamente desde este archivo. No introducir cadenas de referencias de segundo nivel para reglas necesarias.

## Precedencia interna

Si existe una aparente contradicción:

1. las instrucciones del repositorio y del sistema tienen precedencia;
2. las reglas de autorización y seguridad de este `SKILL.md` prevalecen sobre cualquier referencia;
3. una regla especializada de una referencia aplicable prevalece sobre una regla genérica, pero nunca puede ampliar autoridad;
4. ninguna referencia convierte diagnóstico en autorización de escritura.

## Referencias obligatorias y condicionales

### Fase 0 — siempre

Leer [references/discovery-coverage.md](references/discovery-coverage.md).

Construir el inventario y la matriz de cobertura antes de declarar que la auditoría es exhaustiva.

### Fase 1 — áreas generales

Leer [references/audit-areas.md](references/audit-areas.md).

Aplicar únicamente las áreas relevantes al stack detectado, manteniendo una disposición explícita para todas las áreas inventariadas.

### Fase 1 — sistema de Skills e instrucciones

Si el proyecto contiene Skills, prompts persistentes, agentes, loops, comandos, routing u otros archivos de control de asistentes, leer [references/skills-instructions.md](references/skills-instructions.md).

Si no existe un sistema equivalente, marcar esta área como `NO_APLICABLE`.

### Fase 1 — limpieza y racionalización

Leer [references/repository-cleanup.md](references/repository-cleanup.md).

Esta revisión forma parte del `full-audit`: debe detectar residuos, duplicados, elementos obsoletos y artefactos innecesarios con evidencia. La ausencia de referencias textuales nunca basta por sí sola para proponer eliminación.

### Fase 1 — cuantitativo / ML

Si existen modelos estadísticos, machine learning, calibración, backtesting o decisiones cuantitativas, leer [references/quant-ml.md](references/quant-ml.md).

Si no aplican, marcar el área como `NO_APLICABLE`.

### Clasificación de cualquier candidato — siempre antes de reportarlo

Leer [references/evidence-findings.md](references/evidence-findings.md) antes de clasificar candidatos, asignar severidad/confianza o presentar un defecto como confirmado.

Regla esencial:

`CONFIRMADO = REPRODUCIDO OR VERIFICADO_ESTÁTICAMENTE`

`DETECTADO_POR_HERRAMIENTA` es intermedio y nunca puede permanecer como estado final.

### Fases 2–5

Leer [references/validation-remediation.md](references/validation-remediation.md).

La Fase 2 revalida de forma independiente. La Fase 3 prepara el plan. La Fase 4 solo se ejecuta después de autorización explícita y separada. La Fase 5 valida las correcciones realmente realizadas.

### Modo orquestado

Cuando corresponda, leer [references/orchestration.md](references/orchestration.md).

No asumir que un especialista existe por estar nombrado y no delegar dos veces el mismo trabajo sin una finalidad de validación cruzada.

### Informe final

Antes de consolidar la salida, leer [references/reporting.md](references/reporting.md).

El informe debe mantener separados:

- confirmados;
- inferidos;
- no verificables;
- detecciones de herramientas pendientes;
- falsos positivos descartados.

---

# Flujo operativo obligatorio

## Fase 0 — Descubrimiento

1. Aplicar las reglas de autoridad y seguridad.
2. Leer la referencia de descubrimiento y cobertura.
3. Inventariar el proyecto.
4. Estratificar por criticidad cuando el tamaño lo requiera.
5. Crear la matriz de cobertura.
6. No buscar "exhaustividad" mediante ejecución indiscriminada de comandos.

## Fase 1 — Auditoría

1. Leer las referencias aplicables.
2. Tratar todo posible defecto inicialmente como `CANDIDATO`.
3. Cubrir las áreas generales.
4. Cubrir Skills/instrucciones cuando existan.
5. Ejecutar la revisión de limpieza y racionalización.
6. Cubrir cuantitativo/ML cuando aplique.
7. No modificar archivos.
8. No presentar candidatos como defectos confirmados antes de Fase 2.

## Fase 2 — Validación independiente

1. Leer la taxonomía de evidencia y la referencia de validación.
2. Revalidar cada candidato mediante evidencia adicional independiente.
3. Buscar protecciones, contraejemplos y comportamiento intencional.
4. Asignar un estado final permitido.
5. Conservar los falsos positivos relevantes con la evidencia que los refutó.

## Fase 3 — Plan

1. Preparar un plan priorizado para hallazgos confirmados.
2. Relacionar cada acción con IDs, archivos, riesgos, pruebas y criterio de aceptación.
3. Para eliminaciones, exigir la evidencia adicional definida en la referencia de limpieza.
4. Entregar el informe.
5. Detenerse y esperar aprobación explícita.

## Fase 4 — Corrección

Ejecutar únicamente tras aprobación separada e inequívoca.

1. Revalidar que el árbol y la evidencia siguen vigentes.
2. Confirmar IDs o alcance aprobado.
3. Aplicar el parche mínimo.
4. No ampliar el alcance por conveniencia.
5. No eliminar elementos `NO_VERIFICABLE`.
6. Detenerse si aparece una nueva dependencia, ambigüedad o requisito de autorización.

## Fase 5 — Validación final

1. Ejecutar validaciones específicas y regresión relevante cuando sean seguras.
2. Revisar el diff.
3. Separar fallos preexistentes de regresiones introducidas.
4. Si hubo eliminaciones, buscar referencias rotas y validar consumidores.
5. No afirmar éxito sobre comprobaciones no ejecutadas.

---

# Carga mínima por tipo de tarea

Una solicitud de `full audit` normalmente requiere, en orden:

1. `references/discovery-coverage.md`;
2. `references/audit-areas.md`;
3. `references/repository-cleanup.md`;
4. las referencias condicionales aplicables;
5. `references/evidence-findings.md`;
6. `references/validation-remediation.md`;
7. `references/orchestration.md` si se activa el modo orquestado;
8. `references/reporting.md` al consolidar el informe.

No cargar de entrada todas las referencias si todavía no son necesarias. Mantener el contexto enfocado, pero no omitir una referencia obligatoria antes de ejecutar la fase que gobierna.

---

# Criterio de finalización

## Auditoría completada

Considerar completada la auditoría cuando:

- exista un inventario verificable;
- toda área inventariada tenga una disposición en la matriz de cobertura;
- todos los candidatos relevantes hayan sido revalidados;
- los hallazgos confirmados estén separados de inferidos y no verificables;
- los falsos positivos relevantes estén identificados;
- los límites de la revisión estén declarados;
- exista un plan priorizado;
- no se hayan modificado archivos.

## Corrección completada

Considerar completada la corrección cuando:

- se hayan tratado únicamente los IDs aprobados;
- las pruebas específicas hayan sido ejecutadas cuando sean viables;
- no existan regresiones atribuibles conocidas;
- el diff final haya sido revisado;
- los riesgos pendientes estén documentados;
- las limitaciones estén documentadas;
- las validaciones no ejecutadas estén declaradas;
- no se afirme éxito sobre comprobaciones no realizadas;
- si hubo eliminaciones, todas las rutas eliminadas correspondan a candidatos aprobados y no existan referencias rotas o regresiones atribuibles conocidas.

---

# Restricciones finales

- No modificar archivos automáticamente durante la auditoría.
- No realizar refactorizaciones masivas sin aprobación.
- No cambiar modelos, estrategias, parámetros ni criterios de negocio sin autorización explícita.
- No alterar producción, servicios externos, bases de datos reales ni credenciales.
- No ejecutar commits, pushes, merges, releases o deployments sin solicitud expresa.
- No ocultar fallos.
- No debilitar validaciones.
- No presentar inferencias como hechos confirmados.
- No convertir automáticamente alertas de herramientas en defectos confirmados.
- No inflar la severidad sin evidencia causal.
- No inflar el número de hallazgos separando artificialmente manifestaciones de una misma causa raíz.
- No declarar un archivo eliminable únicamente por ausencia de referencias textuales.
- No eliminar archivos, directorios o recursos sin evidencia suficiente y aprobación explícita.
- No declarar cobertura total sin matriz verificable.
- Priorizar precisión, evidencia, trazabilidad y reproducibilidad sobre velocidad.
- Documentar toda modificación relevante cuando la fase de corrección haya sido autorizada.
