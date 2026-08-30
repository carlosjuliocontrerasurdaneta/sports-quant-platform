# Fases 0–3 — Diagnóstico

Procedimiento de la skill `full-audit`. Las reglas obligatorias y la precedencia
viven en `SKILL.md` y no se repiten aquí.

## Política de comandos

Permitido: lectura, búsqueda, inspección y comandos observacionales; `git
status`, `git diff`, `git log`, `git show` y equivalentes sin mutación;
analizadores estáticos en modo no modificador; tests o builds **sólo** si sus
efectos secundarios son conocidos y aceptables; directorios temporales o
entornos aislados para artefactos de validación.

Prohibido:

- `git reset`, `git restore`, `git checkout --`, `git clean`, `git stash`, commits, pushes, merges, rebases, tags o releases;
- formatters/linters con `--fix` o escritura automática;
- instalar, actualizar o eliminar dependencias;
- ejecutar migraciones o modificar datos reales;
- escribir sobre APIs/servicios externos o desplegar;
- ejecutar scripts con efectos de escritura desconocidos.

Los verbos git destructivos están además denegados en `.claude/settings.json`
para Bash y PowerShell. Esa denegación es una red, no la regla: no cubre la
escritura sobre el código fuente, que sigue siendo responsabilidad de esta
política.

Nota de entorno: el hook `PostToolUse` de este repositorio ejecuta `ruff check
--fix` tras cada `Edit`/`Write` (`.claude/hooks/post-edit-format.sh`). Durante
las fases 0–3 no debe dispararse, porque no se escribe sobre el código. Si se
dispara, algo se escribió que no debía: registrarlo como limitación.

Si una herramienta puede generar caches, coverage, snapshots o lockfiles:

1. buscar un modo no modificador;
2. si es viable, aislarla fuera del repositorio;
3. comprobar Git antes y después;
4. detener ese método si aparecen cambios inesperados;
5. no borrar automáticamente archivos ambiguos;
6. registrar el efecto como limitación.

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

Clasificar cada área o componente como `REVISADA`, `PARCIAL`, `NO_APLICA`,
`COBERTURA_NO_VERIFICABLE` o `EXCLUIDA`. Registrar rutas/componentes cubiertos,
método, validaciones y limitaciones.

En monorepos o repositorios grandes, dividir por paquete, servicio, aplicación o
componente crítico.

### Cobertura operativa y presupuesto

`REVISADA` exige **lectura completa**, no muestreo, en:

- todos los puntos de entrada (CLI, scripts operacionales, jobs programados);
- todo módulo que toque dinero, probabilidad, cuotas, stake o bankroll;
- toda la capa de persistencia y de settlement;
- toda la configuración y sus manifiestos.

En el resto se admite muestreo, pero debe declararse el criterio y el número de
archivos inspeccionados sobre el total, y el área se marca `PARCIAL`, nunca
`REVISADA`.

Presupuesto por defecto: 8 iteraciones (el mismo contador de
`current-task.md`). Al agotarlo, cerrar con lo cubierto y declarar `PARCIAL`;
no extender en silencio. Persistir el avance tras cada área, no al final.

## Fase 1 — Auditoría

Revisar todas las áreas aplicables.

### Arquitectura
Límites, responsabilidades, cohesión, acoplamiento, ciclos, contratos, flujos,
inicialización/cierre, estado, concurrencia, idempotencia, recuperación y puntos
únicos de fallo. No convertir preferencias arquitectónicas en defectos sin
impacto demostrado.

### Código
Bugs funcionales/lógicos, condiciones incorrectas, excepciones, async, nulls,
imports/rutas rotas, estados imposibles, ramas inalcanzables, código muerto
relevante, duplicación con impacto, recursos no liberados, races, serialización,
validación y manejo de errores.

### Configuración
Precedencia, defaults, variables de entorno, rutas, URLs, puertos, timeouts,
flags, diferencias por entorno, archivos de ejemplo, validación y coherencia con
código y documentación. No cambiar reglas de negocio, modelos, estrategias ni
parámetros.

### Dependencias y supply chain
Manifiestos, lockfiles, runtime, dependencias directas/transitivas,
faltantes/sin uso, incompatibilidades, reproducibilidad, abandono,
vulnerabilidades conocidas y coherencia entre manifiestos y locks.

Distinguir: `REPORTADA`, `APLICABLE`, `EXPLOTABLE`, `TRANSITIVA`,
`FALSO_POSITIVO`.

No instalar ni actualizar dependencias para auditar. Si es imprescindible para
comprobar algo, dejarlo `EVIDENCIA_NO_VERIFICABLE` salvo autorización separada.

### Pruebas
Unitarias, integración, E2E, regresión, edge cases, errores,
determinismo/flakiness, fixtures/mocks, cobertura de componentes críticos y
pruebas ausentes para bugs detectados. Nunca desactivar ni debilitar pruebas
para obtener verde.

