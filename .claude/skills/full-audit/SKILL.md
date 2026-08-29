---
name: full-audit
description: Audita de forma integral y de solo lectura un repositorio o proyecto completo. Produce inventario, matriz de cobertura, hallazgos con evidencia reproducible, validación independiente y plan priorizado. Usar cuando el usuario solicite explícitamente una auditoría completa, integral, full audit o full system audit. No usar para revisar un único archivo, PR, bug o cambio puntual.
when_to_use: Activar cuando el alcance sea el sistema completo o varias áreas coordinadas. No activar para implementar fixes, features o revisiones aisladas salvo que el usuario pida además una auditoría integral.
argument-hint: "[alcance opcional]"
---

# Full Audit

## Objetivo

Auditar exhaustivamente el proyecto para identificar defectos funcionales, errores lógicos, vulnerabilidades, riesgos operacionales, problemas de datos, inconsistencias y deuda técnica con impacto demostrable.

Priorizar precisión, evidencia y cobertura verificable sobre cantidad de observaciones o velocidad.

## Integración con `CLAUDE.md`

Esta skill complementa las reglas globales de `CLAUDE.md`.

Durante las fases 0–3:

- las restricciones de solo lectura de esta skill prevalecen sobre cualquier comando general de validación descrito en `CLAUDE.md`;
- un comando recomendado por `CLAUDE.md` sólo puede ejecutarse si sus efectos son compatibles con esta política de solo lectura;
- las reglas cuantitativas globales de `CLAUDE.md` siguen siendo aplicables;
- no interpretar las reglas de implementación de `CLAUDE.md` como autorización para corregir hallazgos.

Después de una corrección autorizada en Fase 4, las actualizaciones de registro exigidas por `CLAUDE.md` (por ejemplo, notas Obsidian de la misma sesión) están permitidas como bookkeeping obligatorio y no amplían el alcance funcional de la corrección. Si la ubicación o convención requerida no puede determinarse con seguridad, reportar la limitación y no adivinar.

## Reglas obligatorias

1. **Solo lectura durante diagnóstico.** No modificar código, configuración, datos, dependencias ni archivos del proyecto en descubrimiento, auditoría, validación o planificación.
2. **Preservar estado existente.** No sobrescribir, revertir, limpiar ni descartar cambios preexistentes.
3. **Evidencia antes que inferencia.** No presentar hipótesis o resultados de herramientas como defectos confirmados.
4. **Validación independiente.** Revalidar cada hallazgo relevante mediante otro método cuando sea viable.
5. **Cobertura explícita.** No llamar “exhaustiva” a la auditoría sin matriz de cobertura.
6. **Auditar no autoriza corregir.** Esperar aprobación explícita antes de modificar el proyecto.
7. **Sin acciones externas o destructivas.** No alterar producción, repositorios remotos, servicios, bases reales ni recursos de pago.
8. **No exponer secretos.** Reportar tipo y ubicación; redactar el valor.
9. **No inventar evidencia.** No inventar archivos, líneas, comandos, resultados, errores ni comportamientos.
10. **No afirmar éxito no comprobado.**

## Autoridad y preflight

Antes de auditar:

1. Leer `AGENTS.md`, `CLAUDE.md` y reglas específicas aplicables.
2. Inspeccionar Git cuando esté disponible: estado, cambios preexistentes y archivos no versionados relevantes.
3. Determinar alcance, exclusiones y acciones autorizadas.
4. Registrar limitaciones del entorno.
5. Respetar las instrucciones más específicas de cada directorio y las de mayor autoridad.
6. No importar la identidad o el rol de Codex desde `AGENTS.md`; usarlo sólo como fuente de reglas del repositorio relevantes para la auditoría.

## Política de solo lectura

Durante las fases 0–3:

- usar lectura, búsqueda, inspección y comandos observacionales;
- preferir `git status`, `git diff`, `git log`, `git show` y equivalentes sin mutación;
- ejecutar analizadores estáticos sólo en modo no modificador;
- ejecutar tests o builds únicamente si sus efectos secundarios son conocidos y aceptables;
- preferir directorios temporales o entornos aislados para artefactos de validación.

Prohibido:

- `git reset`, `git restore`, `git checkout --`, `git clean`, `git stash`, commits, pushes, merges, rebases, tags o releases;
- formatters/linters con `--fix` o escritura automática;
- instalar, actualizar o eliminar dependencias;
- ejecutar migraciones o modificar datos reales;
- escribir sobre APIs/servicios externos o desplegar;
- ejecutar scripts con efectos de escritura desconocidos.

Si una herramienta puede generar caches, coverage, snapshots, lockfiles u otros archivos:

1. buscar un modo no modificador;
2. si es viable, aislarla fuera del repositorio;
3. comprobar Git antes y después;
4. detener ese método si aparecen cambios inesperados;
5. no borrar automáticamente archivos ambiguos;
6. registrar el efecto como limitación.

Si el usuario pide guardar el informe, se puede escribir **únicamente** el archivo de informe expresamente autorizado. No sobrescribir uno existente sin autorización.

## Fase 0 — Descubrimiento y cobertura

Inventariar antes de buscar defectos:

- propósito, dominio, arquitectura y estructura;
- lenguajes, runtimes, frameworks y puntos de entrada;
- módulos, componentes, scripts y configuración;
- variables de entorno, manifiestos, lockfiles y dependencias;
- persistencia, schemas y migraciones;
- APIs, integraciones, jobs, colas y procesos síncronos/asíncronos;
- modelos estadísticos/ML;
- tests, CI/CD, contenedores e infraestructura como código;
- observabilidad y documentación;
- código generado/vendorizado;
- archivos inaccesibles, ignorados o excluidos.

### Matriz de cobertura

Clasificar cada área o componente como:

- `REVISADA`
- `PARCIAL`
- `NO_APLICA`
- `NO_VERIFICABLE`
- `EXCLUIDA`

Registrar rutas/componentes cubiertos, método, validaciones y limitaciones.

En monorepos o repositorios grandes, dividir por paquete, servicio, aplicación o componente crítico. No marcar `REVISADA` una muestra no representativa.

## Fase 1 — Auditoría

Revisar todas las áreas aplicables.

### Arquitectura
Límites, responsabilidades, cohesión, acoplamiento, ciclos, contratos, flujos, inicialización/cierre, estado, concurrencia, idempotencia, recuperación y puntos únicos de fallo. No convertir preferencias arquitectónicas en defectos sin impacto demostrado.

### Código
Bugs funcionales/lógicos, condiciones incorrectas, excepciones, async, nulls, imports/rutas rotas, estados imposibles, ramas inalcanzables, código muerto relevante, duplicación con impacto, recursos no liberados, races, serialización, validación y manejo de errores.

### Configuración
Precedencia, defaults, variables de entorno, rutas, URLs, puertos, timeouts, flags, diferencias por entorno, archivos de ejemplo, validación y coherencia con código/documentación. No cambiar reglas de negocio, modelos, estrategias ni parámetros.

### Dependencias y supply chain
Manifiestos, lockfiles, runtime, dependencias directas/transitivas, faltantes/sin uso, incompatibilidades, reproducibilidad, abandono, vulnerabilidades conocidas y coherencia entre manifiestos y locks.

Distinguir: `REPORTADA`, `APLICABLE`, `EXPLOTABLE`, `TRANSITIVA`, `FALSO_POSITIVO`.

No instalar ni actualizar dependencias para auditar. Si es imprescindible para comprobar algo, dejarlo `NO_VERIFICABLE` salvo autorización separada.

### Pruebas
Unitarias, integración, E2E, regresión, edge cases, errores, determinismo/flakiness, fixtures/mocks, cobertura de componentes críticos y pruebas ausentes para bugs detectados. Nunca desactivar o debilitar pruebas para obtener verde.

### Seguridad
Secretos, credenciales, permisos, autenticación, autorización, input validation, inyección, traversal, SSRF, XSS, CSRF, CORS, deserialización, command execution, uploads, criptografía, sesiones, cookies, JWT, datos sensibles en logs, dependencias, configuración y permisos CI/CD.

### Datos y persistencia
Integridad, schemas, migraciones, constraints, relaciones, transacciones, locking, concurrencia, atomicidad, duplicados, sobrescritura, recuperación, retención, eliminación, corrupción, compatibilidad, timestamps y zonas horarias. No ejecutar migraciones ni modificar datos reales.

### Rendimiento
Sólo problemas relevantes y demostrables: complejidad, cálculos repetidos, N+1, carga excesiva, llamadas duplicadas, bloqueos, memory leaks, recursos abiertos, sync costoso, paginación ausente, caching incorrecto y procesamiento redundante.

### Integraciones externas
Contratos/schemas, autenticación, timeouts, retries/backoff, rate limits, paginación, respuestas parciales, errores, idempotencia, caching, fallback, cuotas, trazabilidad e indisponibilidad. No escribir externamente ni consumir servicios de pago.

### Cuantitativo y machine learning

Cuando aplique, verificar contra los contratos, configuración e implementación canónica del proyecto. No inventar thresholds, fórmulas, cutoffs ni semánticas ausentes.

Revisar:

- look-ahead bias;
- temporal leakage;
- target leakage;
- contaminación train/test;
- splits temporales;
- información disponible después del prediction/information cutoff;
- diferencia entre event time e information-availability time cuando exista;
- features futuras;
- selección retrospectiva;
- calibración;
- Brier score, log-loss y ECE cuando correspondan;
- invariantes probabilísticos y estabilidad numérica;
- odds freshness según la política canónica del proyecto;
- tamaño muestral;
- backtesting y walk-forward;
- reproducibilidad y seeds;
- tuning sobre test;
- compatibilidad de artefactos;
- promoción de modelos;
- separación entre experimentación y producción.

No presentar resultados sintéticos, in-sample o seleccionados retrospectivamente como evidencia fuera de muestra.

## Estados de evidencia

Cada candidato tiene exactamente un estado:

- `REPRODUCIDO`: activado de forma controlada y observado el resultado incorrecto.
- `VERIFICADO_ESTATICAMENTE`: demostrado directamente por código, configuración, contrato o datos inspeccionables.
- `DETECTADO_POR_HERRAMIENTA`: reportado por una herramienta; aplicabilidad/impacto aún sin confirmar.
- `INFERIDO`: evidencia razonable, pero falta una condición necesaria.
- `NO_VERIFICABLE`: el entorno carece de una condición necesaria.
- `DESCARTADO`: revisión adicional refutó la sospecha.

Sólo `REPRODUCIDO` y `VERIFICADO_ESTATICAMENTE` pueden entrar automáticamente en hallazgos confirmados.

## Severidad

Usar exactamente cuatro niveles; el ID debe coincidir.

- `CRITICAL` → `AUD-CRIT-NNN`: pérdida/corrupción significativa de datos, exposición crítica de credenciales, ejecución arbitraria, vulnerabilidad crítica explotable, indisponibilidad completa o resultado principal sistemáticamente incorrecto.
- `HIGH` → `AUD-HIGH-NNN`: bug material, fallo frecuente, degradación importante, vulnerabilidad considerable, regresión importante o riesgo sustancial de datos.
- `MEDIUM` → `AUD-MED-NNN`: defecto real de impacto limitado/condicionado, degradación parcial, validación relevante ausente o mantenibilidad con riesgo material.
- `LOW` → `AUD-LOW-NNN`: deuda técnica acotada, duplicación, documentación incorrecta, inconsistencia o mejora defensiva de bajo impacto.

No elevar severidad por posibilidad teórica sin ruta causal demostrable.

## Confianza

Independiente de la severidad:

- `HIGH`: evidencia inequívoca.
- `MEDIUM`: evidencia sólida pero incompleta.
- `LOW`: hipótesis plausible dependiente de información o condiciones ausentes.

Reglas:

- confianza `LOW` nunca se presenta como defecto confirmado;
- `DETECTADO_POR_HERRAMIENTA` no obtiene `HIGH` sólo por la herramienta;
- `REPRODUCIDO` normalmente es `HIGH` si demuestra causalidad;
- `VERIFICADO_ESTATICAMENTE` puede ser `HIGH` si la ruta causal es inequívoca; de lo contrario `MEDIUM`.

## Registro por hallazgo

Registrar:

- ID, título, estado, severidad, confianza y categoría;
- componente, archivos y líneas;
- evidencia y condición de activación;
- reproducción/comprobación;
- esperado vs observado;
- causa raíz, impacto y alcance;
- solución mínima y alternativas relevantes;
- riesgo de regresión y pruebas necesarias;
- limitaciones.

Si un dato no existe, indicarlo expresamente.

## Fase 2 — Validación independiente

Para cada candidato relevante:

1. revisar llamadores, consumidores y flujos relacionados;
2. buscar guards/protecciones;
3. contrastar código, configuración, tests y documentación;
4. buscar contraejemplos;
5. intentar reproducción segura cuando sea viable;
6. comprobar si el comportamiento es intencional;
7. reevaluar severidad y confianza;
8. asignar estado final.

Usar un segundo método distinto cuando sea posible: estático + test, herramienta + revisión manual, configuración + contrato, reproducción + causa raíz.

Si no existe segundo método viable, declarar la limitación; no fabricar validación.

Conservar falsos positivos relevantes en una sección separada con la evidencia que los descartó.

## Fase 3 — Plan de corrección

Prioridad:

1. `CRITICAL`
2. `HIGH`
3. seguridad e integridad de datos
4. riesgos operacionales
5. `MEDIUM`
6. pruebas/regresiones
7. `LOW` y deuda técnica
8. mejoras opcionales

Por acción indicar: IDs, archivos previstos, cambio mínimo, dependencias, riesgo, pruebas, criterio de aceptación y orden.

No modificar todavía. Entregar informe y esperar aprobación explícita.

La aprobación puede identificar IDs, grupos inequívocos o “todos los hallazgos confirmados”.

## Fase 4 — Corrección autorizada

Sólo después de aprobación:

