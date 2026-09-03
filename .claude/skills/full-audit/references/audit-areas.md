# Áreas generales de auditoría

## Contenidos

- Fase 1 — Auditoría
- Arquitectura
- Código
- Configuración
- Dependencias
- Tests
- Seguridad
- Datos y persistencia
- Rendimiento
- Integraciones externas

---
# Fase 1 — Auditoría

Durante esta fase, todo posible defecto se considera inicialmente un:

`CANDIDATO DE AUDITORÍA`

No debe tratarse como hallazgo confirmado hasta completar la validación independiente de Fase 2.

Revisar todas las áreas aplicables al proyecto.

## Arquitectura

Analizar:

- límites entre componentes;
- responsabilidades;
- cohesión;
- acoplamiento;
- dependencias circulares;
- flujos principales;
- contratos internos;
- puntos únicos de fallo;
- inicialización;
- cierre;
- manejo de estado;
- concurrencia;
- idempotencia;
- recuperación ante fallos;
- consistencia transaccional;
- propagación de errores;
- aislamiento entre dominios.

No reportar como defecto una preferencia arquitectónica sin impacto demostrable.

## Código

Revisar todos los lenguajes detectados que formen parte del comportamiento relevante del sistema, incluidos cuando correspondan:

- Python;
- BAT;
- PowerShell;
- Bash;
- JavaScript;
- TypeScript;
- SQL;
- archivos de configuración;
- infraestructura como código;
- otros lenguajes presentes.

Buscar:

- bugs funcionales;
- errores lógicos;
- condiciones incorrectas;
- excepciones potenciales;
- errores asíncronos;
- valores nulos inesperados;
- imports rotos;
- rutas rotas;
- estados imposibles;
- ramas inalcanzables;
- código muerto;
- duplicación;
- responsabilidades mezcladas;
- recursos no liberados;
- condiciones de carrera;
- errores de serialización;
- validación insuficiente;
- manejo incorrecto de errores;
- inconsistencias entre contrato e implementación.

Priorizar código ejecutable, configuración activa y rutas alcanzables.

No realizar revisión línea por línea de código generado, vendorizado, caches o artefactos de build salvo que:

- formen parte de una ruta relevante;
- sean modificados directamente por el proyecto;
- participen en un hallazgo;
- afecten la seguridad, integridad o reproducibilidad.

## Configuración

Revisar:

- precedencia;
- valores predeterminados;
- variables de entorno;
- rutas;
- URLs;
- puertos;
- timeouts;
- feature flags;
- configuración por entorno;
- archivos de ejemplo;
- validación;
- coherencia con documentación;
- configuración efectiva;
- valores implícitos;
- diferencias entre desarrollo, staging y producción cuando puedan verificarse.

No modificar parámetros, modelos, estrategias ni criterios de negocio durante la auditoría.

## Dependencias

Revisar:

- manifiestos;
- lockfiles;
- versiones de runtime;
- imports utilizados;
- dependencias faltantes;
- dependencias sin uso;
- incompatibilidades;
- reproducibilidad;
- paquetes abandonados;
- vulnerabilidades conocidas según herramientas disponibles;
- coherencia entre manifiestos y lockfiles;
- dependencias transitivas;
- restricciones de versión;
- paquetes duplicados o incompatibles.

Distinguir entre:

- vulnerabilidad reportada;
- vulnerabilidad aplicable;
- vulnerabilidad explotable;
- dependencia transitiva;
- falso positivo.

No instalar ni actualizar dependencias durante la auditoría salvo autorización expresa y cuando sea indispensable para una validación segura.

## Tests

Analizar:

- pruebas unitarias;
- integración;
- end-to-end;
- regresión;
- casos límite;
- validaciones;
- manejo de errores;
- determinismo;
- flakiness;
- fixtures;
- mocks;
- cobertura de componentes críticos;
- pruebas ausentes para bugs detectados;
- pruebas que no verifican realmente el comportamiento;
- tests deshabilitados o condicionados;
- aislamiento del entorno.

No eliminar, desactivar, omitir ni debilitar pruebas para conseguir resultados exitosos.

## Seguridad

Revisar según el stack:

- secretos versionados;
- credenciales;
- tokens;
- permisos;
- autenticación;
- autorización;
- validación de entradas;
- inyecciones;
- traversal;
- SSRF;
- XSS;
- CSRF;
- CORS;
- deserialización insegura;
- ejecución de comandos;
- archivos subidos;
- criptografía;
- sesiones;
- cookies;
- JWT;
- información sensible en logs;
- dependencias vulnerables;
- configuración insegura;
- permisos de CI/CD;
- superficies administrativas;
- exposición accidental de endpoints;
- manejo de errores con información sensible;
- privilegios excesivos.

No mostrar secretos completos.

Informar únicamente:

- tipo;
- ubicación;
- alcance;
- riesgo;
- acción necesaria.

## Datos y persistencia

Revisar:

- integridad;
- validación;
- schemas;
- migraciones;
- constraints;
- relaciones;
- transacciones;
- locking;
- concurrencia;
- escrituras atómicas;
- duplicados;
- sobrescritura;
- recuperación;
- retención;
- eliminación;
- corrupción;
- compatibilidad de formatos;
- timestamps;
- zonas horarias;
- normalización;
- claves;
- índices;
- serialización;
- compatibilidad hacia atrás.

No ejecutar migraciones ni modificar datos reales durante la auditoría.

## Rendimiento

Buscar únicamente problemas relevantes y demostrables:

- complejidad algorítmica;
- cálculos repetidos;
- consultas N+1;
- carga excesiva;
- llamadas duplicadas;
- bloqueos;
- memory leaks;
- streams o archivos no cerrados;
- operaciones síncronas costosas;
- paginación ausente;
- caching incorrecto;
- procesamiento redundante;
- reintentos excesivos;
- serializaciones innecesarias;
- degradación observable en rutas críticas.

No recomendar optimizaciones hipotéticas sin evidencia.

## Integraciones externas

Revisar:

- contratos;
- autenticación;
- timeouts;
- retries;
- backoff;
- rate limits;
- paginación;
- respuestas parciales;
- schemas;
- errores;
- idempotencia;
- caching;
- fallback;
- consumo de cuota;
- trazabilidad;
- comportamiento ante indisponibilidad;
- circuit breakers;
- duplicación de operaciones;
- consistencia eventual;
- límites del proveedor.

No efectuar escrituras externas, consumir servicios de pago ni operar sobre producción durante la auditoría.