### Seguridad
Secretos, credenciales, permisos, autenticación, autorización, input validation,
inyección, traversal, SSRF, XSS, CSRF, CORS, deserialización, command execution,
uploads, criptografía, sesiones, cookies, JWT, datos sensibles en logs,
dependencias, configuración y permisos CI/CD.

### Datos y persistencia
Integridad, schemas, migraciones, constraints, relaciones, transacciones,
locking, concurrencia, atomicidad, duplicados, sobrescritura, recuperación,
retención, eliminación, corrupción, compatibilidad, timestamps y zonas horarias.
No ejecutar migraciones ni modificar datos reales.

### Rendimiento
Sólo problemas relevantes y demostrables: complejidad, cálculos repetidos, N+1,
carga excesiva, llamadas duplicadas, bloqueos, memory leaks, recursos abiertos,
sync costoso, paginación ausente, caching incorrecto y procesamiento redundante.

### Integraciones externas
Contratos/schemas, autenticación, timeouts, retries/backoff, rate limits,
paginación, respuestas parciales, errores, idempotencia, caching, fallback,
cuotas, trazabilidad e indisponibilidad. No escribir externamente ni consumir
servicios de pago.

### Cuantitativo y machine learning

Verificar contra los contratos, configuración e implementación canónica del
proyecto, cuyas rutas están en `project-anchors.md`. **No inventar thresholds,
fórmulas, cutoffs ni semánticas ausentes**: si un umbral no existe en el código,
la configuración o una decisión humana registrada, el hallazgo es
`EVIDENCIA_NO_VERIFICABLE` con una propuesta de umbral, nunca un número
improvisado después de ver los datos.

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

No presentar resultados sintéticos, in-sample o seleccionados retrospectivamente
como evidencia fuera de muestra.

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

Usar un segundo método distinto cuando sea posible: estático + test, herramienta
+ revisión manual, configuración + contrato, reproducción + causa raíz.

**Una búsqueda que no encuentra algo no es evidencia de que no exista.** Antes de
reportar código muerto, una función sin llamadores o una defensa no cableada,
repetir la búsqueda sin los filtros que la acotaron —incluida la exclusión del
propio módulo que define el símbolo— y sobre todo el repositorio. Este error ya
produjo un falso positivo `ALTO` (auditoría 2026-08-30).

Si no existe segundo método viable, declarar la limitación; no fabricar
validación.

Conservar los falsos positivos relevantes con la evidencia que los descartó.

## Fase 3 — Plan de corrección

Prioridad:

1. `CRÍTICO`
2. `ALTO`
3. seguridad e integridad de datos
4. riesgos operacionales
5. `MEDIO`
6. pruebas/regresiones
7. `BAJO` y deuda técnica
8. mejoras opcionales

Por acción indicar: IDs, archivos previstos, cambio mínimo, dependencias,
riesgo, pruebas, criterio de aceptación y orden.

Entregar los artefactos definidos en `deliverables.md` y **detenerse**. La
aprobación puede identificar IDs, grupos inequívocos o "todos los hallazgos
confirmados". Con aprobación, continuar en la skill `audit-remediation`.

## Orquestación

La ruta `full-audit` de `.claude/automation/model-routing.json` designa
`principal-orchestrator` como agente coordinador y declara el conjunto de
especialistas por defecto. Ese archivo es la fuente de verdad del conjunto; no
duplicar aquí una lista paralela que se desincronice.

Designar un coordinador **no obliga a abrir el abanico**. Delegar en un
especialista sólo cuando se cumplan las dos condiciones:

1. existe un workstream realmente independiente, revisable sin depender de forma continua de los demás;
2. el paralelismo mejora materialmente la cobertura, la verificación o la latencia.

No delegar únicamente porque el usuario haya dicho "auditoría completa". La
palabra clave elige la ruta, no el número de agentes. `CLAUDE.md` prohíbe además
generar subagentes por defecto: la delegación es la excepción justificada, no el
punto de partida.

Además del conjunto por defecto, hay especialistas disponibles en
`.claude/agents/` para áreas concretas: leakage, calibración, backtesting,
cuotas y mercados, riesgo, datos, features, arquitectura, pruebas y seguridad.
Comprobar su existencia antes de nombrarlos; si falta uno, cubrir el área
localmente y **declararlo**, nunca reducir la cobertura en silencio.

A cada especialista dar: alcance, rutas y componentes, exclusiones, prohibición
de modificar, la taxonomía de `taxonomy.md`, el formato de `deliverables.md` y
los comandos permitidos.

El coordinador verifica evidencia, deduplica, resuelve inconsistencias,
normaliza severidad y confianza, descarta falsos positivos, conserva
trazabilidad e identifica huecos. **No aceptar conclusiones automáticamente**:
un hallazgo delegado entra al informe con el mismo estándar de evidencia que uno
propio.
