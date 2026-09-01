
---

name: full-audit
description: Auditar exhaustivamente repositorios y proyectos de software sin modificar archivos durante el diagnóstico. Usar cuando el usuario solicite una auditoría completa, revisión integral, full audit, full system audit, detección general de bugs, riesgos, vulnerabilidades, problemas de arquitectura, dependencias, configuración, pruebas, scripts, datos, modelos cuantitativos o integraciones externas. Inventariar primero el proyecto, documentar evidencia reproducible, validar los hallazgos, clasificarlos por severidad y confianza, preparar un plan de corrección y esperar aprobación explícita antes de implementar cambios.
---


# Full Audit

## Objetivo

Analizar exhaustivamente el proyecto para detectar defectos funcionales, errores lógicos, riesgos de ejecución, vulnerabilidades, problemas de datos, deuda técnica e inconsistencias.

Distinguir siempre entre:

* defectos confirmados;
* hallazgos inferidos;
* problemas detectados por herramientas;
* elementos no verificables en el entorno;
* falsos positivos descartados.

No modificar archivos durante las fases de descubrimiento, auditoría, validación y planificación.

## Reglas de autoridad y seguridad

Antes de auditar:

1. Leer `AGENTS.md` y cualquier instrucción específica del repositorio.
2. Inspeccionar el estado de Git cuando esté disponible.
3. Identificar cambios preexistentes.
4. No sobrescribir, revertir ni descartar modificaciones del usuario.
5. Respetar las instrucciones más específicas aplicables a cada directorio.
6. Determinar qué acciones están autorizadas por la solicitud del usuario.

Interpretar las solicitudes de auditar, revisar, analizar, diagnosticar o buscar errores como autorización de solo lectura.

No tratar una solicitud de auditoría como autorización para modificar código.

## Fase 0 — Descubrimiento y cobertura

Antes de buscar defectos, construir un inventario del proyecto.

Identificar:

* propósito y dominio;
* arquitectura;
* estructura de directorios;
* lenguajes y versiones;
* frameworks;
* puntos de entrada;
* módulos y componentes;
* scripts;
* configuración;
* variables de entorno;
* manifiestos y lockfiles;
* dependencias;
* almacenamiento y persistencia;
* esquemas y migraciones;
* APIs;
* integraciones externas;
* procesos síncronos y asíncronos;
* modelos estadísticos o de machine learning;
* pruebas;
* CI/CD;
* contenedores;
* infraestructura declarativa;
* documentación;
* código generado o vendorizado;
* archivos inaccesibles o excluidos.

Clasificar cada área como:

* revisada;
* revisada parcialmente;
* no aplicable;
* no verificable;
* excluida, indicando la razón.

No declarar que la auditoría es exhaustiva sin presentar una matriz de cobertura.

## Fase 1 — Auditoría

Revisar todas las áreas aplicables al proyecto.

### Arquitectura

Analizar:

* límites entre componentes;
* responsabilidades;
* cohesión;
* acoplamiento;
* dependencias circulares;
* flujos principales;
* contratos internos;
* puntos únicos de fallo;
* inicialización y cierre;
* manejo de estado;
* concurrencia;
* idempotencia;
* recuperación ante fallos.

No reportar como defecto una preferencia arquitectónica sin impacto demostrable.

### Código

Revisar todos los lenguajes detectados, incluidos cuando correspondan:

* Python;
* scripts BAT;
* PowerShell;
* Bash;
* JavaScript o TypeScript;
* SQL;
* archivos de configuración;
* infraestructura como código.

Buscar:

* bugs funcionales;
* errores lógicos;
* condiciones incorrectas;
* excepciones potenciales;
* errores asíncronos;
* valores nulos inesperados;
* imports o rutas rotas;
* estados imposibles;
* ramas inalcanzables;
* código muerto;
* duplicación;
* responsabilidades mezcladas;
* recursos no liberados;
* condiciones de carrera;
* errores de serialización;
* validación insuficiente;
* manejo incorrecto de errores.

### Configuración

Revisar:

* precedencia;
* valores predeterminados;
* variables de entorno;
* rutas;
* URLs;
* puertos;
* timeouts;
* feature flags;
* configuración por entorno;
* archivos de ejemplo;
* validación;
* coherencia con la documentación.

No modificar parámetros, modelos, estrategias ni criterios de negocio durante la auditoría.

### Dependencias

Revisar:

