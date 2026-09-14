# Verificación independiente de remediación

## OBJETIVO

Verifica de forma independiente las correcciones realizadas durante la fase de remediación.

Archivos principales:

`audits/consolidated/latest.md`

`audits/remediation/latest.md`

La verificación deberá contrastarse directamente contra el código actual.

Esta fase es de **verificación**, no de corrección.

No modifiques código fuente para conseguir que un hallazgo pase la validación.

Genera:

`audits/verification/latest.md`

Antes de sobrescribir una verificación anterior, archívala, cuando sea posible, en:

`audits/verification/history/YYYY-MM-DD-HHMM.md`

---

# 1. Principio de independencia

No asumas que una corrección es correcta porque:

- el agente de remediación lo afirma;
- existe un commit;
- los tests pasan;
- el código cambió;
- desapareció el patrón original.

Verifica cada criterio contra evidencia actual.

El código actual es la fuente de verdad.

---

# 2. No corregir durante esta fase

No modifiques:

- código;
- tests;
- configuración;
- dependencias;
- migraciones;

para conseguir que la verificación resulte satisfactoria.

Si detectas un problema, regístralo.

La separación entre remediación y verificación es intencional.

---

# 3. Preparación

Antes de verificar:

1. determina la raíz;
2. lee las instrucciones aplicables del repositorio;
3. identifica el estado Git;
4. lee `audits/consolidated/latest.md`;
5. lee `audits/remediation/latest.md`;
6. identifica los hallazgos procesados;
7. identifica criterios de aceptación;
8. identifica pruebas de regresión;
9. identifica cambios realizados.

---

# 4. Hallazgos a verificar

Prioriza:

1. P0
2. P1
3. P2
4. P3
5. P4

Verifica obligatoriamente todos los hallazgos que la remediación marque como:

- Corregido
- Pendiente de validación independiente

No cierres automáticamente hallazgos marcados:

- Bloqueado
- No reproducible
- No aplicable

Revísalos según la evidencia disponible.

---

# 5. Verificación por hallazgo

Para cada ID:

## Paso 1 — Revisar problema original

Comprende:

- causa raíz;
- evidencia;
- impacto;
- escenario;
- criterio de aceptación.

## Paso 2 — Revisar cambio

Inspecciona el diff o implementación actual.

Comprueba que:

- aborda la causa raíz;
- no solo oculta el síntoma;
- no desactiva una validación;
- no elimina una prueba;
- no reduce seguridad;
- no introduce bypass;
- no desplaza el fallo.

## Paso 3 — Reproducir escenario

Cuando sea seguro:

- reproduce el escenario original;
- ejecuta la prueba de regresión;
- ejecuta tests relevantes.

## Paso 4 — Comprobar criterio de aceptación

Evalúa cada requisito explícitamente.

## Paso 5 — Buscar regresiones

Revisa efectos en:

- callers;
- módulos dependientes;
- APIs;
- datos;
- errores;
- rendimiento;
- seguridad;
- concurrencia;
- compatibilidad.

---

# 6. Estados de verificación

Asigna uno:

## Verificado — Corregido

Existe evidencia suficiente de que la causa raíz fue corregida y el criterio de aceptación se cumple.

## Verificado — Mitigado

El riesgo fue reducido de forma suficiente, pero existe riesgo residual documentado.

## Reabierto

El problema continúa presente total o parcialmente.

## Regresión

La corrección introdujo un problema nuevo materialmente relacionado.

## No verificable

El entorno no permite obtener evidencia suficiente.

## No aplicable

Existe evidencia suficiente de que el hallazgo original no era aplicable al estado actual.

---

# 7. Pruebas

Ejecuta cuando corresponda:

- prueba de regresión;
- tests unitarios relacionados;
- integración;
- E2E;
- lint;
- type-checking;
- build;
- análisis estático.

No necesitas ejecutar indiscriminadamente todos los controles para cada hallazgo si no aportan evidencia relevante.

Al final, ejecuta una validación global razonable.

---

# 8. Verificación de seguridad

Para correcciones de seguridad, verifica específicamente:

- autenticación;
- autorización;
- validación;
- paths alternativos;
- controles compensatorios;
- errores;
- exposición de datos.

Una corrección que solo bloquea un caso específico pero mantiene vías equivalentes vulnerables no debe cerrarse.

---

# 9. Verificación de datos

Para correcciones de datos:

