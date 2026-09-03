# Validación, planificación, corrección y validación final

## Contenidos

- Fase 2 — Validación independiente
- Fase 3 — Plan de corrección
- Fase 4 — Corrección
- Fase 5 — Validación final
- Reglas especiales para eliminaciones autorizadas

---
# Fase 2 — Validación independiente

Revisar nuevamente cada candidato mediante al menos un método adicional que aporte evidencia independiente.

La segunda validación no puede consistir únicamente en repetir el mismo razonamiento inicial.

Métodos válidos, según corresponda:

- análisis estático + prueba de reproducción;
- análisis de flujo + inspección de callers;
- alerta SAST + revisión manual;
- test existente + test mínimo de reproducción;
- configuración + comportamiento documentado;
- Skill o instrucción + routing, loop o consumidor que la ejecuta;
- dependencia vulnerable + comprobación de reachability;
- revisión de contrato + implementación;
- implementación + integración que la consume;
- análisis de esquema + ruta de escritura;
- modelo + pipeline de datos;
- backtest + construcción temporal de features;
- comportamiento observado + código que lo produce.

Para cada candidato:

1. revisar callers y flujos relacionados;
2. buscar validaciones o protecciones existentes;
3. contrastar configuración, pruebas y documentación;
4. buscar contraejemplos;
5. intentar una reproducción segura cuando sea posible;
6. determinar si el comportamiento es intencional;
7. reevaluar severidad;
8. reevaluar confianza;
9. asignar su estado final:
   - `REPRODUCIDO`;
   - `VERIFICADO_ESTÁTICAMENTE`;
   - `INFERIDO`;
   - `NO_VERIFICABLE`;
   - `DESCARTADO`;
10. aplicar la regla formal:
    - `CONFIRMADO` únicamente si el estado final es `REPRODUCIDO` o `VERIFICADO_ESTÁTICAMENTE`;
    - `INFERIDO`, `NO_VERIFICABLE` y `DESCARTADO` nunca son defectos confirmados;
    - `DETECTADO_POR_HERRAMIENTA` no puede quedar como estado final.

No eliminar silenciosamente falsos positivos.

Conservar los descartados relevantes en un apartado separado indicando:

- sospecha inicial;
- evidencia revisada;
- motivo del descarte.

No limitarse a repetir el razonamiento inicial.

---

# Fase 3 — Plan de corrección

Generar un plan ordenado por:

1. defectos `CRITICAL`;
2. defectos `HIGH`;
3. seguridad e integridad de datos;
4. riesgos operacionales;
5. defectos `MEDIUM`;
6. pruebas y regresiones;
7. defectos `LOW`;
8. deuda técnica;
9. limpieza y racionalización confirmada;
10. mejoras opcionales.

Para cada acción indicar:

- IDs relacionados;
- archivos previstos;
- cambio mínimo;
- dependencias;
- riesgo;
- pruebas requeridas;
- criterio de aceptación;
- orden de implementación.

Para cualquier eliminación propuesta añadir además:

- rutas exactas;
- categoría de limpieza;
- evidencia que demuestra que cada ruta puede retirarse;
- consumidores y contratos comprobados;
- reemplazo o fuente canónica, cuando exista;
- riesgo de referencias rotas;
- método de reversión cuando esté disponible;
- validaciones posteriores obligatorias.

No modificar archivos todavía.

Entregar el informe y esperar aprobación explícita.

La aprobación debe identificar:

- IDs concretos;
- grupos de IDs;
- categorías concretas;
- o un alcance inequívoco de cambios autorizados.

---

# Fase 4 — Corrección

Ejecutar esta fase únicamente después de recibir aprobación expresa.

Antes de modificar:

1. confirmar los IDs aprobados;
2. releer las instrucciones aplicables;
3. inspeccionar nuevamente el estado de Git;
4. identificar cambios preexistentes;
5. determinar si cada defecto es:
   - preexistente;
   - introducido por cambios locales;
   - de origen temporal no determinable;
6. detectar solapamientos;
7. mostrar los archivos afectados;
8. mostrar el plan exacto de cambios.

Corregir únicamente los elementos aprobados.

Aplicar el parche mínimo que resuelva la causa confirmada.

Preservar, salvo autorización expresa:

- lógica de negocio válida;
- comportamiento funcional;
- configuración no relacionada;
- interfaces públicas;
- compatibilidad;
- esquemas;
- modelos;
- estrategias;
- parámetros;
- criterios de decisión;
- datos históricos.

No realizar:

- refactorizaciones masivas;
- cambios cosméticos no relacionados;
- limpieza oportunista;
- renombrados no necesarios;
- actualizaciones de dependencias no requeridas.

No eliminar archivos salvo que la eliminación forme parte de un hallazgo de limpieza confirmado y haya sido aprobada explícitamente.

Incluso con aprobación, no eliminar automáticamente:

- archivos no versionados cuya procedencia o función no esté verificada;
- archivos ambiguos;
- archivos cuyo estado haya cambiado desde la auditoría;
- elementos clasificados como `NO_VERIFICABLE`;
- elementos que contengan cambios preexistentes del usuario no incluidos expresamente en la aprobación.

Para una eliminación autorizada:

1. volver a verificar la ruta y su estado actual;
2. confirmar que el hallazgo y la evidencia siguen vigentes;
3. comprobar nuevamente consumidores y referencias relevantes;
4. registrar exactamente qué se eliminará;
5. aplicar únicamente las eliminaciones aprobadas;
6. detenerse si aparece una dependencia nueva o una ambigüedad.

No ejecutar:

- operaciones destructivas;
- migraciones irreversibles;
- acciones externas;
- cambios de producción;

sin autorización explícita.

---

# Fase 5 — Validación final

Después de cada conjunto lógico de correcciones:

1. ejecutar la prueba específica del defecto;
2. ejecutar las pruebas del componente;
3. ejecutar validaciones estáticas pertinentes;
4. ejecutar la suite de regresión relevante;
5. ejecutar la suite completa cuando sea viable y segura;
6. revisar el diff;
7. comprobar configuración;
8. comprobar manifiestos;
9. comprobar lockfiles;
10. buscar regresiones accidentales;
11. revisar nuevamente las áreas afectadas;
12. si se eliminaron archivos o directorios:
    - buscar referencias rotas a las rutas eliminadas;
    - comprobar imports, registries, entry points y carga dinámica aplicables;
    - comprobar manifiestos, empaquetado, CI/CD, contenedores y scripts afectados;
    - ejecutar los tests que cubrían a los consumidores identificados;
    - comprobar que no se eliminó una fuente canónica por error;
    - comprobar que los artefactos `GENERADO_RECONSTRUIBLE` realmente puedan regenerarse cuando esa validación sea segura;
    - revisar `git diff --check` y el diff completo de eliminaciones.

Distinguir entre:

- validaciones exitosas;
- validaciones fallidas;
- fallos preexistentes;
- regresiones introducidas;
- validaciones no ejecutables.

No afirmar éxito si una comprobación no se ejecutó.

Entregar:

- IDs corregidos;
- cambios realizados;
- archivos modificados;
- comandos ejecutados;
- resultados;
- pruebas añadidas;
- pruebas modificadas;
- regresiones detectadas;
- riesgos pendientes;
- limitaciones;
- validaciones no ejecutadas y su causa.