* manifiestos;
* lockfiles;
* versiones de runtime;
* imports utilizados;
* dependencias faltantes;
* dependencias sin uso;
* incompatibilidades;
* reproducibilidad;
* paquetes abandonados;
* vulnerabilidades conocidas según las herramientas disponibles;
* coherencia entre manifiestos y lockfiles.

Distinguir entre:

* vulnerabilidad reportada;
* vulnerabilidad aplicable;
* vulnerabilidad explotable;
* dependencia transitiva;
* falso positivo.

No instalar ni actualizar dependencias durante la auditoría, salvo autorización expresa y cuando sea indispensable para una validación segura.

### Tests

Analizar:

* pruebas unitarias;
* integración;
* end-to-end;
* regresión;
* casos límite;
* validaciones;
* manejo de errores;
* determinismo;
* flakiness;
* fixtures;
* mocks;
* cobertura de componentes críticos;
* pruebas ausentes para bugs detectados.

No eliminar, desactivar, omitir ni debilitar pruebas para conseguir resultados exitosos.

### Seguridad

Revisar según el stack:

* secretos versionados;
* credenciales y tokens;
* permisos;
* autenticación;
* autorización;
* validación de entradas;
* inyecciones;
* traversal;
* SSRF;
* XSS;
* CSRF;
* CORS;
* deserialización insegura;
* ejecución de comandos;
* archivos subidos;
* criptografía;
* sesiones;
* cookies;
* JWT;
* información sensible en logs;
* dependencias vulnerables;
* configuración insegura;
* permisos de CI/CD.

No mostrar secretos completos. Informar únicamente su tipo, ubicación y acción necesaria.

### Datos y persistencia

Revisar:

* integridad;
* validación;
* schemas;
* migraciones;
* constraints;
* relaciones;
* transacciones;
* locking;
* concurrencia;
* escrituras atómicas;
* duplicados;
* sobrescritura;
* recuperación;
* retención;
* eliminación;
* corrupción;
* compatibilidad de formatos;
* timestamps y zonas horarias.

No ejecutar migraciones ni modificar datos reales durante la auditoría.

### Rendimiento

Buscar únicamente problemas relevantes y demostrables:

* complejidad algorítmica;
* cálculos repetidos;
* consultas N+1;
* carga excesiva;
* llamadas duplicadas;
* bloqueos;
* memory leaks;
* streams o archivos no cerrados;
* operaciones síncronas costosas;
* paginación ausente;
* caching incorrecto;
* procesamiento redundante.

No recomendar optimizaciones hipotéticas sin evidencia.

### Integraciones externas

Revisar:

* contratos;
* autenticación;
* timeouts;
* retries;
* rate limits;
* paginación;
* respuestas parciales;
* schemas;
* errores;
* idempotencia;
* caching;
* fallback;
* consumo de cuota;
* trazabilidad;
* comportamiento ante indisponibilidad.

No efectuar escrituras externas, consumir servicios de pago ni operar sobre producción durante la auditoría.

### Código cuantitativo y machine learning

Cuando corresponda, revisar:

* look-ahead bias;
* target leakage;
* contaminación train/test;
* splits temporales;
* features futuras;
* timestamps;
* selección retrospectiva;
* calibración;
* Brier score;
* log-loss;
* ECE;
* tamaño muestral;
* backtesting;
* walk-forward;
* reproducibilidad;
* seeds;
* tuning sobre el conjunto de prueba;
* compatibilidad de artefactos;
* promoción de modelos;
* separación entre código experimental y producción.

No presentar resultados sintéticos, in-sample o retrospectivamente seleccionados como evidencia fuera de muestra.

## Evidencia de los hallazgos

Asignar un identificador estable a cada hallazgo:

* `AUD-CRIT-001`;
* `AUD-HIGH-001`;
* `AUD-MED-001`;
* `AUD-LOW-001`.

Para cada hallazgo indicar:

* ID;
* título;
* estado;
* severidad;
* nivel de confianza;
* categoría;
* archivos y líneas;
* componente;
* evidencia;
* condición de activación;
* pasos o comando de reproducción;
* resultado esperado;
* resultado observado;
* causa raíz;
* impacto;
* alcance;
* solución mínima propuesta;
* alternativas;
* riesgo de regresión;
* pruebas necesarias;
* limitaciones.

Si un dato no está disponible, indicarlo expresamente. No inventar archivos, líneas, comandos, resultados, errores ni comportamientos.

## Estados de evidencia

### REPRODUCIDO

El defecto fue activado mediante una ejecución controlada y se observó el resultado incorrecto.

