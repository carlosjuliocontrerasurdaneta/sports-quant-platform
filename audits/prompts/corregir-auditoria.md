# Remediación controlada de auditoría

## OBJETIVO

Corrige de forma controlada, verificable y trazable los hallazgos contenidos en:

`audits/consolidated/latest.md`

Esta ejecución corresponde a la fase de **remediación**.

No vuelvas a realizar una auditoría general del repositorio salvo que sea estrictamente necesario para comprender o corregir un hallazgo.

El repositorio actual es la fuente de verdad.

El informe consolidado define el backlog de trabajo, pero cada hallazgo deberá volver a verificarse antes de modificar código.

---

# 1. Principios obligatorios

Trabaja según estos principios:

1. corregir causa raíz, no síntomas;
2. realizar el cambio mínimo correcto;
3. evitar modificaciones no relacionadas;
4. preservar comportamiento correcto existente;
5. añadir pruebas de regresión cuando corresponda;
6. validar cada corrección;
7. mantener trazabilidad;
8. evitar cambios destructivos;
9. detener una corrección individual si existe incertidumbre material, sin detener innecesariamente el resto del proceso;
10. no marcar como corregido algo que no haya sido verificado.

No conviertas esta ejecución en una refactorización general.

---

# 2. Instrucciones del repositorio

Antes de modificar código:

1. determina la raíz del repositorio;
2. lee las instrucciones aplicables, como `AGENTS.md`, `CLAUDE.md` u otros archivos equivalentes;
3. identifica convenciones de código;
4. identifica comandos de test;
5. identifica lint;
6. identifica type-checking;
7. identifica build;
8. identifica políticas de migraciones;
9. identifica requisitos de CI/CD;
10. determina el estado actual de Git.

Respeta las instrucciones aplicables del proyecto.

---

# 3. Estado inicial

Antes de corregir cualquier hallazgo, registra:

- branch actual;
- commit actual, cuando exista;
- estado del working tree;
- cambios preexistentes;
- tests inicialmente fallidos, si pueden determinarse razonablemente;
- limitaciones del entorno.

No atribuyas a esta remediación cambios o fallos que ya existían previamente.

No sobrescribas cambios preexistentes del usuario.

---

# 4. Fuente de trabajo

Lee:

`audits/consolidated/latest.md`

Extrae:

- IDs;
- prioridad;
- severidad;
- confianza;
- ubicación;
- evidencia;
- causa raíz;
- recomendación;
- criterio de aceptación;
- prueba de regresión sugerida;
- estado.

No leas los informes originales de Claude u OpenAI salvo que el consolidado no contenga información suficiente para comprender un hallazgo.

---

# 5. Orden de remediación

Trabaja por prioridad:

1. P0
2. P1
3. P2
4. P3
5. P4

Dentro de una misma prioridad, considera:

1. mayor severidad;
2. mayor confianza;
3. dependencias entre hallazgos;
4. causas raíz compartidas;
5. riesgo de regresión;
6. alcance del cambio.

No ejecutes automáticamente todos los hallazgos en un único cambio lógico.

Agrupa únicamente hallazgos que compartan claramente:

- causa raíz;
- componente;
- solución;
- pruebas.

---

# 6. Lotes de corrección

Divide el trabajo en lotes pequeños y coherentes.

Cada lote deberá tener:

- uno o varios IDs relacionados;
- objetivo;
- archivos previstos;
- riesgo;
- criterios de aceptación;
- pruebas necesarias.

Evita lotes que mezclen:

- seguridad;
- arquitectura;
- datos;
- UI;
- infraestructura;

si no comparten causa raíz.

---

# 7. Verificación previa de cada hallazgo

Antes de modificar código para un hallazgo:

1. localiza la evidencia;
2. confirma que el código actual sigue afectado;
3. verifica que no haya sido corregido previamente;
4. identifica la causa raíz;
5. identifica controles existentes;
6. determina el cambio mínimo necesario;
7. identifica pruebas relevantes.

Clasifica el resultado previo como:

- Confirmado
- Ya corregido
- Parcialmente corregido
- No reproducible
- No aplicable
- Requiere información adicional

No modifiques código para un hallazgo que ya no sea aplicable.

---

# 8. Corrección

Cuando el hallazgo esté confirmado:

1. corrige la causa raíz;
2. evita workarounds innecesarios;
3. evita silenciar errores sin resolverlos;
4. evita desactivar validaciones;
5. evita ampliar permisos;
6. evita eliminar tests para conseguir resultados verdes;
7. evita cambiar expectativas correctas para ocultar fallos;
8. conserva compatibilidad cuando sea razonablemente necesaria;
9. actualiza documentación solo cuando el cambio lo requiera;
10. modifica configuración únicamente cuando forme parte legítima de la solución.

---

# 9. Cambios de arquitectura

Para hallazgos arquitectónicos:

- prioriza cambios incrementales;
- evita reescrituras completas salvo necesidad demostrable;
- conserva interfaces existentes cuando sea razonable;
- identifica dependencias;
- valida flujos principales.

Un hallazgo de arquitectura no autoriza automáticamente un refactor global.

---

# 10. Seguridad

Para hallazgos de seguridad:

- no reproduzcas secretos;
- no uses credenciales reales contra servicios;
- no desactives controles existentes;
- no introduzcas bypass temporales;
- corrige la causa raíz;
- añade pruebas negativas cuando sea razonable;
- verifica autorización además de autenticación cuando corresponda.

Si la corrección requiere rotación de credenciales externa, no la ejecutes automáticamente. Documenta la acción manual necesaria.

---

# 11. Datos y migraciones

Cuando una corrección afecte persistencia:

- protege integridad;
- considera compatibilidad;
- evalúa datos existentes;
- evita migraciones destructivas sin autorización explícita;
- evalúa rollback;
- considera transacciones;
- verifica idempotencia cuando corresponda.

Si una migración puede provocar pérdida de datos, no la ejecutes automáticamente.

---

# 12. Dependencias

Antes de actualizar dependencias:

1. confirma que la actualización aborda el hallazgo;
2. revisa compatibilidad;
3. minimiza saltos innecesarios;
4. actualiza lockfile cuando corresponda;
5. ejecuta pruebas relevantes;
6. verifica cambios de API.

No actualices todo el árbol de dependencias sin necesidad.

---

# 13. Pruebas de regresión

Cuando un defecto sea reproducible mediante una prueba automatizable:

1. crea o adapta una prueba que represente el fallo;
2. confirma, cuando sea razonable, que la prueba habría detectado el defecto;
3. implementa la corrección;
4. verifica que la prueba pase;
5. ejecuta pruebas relacionadas.

La prueba debe validar comportamiento, no detalles innecesarios de implementación.

---

# 14. Validación por hallazgo

Después de cada corrección:

- verifica el criterio de aceptación;
- ejecuta la prueba de regresión;
- ejecuta tests relacionados;
- ejecuta lint relevante;
- ejecuta type-checking relevante;
- ejecuta build cuando corresponda;
- inspecciona el diff.

No marques un hallazgo como corregido únicamente porque el código compile.

---

# 15. Validación por lote

Después de cada lote:

1. ejecuta pruebas específicas;
2. ejecuta controles estáticos relevantes;
3. revisa el diff;
4. comprueba que no existan cambios no relacionados;
5. verifica criterios de aceptación;
6. registra resultados.

Si el lote introduce una regresión, corrígela antes de continuar cuando sea razonablemente atribuible al lote.

---

# 16. Validación global

Cuando termines todos los lotes autorizados:

ejecuta, cuando estén disponibles y sean razonables:

- tests completos;
- lint;
- type-checking;
- build;
- pruebas de integración relevantes.

Distingue claramente:

- controles ejecutados;
- controles no ejecutados;
- controles fallidos por causas preexistentes;
- controles fallidos por cambios actuales;
- controles imposibles de ejecutar.

---

# 17. Prohibiciones

No:

- hagas push;
- despliegues;
- publiques paquetes;
- borres datos;
- ejecutes comandos destructivos;
- reescribas historial Git;
- hagas force push;
- elimines tests válidos;
- reduzcas controles de seguridad;
- ocultes errores;
- alteres informes anteriores para simular correcciones;
- marques hallazgos como resueltos sin evidencia.

---

# 18. Registro de remediación

Genera:

`audits/remediation/latest.md`

Antes de sobrescribir un informe anterior, archívalo, cuando sea posible, en:

`audits/remediation/history/YYYY-MM-DD-HHMM.md`

---

# 19. Formato de cada corrección

Incluye:

## ID

ID consolidado.

## Estado inicial

- Confirmado
- Ya corregido
- Parcialmente corregido
- No reproducible
- No aplicable

## Causa raíz

Descripción breve y basada en evidencia.

## Archivos modificados

Lista exacta.

## Cambio realizado

Explicación precisa.

## Prueba de regresión

Indica:

- añadida;
- modificada;
- existente suficiente;
- no aplicable.

## Validaciones ejecutadas

Incluye comandos y resultados.

## Criterio de aceptación

Indica si se cumple.

## Estado final

- Corregido
- Pendiente de validación independiente
- Bloqueado
- No aplicable

## Riesgos residuales

Indícalos cuando existan.

---

# 20. Tabla maestra de remediación

Incluye:

| ID | Prioridad | Severidad | Estado inicial | Estado final | Archivos modificados | Tests | Criterio de aceptación |
|---|---|---|---|---|---|---|---|

---

# 21. No modificar el consolidado como fuente histórica

No reescribas `audits/consolidated/latest.md` para hacer desaparecer hallazgos.

El informe consolidado representa el estado detectado antes de la remediación.

La fase posterior de verificación determinará qué hallazgos pueden cerrarse.

---

# 22. Resultado final

El informe:

`audits/remediation/latest.md`

deberá incluir:

1. Resumen
2. Estado inicial
3. Hallazgos procesados
4. Hallazgos corregidos
5. Hallazgos ya corregidos
6. Hallazgos bloqueados
7. Hallazgos no aplicables
8. Cambios realizados
9. Pruebas de regresión
10. Validaciones ejecutadas
11. Fallos preexistentes
12. Riesgos residuales
13. Tabla maestra
14. Cambios pendientes de verificación independiente
15. Anexo de comandos

Al terminar, no declares el proyecto completamente corregido.

Indica que las correcciones quedan pendientes de la fase independiente:

`verificar-remediacion.md`