1. confirmar alcance autorizado;
2. releer instrucciones aplicables;
3. volver a inspeccionar Git;
4. detectar cambios preexistentes y solapamientos;
5. enumerar archivos afectados y parche mínimo;
6. modificar únicamente lo aprobado.

Preservar comportamiento válido, configuración no relacionada, interfaces públicas, compatibilidad, schemas, modelos, estrategias, parámetros, criterios de decisión y datos históricos salvo autorización específica.

No hacer refactors masivos, limpieza cosmética u otros cambios oportunistas. No eliminar archivos untracked/ambiguos. No ejecutar acciones externas, migraciones irreversibles, commits, pushes, merges, releases o deployments sin autorización específica.

Después de los cambios funcionales autorizados, cumplir el bookkeeping obligatorio de `CLAUDE.md` sin ampliar el alcance técnico.

## Fase 5 — Validación final

Tras cada conjunto lógico de correcciones:

1. prueba específica;
2. pruebas del componente;
3. validaciones estáticas;
4. regresión relevante;
5. suite completa si es viable;
6. revisión del diff;
7. coherencia de configuración/manifiestos/lockfiles;
8. búsqueda de regresiones.

Clasificar cada comprobación:

- `PASO`
- `FALLO`
- `FALLO_PREEXISTENTE`
- `REGRESION_INTRODUCIDA`
- `NO_EJECUTADA`

No afirmar éxito global si una validación crítica no se ejecutó.

Entregar IDs corregidos, cambios, archivos, comandos, resultados, tests, regresiones, riesgos pendientes, limitaciones y validaciones no ejecutadas.

## Orquestación

Delegar sólo cuando se cumplan ambas condiciones:

1. existen workstreams realmente independientes o especialidades que puedan revisarse sin depender continuamente unas de otras;
2. el paralelismo mejora materialmente la cobertura, la verificación o la latencia.

No orquestar únicamente porque el usuario diga “full system audit”.

Si `principal-orchestrator` u otros especialistas están disponibles, delegar sólo áreas pertinentes. Posibles especialistas: `repository-cartographer`, `backend-architect`, `data-engineer`, `feature-engineer`, `leakage-detector`, `ml-engineer`, `calibration-auditor`, `backtest-reviewer`, `odds-market-auditor`, `risk-manager`, `qa-engineer`, `security-reviewer`.

No asumir que existen. Si faltan, continuar con los disponibles y cubrir localmente lo viable sin reducir silenciosamente la cobertura.

A cada especialista proporcionar: alcance, rutas/componentes, exclusiones, prohibición de modificar, taxonomía, estados de evidencia, formato y comandos permitidos.

El coordinador debe verificar evidencia, deduplicar, resolver inconsistencias, normalizar severidad/confianza, descartar falsos positivos, conservar trazabilidad e identificar huecos. No aceptar conclusiones automáticamente.

## Informe consolidado

Entregar:

1. **Resumen ejecutivo:** propósito, alcance, arquitectura, estado, riesgos, conclusión y limitaciones.
2. **Matriz de cobertura:** estado, rutas/componentes, método, validaciones y limitaciones.
3. **Hallazgos confirmados:** `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
4. **No confirmados:** `DETECTADO_POR_HERRAMIENTA`, `INFERIDO`, `NO_VERIFICABLE`.
5. **Descartados relevantes:** sospecha y evidencia que la refutó.
6. **Validaciones:** comando/método, propósito, resultado, efectos secundarios y limitaciones.
7. **Plan priorizado:** IDs, archivos, riesgo, pruebas, aceptación y orden.
8. **Riesgos pendientes:** elementos no verificables/corregibles y causa.

## Finalización

### Auditoría completa

Sólo si:

- existe inventario verificable;
- la matriz tiene granularidad suficiente;
- todas las áreas aplicables están revisadas o limitadas explícitamente;
- los hallazgos activos fueron revalidados cuando era viable;
- se registraron descartados relevantes y límites;
- existe plan priorizado;
- no se modificó el proyecto salvo un informe expresamente autorizado.

Si no, declarar la auditoría `PARCIAL` y explicar por qué.

### Corrección completa

Sólo si:

- se trataron únicamente IDs autorizados;
- las pruebas específicas se ejecutaron o su imposibilidad quedó documentada;
- no hay regresiones atribuibles conocidas;
- se revisó el diff final;
- se documentaron riesgos y limitaciones;
- se separaron fallos preexistentes de regresiones introducidas;
- se completó o se declaró imposible el bookkeeping obligatorio de `CLAUDE.md`.

## Restricciones finales

No modificar durante auditoría; no confundir auditoría con autorización de corrección; no alterar producción ni datos reales; no ocultar fallos; no debilitar validaciones; no presentar inferencias como hechos; no inventar evidencia; no ejecutar operaciones remotas/destructivas sin autorización; documentar toda modificación autorizada.