### VERIFICADO ESTÁTICAMENTE

La ruta defectuosa está demostrada directamente por el código o la configuración.

### DETECTADO POR HERRAMIENTA

Una herramienta produjo el hallazgo, pero su aplicabilidad todavía debe comprobarse.

### INFERIDO

Existe evidencia razonable, pero falta una condición o validación necesaria.

### NO VERIFICABLE

No puede comprobarse por ausencia de dependencias, datos, credenciales, servicios, sistema operativo, infraestructura o permisos.

### DESCARTADO

La revisión adicional demostró que la sospecha inicial no era un defecto.

No presentar como confirmado un hallazgo inferido, no verificable o detectado únicamente por una herramienta.

## Severidad

### CRÍTICO

Usar cuando el defecto pueda provocar:

* pérdida o corrupción significativa de datos;
* exposición de credenciales;
* ejecución arbitraria;
* vulnerabilidad crítica explotable;
* indisponibilidad completa;
* resultado principal sistemáticamente incorrecto;
* incumplimiento grave de controles operacionales.

### IMPORTANTE

Usar cuando exista:

* bug funcional relevante;
* fallo frecuente;
* resultado materialmente incorrecto;
* degradación operacional significativa;
* vulnerabilidad de impacto considerable;
* regresión importante;
* riesgo sustancial de datos.

### MENOR

Usar para:

* defecto acotado;
* mantenibilidad;
* duplicación;
* documentación incorrecta;
* validación secundaria ausente;
* robustez adicional;
* impacto funcional reducido.

No elevar la severidad por una posibilidad teórica sin ruta causal demostrable.

## Nivel de confianza

### ALTO

Hallazgo reproducido o demostrado mediante evidencia inequívoca.

### MEDIO

Evidencia estática sólida, pero sin reproducción completa.

### BAJO

Hipótesis plausible que depende de condiciones o información no disponible.

No incluir hallazgos de confianza baja entre los defectos confirmados.

## Fase 2 — Validación independiente

Revisar nuevamente cada hallazgo mediante un método adicional.

Para cada candidato:

1. revisar los llamadores y flujos relacionados;
2. buscar validaciones o protecciones existentes;
3. contrastar configuración, pruebas y documentación;
4. buscar contraejemplos;
5. intentar una reproducción segura;
6. determinar si el comportamiento es intencional;
7. reevaluar severidad y confianza;
8. clasificarlo como confirmado, inferido, no verificable o descartado.

No eliminar silenciosamente falsos positivos. Conservar los descartados relevantes en un apartado separado, explicando por qué fueron refutados.

No limitarse a repetir el razonamiento inicial.

## Fase 3 — Plan de corrección

Generar un plan ordenado por:

1. defectos críticos;
2. defectos importantes;
3. seguridad e integridad de datos;
4. riesgos operacionales;
5. pruebas y regresiones;
6. deuda técnica;
7. mejoras opcionales.

Para cada acción indicar:

* IDs relacionados;
* archivos previstos;
* cambio mínimo;
* dependencias;
* riesgo;
* pruebas requeridas;
* criterio de aceptación;
* orden de implementación.

No modificar archivos todavía.

Entregar el informe y esperar aprobación explícita.

La aprobación debe identificar los hallazgos o grupos de cambios autorizados.

## Fase 4 — Corrección

Ejecutar esta fase únicamente después de recibir aprobación expresa.

Antes de modificar:

1. confirmar los IDs aprobados;
2. releer las instrucciones aplicables;
3. inspeccionar nuevamente el estado de Git;
4. identificar cambios preexistentes;
5. detectar solapamientos;
6. mostrar los archivos afectados;
7. mostrar el plan exacto de cambios.

Corregir únicamente los elementos aprobados.

Aplicar el parche mínimo que resuelva la causa confirmada.

Preservar, salvo autorización expresa:

* lógica de negocio válida;
* comportamiento funcional;
* configuración no relacionada;
* interfaces públicas;
* compatibilidad;
* esquemas;
* modelos;
* estrategias;
* parámetros;
* criterios de decisión;
* datos históricos.

No realizar refactorizaciones masivas ni cambios cosméticos no relacionados.

No eliminar archivos no versionados, ambiguos o preexistentes.

No ejecutar operaciones destructivas, migraciones irreversibles ni acciones externas sin autorización explícita.

## Fase 5 — Validación final

Después de cada conjunto lógico de correcciones:

1. ejecutar la prueba específica del defecto;
2. ejecutar las pruebas del componente;
3. ejecutar las validaciones estáticas pertinentes;
4. ejecutar la suite de regresión relevante;
5. ejecutar la suite completa cuando sea viable;
6. revisar el diff;
7. comprobar configuración, manifiestos y lockfiles;
8. buscar regresiones accidentales;
9. revisar nuevamente las áreas afectadas.

Distinguir entre:

* validaciones exitosas;
* validaciones fallidas;
* fallos preexistentes;
* regresiones introducidas;
* validaciones no ejecutables.

No afirmar éxito si una comprobación no se ejecutó.

Entregar:

* IDs corregidos;
* cambios realizados;
* archivos modificados;
* comandos ejecutados;
* resultados;
* pruebas añadidas o modificadas;
* regresiones detectadas;
* riesgos pendientes;
* limitaciones;
* validaciones no ejecutadas y su causa.

## Modo orquestado

Activar cuando:

* la auditoría abarque todo el sistema;
* el usuario solicite “full system audit”;
* el usuario solicite una auditoría orquestada;
* el alcance requiera especialidades independientes.

Usar `principal-orchestrator` cuando esté disponible y delegar únicamente las áreas aplicables entre:

* `repository-cartographer`;
* `backend-architect`;
* `data-engineer`;
* `feature-engineer`;
* `leakage-detector`;
* `ml-engineer`;
* `calibration-auditor`;
* `backtest-reviewer`;
* `odds-market-auditor`;
* `risk-manager`;
* `qa-engineer`;
* `security-reviewer`.

No asumir que un especialista existe por estar nombrado.

Si un especialista no está disponible:

1. continuar con los especialistas disponibles;
2. realizar localmente la revisión equivalente;
3. indicar qué área no pudo delegarse;
4. no reducir silenciosamente la cobertura.

Proporcionar a cada especialista:

* alcance exacto;
* archivos o componentes asignados;
* exclusiones;
* prohibición de modificar;
* taxonomía de severidad;
* estados de evidencia;
* formato obligatorio;
* comandos permitidos.

El orquestador debe:

1. verificar la evidencia de cada especialista;
2. deduplicar hallazgos;
3. resolver inconsistencias;
4. unificar severidad y confianza;
5. descartar falsos positivos;
6. conservar la trazabilidad;
7. identificar áreas sin cobertura.

No aceptar automáticamente las conclusiones de los especialistas.

## Informe consolidado

Entregar:

### Resumen ejecutivo

* propósito;
* arquitectura;
* estado general;
* riesgos principales;
* conclusión;
* limitaciones.

### Matriz de cobertura

Para cada área:

* estado;
* método de revisión;
* validación;
* limitaciones.

### Hallazgos confirmados

Ordenar por:

1. críticos;
2. importantes;
3. menores.

### Hallazgos inferidos o no verificables

Mantenerlos separados de los confirmados.

### Falsos positivos descartados

Incluir los casos relevantes y la evidencia que los descartó.

### Validaciones

Para cada comando:

* comando exacto;
* resultado;
* fallos;
* limitaciones.

### Plan priorizado

Relacionar cada acción con sus IDs, archivos, riesgos, pruebas y criterio de aceptación.

### Riesgos pendientes

Indicar los problemas que no puedan corregirse o verificarse y explicar la causa.

## Criterio de finalización

Considerar completada la auditoría cuando:

* exista un inventario verificable;
* la matriz de cobertura esté completa;
* todos los hallazgos hayan sido revalidados;
* los falsos positivos relevantes estén identificados;
* los límites de la revisión estén declarados;
* exista un plan priorizado;
* no se hayan modificado archivos.

Considerar completada la corrección cuando:

* se hayan tratado únicamente los IDs aprobados;
* las pruebas específicas hayan sido ejecutadas;
* no existan regresiones atribuibles conocidas;
* el diff final haya sido revisado;
* los riesgos y limitaciones pendientes estén documentados.

## Restricciones finales

* No modificar archivos automáticamente durante la auditoría.
* No realizar refactorizaciones masivas sin aprobación.
* No cambiar modelos, estrategias, parámetros ni criterios de negocio sin autorización explícita.
* No alterar producción, servicios externos, bases de datos reales ni credenciales.
* No ejecutar commits, pushes, merges, releases o deployments sin solicitud expresa.
* No ocultar fallos ni debilitar validaciones.
* No presentar inferencias como hechos confirmados.
* Priorizar precisión y evidencia sobre velocidad.
* Documentar toda modificación relevante.