- comprueba integridad;
- consistencia;
- compatibilidad;
- migraciones;
- transacciones;
- idempotencia;
- casos existentes.

No ejecutes operaciones destructivas.

---

# 10. Verificación de concurrencia

Cuando el hallazgo involucre concurrencia:

- revisa sincronización;
- atomicidad;
- locks;
- transacciones;
- orden de ejecución;
- idempotencia;
- reintentos.

No declares resuelta una carrera únicamente porque no se reproduzca en una ejecución.

Analiza también la corrección estructural.

---

# 11. Verificación de rendimiento

Cuando corresponda:

- verifica que la operación problemática cambió;
- compara complejidad o número de operaciones cuando sea posible;
- evita conclusiones basadas en microbenchmarks irrelevantes;
- documenta ausencia de métricas cuando limite la validación.

---

# 12. Regresiones

Si detectas una regresión relacionada con una corrección:

crea un registro:

`REG-XXX`

Incluye:

- cambio relacionado;
- hallazgo original;
- evidencia;
- impacto;
- severidad;
- recomendación.

No la corrijas durante esta fase.

---

# 13. Cierre

Un hallazgo solo puede quedar como **Verificado — Corregido** cuando:

- la causa raíz fue abordada;
- el escenario original ya no produce el defecto;
- el criterio de aceptación se cumple;
- las pruebas relevantes son satisfactorias;
- no existe una regresión evidente relacionada;
- no se trasladó el defecto.

---

# 14. Severidad de regresiones

Para nuevas regresiones utiliza:

`Puntuación = (I × 30 + A × 20 + P × 20 + E × 15 + R × 10 + C × 5) / 4`

Clasificación:

- 90–100: Crítica
- 70–89,9: Alta
- 40–69,9: Media
- 15–39,9: Baja
- 0–14,9: Informativa

No recalcules innecesariamente la severidad del hallazgo original si su naturaleza no cambió.

---

# 15. Tabla de verificación

Incluye:

| ID | Severidad | Prioridad | Estado remediación | Estado verificación | Criterio aceptación | Regresión | Evidencia |
|---|---|---|---|---|---|---|---|

---

# 16. Tabla de regresiones

Cuando existan:

| ID | Hallazgo original | Regresión | Severidad | Evidencia | Acción recomendada |
|---|---|---|---|---|---|

---

# 17. Métricas finales

Incluye:

- hallazgos verificados;
- corregidos;
- mitigados;
- reabiertos;
- no verificables;
- no aplicables;
- regresiones;
- P0 aún abiertos;
- P1 aún abiertos.

---

# 18. Actualización del backlog

No destruyas ni sobrescribas el informe consolidado original.

Genera además, cuando sea posible:

`audits/consolidated/status.md`

Este archivo debe representar el estado actualizado de los IDs existentes después de la verificación.

Debe contener:

| ID | Estado actual | Severidad | Prioridad | Verificación | Próxima acción |
|---|---|---|---|---|---|

El histórico original permanece intacto.

---

# 19. Informe final

Genera:

`audits/verification/latest.md`

Contenido:

1. Resumen ejecutivo
2. Alcance
3. Metodología
4. Limitaciones
5. Hallazgos verificados
6. Corregidos
7. Mitigados
8. Reabiertos
9. No verificables
10. No aplicables
11. Regresiones
12. Validación global
13. P0/P1 pendientes
14. Tabla maestra
15. Recomendaciones de siguiente acción
16. Anexo de comandos

---

# 20. Decisión final

Al finalizar, determina una de estas situaciones:

## APTO

No quedan P0/P1 abiertos atribuibles a la remediación y las validaciones relevantes son satisfactorias.

## APTO CON PENDIENTES

No existen bloqueos críticos, pero permanecen hallazgos que requieren trabajo planificado.

## NO APTO

Persisten P0/P1 materiales, existen regresiones graves o la evidencia demuestra que correcciones importantes no son válidas.

## VERIFICACIÓN INCOMPLETA

Las limitaciones del entorno impiden obtener evidencia suficiente.

No utilices `APTO` como afirmación absoluta de ausencia de defectos. Significa únicamente que la remediación evaluada superó los criterios definidos.

Al terminar, responde brevemente con:

- estado final;
- corregidos;
- reabiertos;
- regresiones;
- P0 abiertos;
- P1 abiertos;
- ruta del informe.