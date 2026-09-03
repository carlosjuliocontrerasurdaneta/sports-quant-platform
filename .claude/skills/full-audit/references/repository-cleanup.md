# Limpieza y racionalización del repositorio

## Contenidos

- Candidatos a revisar
- Ausencia de referencias vs. inutilidad
- Clasificación de candidatos de limpieza
- Evidencia mínima
- Regla de causa raíz
- Regla de seguridad

---
## Limpieza y racionalización del repositorio

Auditar también si el repositorio contiene archivos, directorios, recursos o artefactos que ya no cumplen una función verificable.

El objetivo es identificar con evidencia elementos que puedan eliminarse o consolidarse de forma segura, no reducir el repositorio por estética, antigüedad o preferencia.

### Candidatos a revisar

Buscar, cuando corresponda:

- archivos huérfanos;
- módulos sin consumidores verificables;
- scripts reemplazados;
- configuraciones obsoletas;
- comandos o workflows retirados;
- documentación duplicada o superada por una fuente canónica;
- copias históricas innecesarias;
- backups accidentales;
- archivos temporales persistidos;
- outputs generados que no deban versionarse;
- artefactos de build versionados sin necesidad;
- caches;
- fixtures o datasets de prueba sin consumidores;
- recursos auxiliares abandonados;
- directorios vacíos o funcionalmente vacíos;
- código experimental abandonado;
- implementaciones reemplazadas que continúan en el árbol;
- archivos cuyo contenido esté duplicado por una fuente canónica;
- referencias residuales a componentes retirados;
- archivos de compatibilidad cuya necesidad ya no pueda establecerse.

### No confundir ausencia de referencias con inutilidad

Un archivo no se considera eliminable únicamente porque una búsqueda textual no encuentre referencias.

Antes de proponer su eliminación, comprobar según corresponda:

- imports directos e indirectos;
- imports dinámicos;
- descubrimiento por convención;
- entry points;
- plugins;
- registries;
- globs y carga por patrones;
- rutas construidas dinámicamente;
- configuración;
- manifiestos;
- empaquetado;
- tests;
- scripts;
- CI/CD;
- contenedores;
- tareas programadas;
- documentación operacional;
- agentes, Skills, loops y comandos;
- consumidores externos documentados;
- generación de artefactos;
- compatibilidad hacia atrás;
- migraciones;
- carga de recursos en runtime;
- referencias desde otros lenguajes del repositorio.

Si la utilización depende de infraestructura, servicios, configuración externa o consumidores no disponibles, clasificar como `NO_VERIFICABLE` en lugar de asumir que el elemento está sin uso.

### Clasificación de candidatos de limpieza

Clasificar cada candidato como:

#### ELIMINABLE_CONFIRMADO

Existe evidencia suficiente de que el elemento no participa en ninguna ruta vigente relevante y su eliminación no rompe un contrato conocido.

#### REDUNDANTE_CONFIRMADO

El elemento duplica funcionalidad, contenido o responsabilidad de una fuente canónica verificable y puede retirarse preservando esa fuente.

#### OBSOLETO_REEMPLAZADO

Existe evidencia de que fue sustituido por otro componente vigente y no conserva una obligación de compatibilidad conocida.

#### GENERADO_RECONSTRUIBLE

Es un artefacto derivado que puede reconstruirse de forma determinista desde fuentes versionadas y no existe una razón contractual para versionarlo.

#### CONSERVAR

La revisión demuestra que el elemento sigue siendo necesario o que su presencia es deliberada.

#### NO_VERIFICABLE

No existe evidencia suficiente para decidir de forma segura si puede eliminarse.

Solo `ELIMINABLE_CONFIRMADO`, `REDUNDANTE_CONFIRMADO`, `OBSOLETO_REEMPLAZADO` y `GENERADO_RECONSTRUIBLE` pueden entrar en un plan de eliminación.

### Evidencia mínima para proponer eliminación

Para cada elemento propuesto registrar:

- ruta exacta;
- tipo de elemento;
- categoría;
- tamaño cuando sea relevante;
- función histórica o aparente;
- consumidores buscados;
- referencias encontradas;
- evidencia de no utilización o sustitución;
- fuente canónica o reemplazo, si existe;
- contratos potencialmente afectados;
- impacto esperado;
- riesgo;
- método de restauración o reversión cuando exista;
- validaciones necesarias después de eliminarlo.

Cuando Git esté disponible, utilizar su historial como evidencia adicional para comprender:

- origen;
- cambios relevantes;
- reemplazos;
- renombrados;
- consumidores históricos;
- si el archivo es versionado o no versionado.

La antigüedad, por sí sola, no demuestra que un archivo sea innecesario.

### Regla de causa raíz para limpieza

No crear un hallazgo independiente por cada archivo cuando varios residuos provengan de una misma causa raíz, por ejemplo:

- una migración incompleta;
- una feature retirada;
- una estructura duplicada;
- un generador que versiona outputs;
- una reestructuración que dejó restos.

Agruparlos cuando compartan causa, corrección y riesgo, manteniendo el inventario exacto de rutas afectadas.

### Regla de seguridad

Durante las fases 0–3:

- no eliminar archivos;
- no mover archivos;
- no renombrar archivos;
- no limpiar directorios;
- no ejecutar `git clean`;
- no ejecutar comandos de cleanup;
- no alterar `.gitignore` para ocultar candidatos;
- no borrar artefactos para comprobar si "algo se rompe".

La ausencia de fallos después de una eliminación experimental no sustituye el análisis previo.

Toda eliminación se trata como una modificación y requiere autorización explícita en Fase 4.
