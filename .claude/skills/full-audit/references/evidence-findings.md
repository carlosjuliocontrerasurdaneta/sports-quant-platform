# Evidencia y clasificación de hallazgos

## Contenidos

- Taxonomía de evidencia
- Estado intermedio DETECTADO_POR_HERRAMIENTA
- Estados finales
- Definición formal de CONFIRMADO
- Severidad
- Nivel de confianza
- Evidencia obligatoria
- Regla de causa raíz

---
# Taxonomía de evidencia

## Flujo de clasificación

Todo problema debe seguir este flujo:

`CANDIDATO → EVIDENCIA INICIAL → VALIDACIÓN → ESTADO FINAL`

`DETECTADO_POR_HERRAMIENTA` es un estado intermedio de evidencia inicial, no un estado final.

### Estado intermedio: DETECTADO_POR_HERRAMIENTA

Una herramienta produjo el candidato, pero su aplicabilidad todavía debe comprobarse mediante validación independiente.

No constituye por sí solo un defecto confirmado y no puede permanecer como estado final después de completar la validación.

## Estados finales permitidos

### REPRODUCIDO

El defecto fue activado mediante una ejecución controlada y se observó el resultado incorrecto.

### VERIFICADO_ESTÁTICAMENTE

La ruta defectuosa está demostrada directamente y de forma concluyente por el código, la configuración o un contrato verificable, sin requerir ejecución adicional.

Un hallazgo `VERIFICADO_ESTÁTICAMENTE` tiene confianza `HIGH`.

### INFERIDO

Existe evidencia razonable, incluida evidencia estática fuerte pero no concluyente, pero falta una condición, contexto o validación necesaria.

### NO_VERIFICABLE

No puede comprobarse por ausencia de:

- dependencias;
- datos;
- credenciales;
- servicios;
- sistema operativo;
- infraestructura;
- permisos;
- entorno requerido.

### DESCARTADO

La revisión adicional demostró que la sospecha inicial no era un defecto.

## Definición formal de CONFIRMADO

`CONFIRMADO = REPRODUCIDO OR VERIFICADO_ESTÁTICAMENTE`

Solo un candidato cuyo estado final sea `REPRODUCIDO` o `VERIFICADO_ESTÁTICAMENTE` puede presentarse como defecto confirmado.

No presentar como confirmado un hallazgo:

- `INFERIDO`;
- `NO_VERIFICABLE`;
- detectado únicamente por una herramienta.

---

# Severidad

Utilizar una única taxonomía:

## CRITICAL

Usar cuando el defecto pueda provocar, mediante una ruta causal demostrable:

- pérdida o corrupción significativa de datos;
- exposición de credenciales;
- ejecución arbitraria;
- vulnerabilidad crítica explotable;
- indisponibilidad completa;
- resultado principal sistemáticamente incorrecto;
- incumplimiento grave de controles operacionales;
- daño material directo y amplio.

ID:

`AUD-CRIT-###`

## HIGH

Usar cuando exista:

- bug funcional relevante;
- fallo frecuente;
- resultado materialmente incorrecto;
- degradación operacional significativa;
- vulnerabilidad de impacto considerable;
- regresión importante;
- riesgo sustancial de datos;
- fallo relevante en una ruta crítica.

ID:

`AUD-HIGH-###`

## MEDIUM

Usar cuando exista:

- defecto funcional acotado;
- riesgo operativo moderado;
- validación incompleta con impacto real;
- fallo de robustez significativo;
- problema de mantenibilidad con consecuencias demostrables;
- inconsistencia relevante sin impacto crítico.

ID:

`AUD-MED-###`

## LOW

Usar para:

- defecto menor;
- mantenibilidad;
- duplicación;
- documentación incorrecta;
- validación secundaria ausente;
- robustez adicional;
- impacto funcional reducido;
- deuda técnica de bajo riesgo.

ID:

`AUD-LOW-###`

No elevar severidad por posibilidades teóricas sin ruta causal demostrable.

---

# Nivel de confianza

La confianza es independiente de la severidad.

## HIGH

Evidencia concluyente.

Corresponde a:

- un hallazgo `REPRODUCIDO`; o
- un hallazgo `VERIFICADO_ESTÁTICAMENTE`.

## MEDIUM

Evidencia fuerte pero no concluyente, por ejemplo:

- evidencia estática sólida que todavía no demuestra por sí sola toda la ruta defectuosa;
- reproducción incompleta;
- una condición externa necesaria aún no observada;
- contexto relevante todavía no verificado.

Un candidato con estas características debe mantenerse como `INFERIDO` mientras falte la evidencia necesaria para confirmarlo.

## LOW

Hipótesis plausible que depende de condiciones o información no disponible.

Los defectos confirmados deben tener confianza `HIGH`, porque `CONFIRMADO` exige estado final `REPRODUCIDO` o `VERIFICADO_ESTÁTICAMENTE`.

## Regla de independencia

La severidad representa:

> el impacto potencial del defecto si existe.

La confianza representa:

> la solidez de la evidencia de que el defecto existe.

Nunca aumentar o reducir automáticamente la severidad en función del nivel de confianza.

Ejemplos válidos:

- `Severity: CRITICAL / Confidence: MEDIUM` para un candidato `INFERIDO` de impacto potencial crítico;
- `Severity: LOW / Confidence: HIGH` para un defecto confirmado de impacto reducido.

---

# Evidencia obligatoria de cada hallazgo

Asignar un identificador estable:

- `AUD-CRIT-001`
- `AUD-HIGH-001`
- `AUD-MED-001`
- `AUD-LOW-001`

Para cada hallazgo indicar:

1. ID
2. título
3. categoría
4. severidad
5. nivel de confianza
6. estado de evidencia
7. componente
8. archivos y líneas
9. descripción
10. evidencia
11. condición de activación
12. pasos o comando de reproducción
13. resultado esperado
14. resultado observado
15. causa raíz
16. impacto
17. alcance
18. solución mínima propuesta
19. alternativas
20. riesgo de regresión
21. pruebas necesarias
22. limitaciones

Si un dato no está disponible, indicarlo expresamente.

No inventar:

- archivos;
- líneas;
- comandos;
- resultados;
- errores;
- comportamientos;
- versiones;
- dependencias;
- outputs;
- condiciones de ejecución.

## Regla de causa raíz

No crear múltiples hallazgos para distintas manifestaciones de una misma causa raíz salvo que:

- requieran correcciones independientes;
- tengan impactos materialmente distintos;
- afecten componentes con ownership diferente;
- deban priorizarse separadamente.

Pruebas ausentes relacionadas con un defecto deben formar parte del mismo hallazgo o del plan de corrección, salvo que constituyan un riesgo independiente.
