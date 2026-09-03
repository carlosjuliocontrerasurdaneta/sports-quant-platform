# Descubrimiento y cobertura

## Contenidos

- Fase 0 — Descubrimiento y cobertura
- Estratificación por criticidad P0–P3
- Estados de cobertura
- Matriz obligatoria

---
# Fase 0 — Descubrimiento y cobertura

Antes de buscar defectos, construir un inventario verificable del proyecto.

Identificar:

- propósito y dominio;
- arquitectura;
- estructura de directorios;
- lenguajes y versiones;
- frameworks;
- puntos de entrada;
- módulos y componentes;
- scripts;
- configuración;
- variables de entorno;
- manifiestos y lockfiles;
- dependencias;
- almacenamiento y persistencia;
- esquemas y migraciones;
- APIs;
- integraciones externas;
- procesos síncronos y asíncronos;
- modelos estadísticos o de machine learning;
- pruebas;
- CI/CD;
- contenedores;
- infraestructura declarativa;
- documentación;
- sistema de Skills e instrucciones para agentes cuando exista;
- agentes, loops, comandos, routing y orquestación relacionados con esas Skills;
- código generado;
- código vendorizado;
- código experimental;
- archivos, directorios y recursos potencialmente obsoletos;
- duplicados y copias históricas;
- artefactos generados o reconstruibles;
- archivos potencialmente huérfanos;
- archivos inaccesibles;
- archivos excluidos;
- áreas no verificables.

## Estratificación por criticidad

Para repositorios grandes, clasificar componentes antes de profundizar:

### P0 — Críticos

- ejecución principal;
- autenticación;
- autorización;
- seguridad;
- integridad de datos;
- persistencia;
- pagos;
- dinero;
- lógica principal de negocio;
- modelos en producción;
- decisiones cuantitativas;
- componentes cuyo fallo pueda causar daño material.

### P1 — Relevantes

- servicios utilizados activamente;
- APIs;
- integraciones;
- workers;
- pipelines;
- módulos compartidos;
- configuración de producción;
- observabilidad;
- pruebas de rutas críticas.

### P2 — Auxiliares

- herramientas internas;
- scripts de soporte;
- utilidades;
- administración;
- tareas de desarrollo.

### P3 — Bajo impacto o revisión limitada

- código legado no alcanzable;
- código experimental;
- ejemplos;
- artefactos de build;
- caches;
- código generado;
- código vendorizado.

La prioridad regula la profundidad y el orden de revisión, pero no elimina áreas de la matriz de cobertura.

## Cobertura

Clasificar cada área como:

- `REVISADA`
- `REVISADA_PARCIALMENTE`
- `NO_APLICABLE`
- `NO_VERIFICABLE`
- `EXCLUIDA`

Toda exclusión debe indicar la razón.

`FULL AUDIT` significa que todas las áreas identificadas en el inventario tienen una disposición explícita en la matriz de cobertura.

No significa que todas las áreas hayan podido validarse dinámicamente.

No declarar que la auditoría es exhaustiva sin presentar una matriz de cobertura.

## Matriz obligatoria

Para cada área indicar:

| Área | Prioridad | Estado | Componentes/archivos | Método | Validación | Limitaciones |
|---|---|---|---|---|---|---|

`REVISADA` no debe utilizarse sin indicar al menos el método aplicado y los componentes cubiertos.
