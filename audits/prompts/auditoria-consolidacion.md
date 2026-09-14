# Consolidación independiente de auditorías

## OBJETIVO

Consolida las auditorías independientes realizadas por Claude Code y OpenAI Astra.

Archivos esperados:

`audits/claude/latest.md`

`audits/openai/latest.md`

El repositorio actual constituye la **fuente de verdad definitiva**.

Los informes son evidencia secundaria y pueden contener:

- falsos positivos;
- falsos negativos;
- severidades incorrectas;
- hallazgos duplicados;
- evidencia insuficiente;
- errores de interpretación.

No combines automáticamente ambos informes.

Verifica las discrepancias relevantes contra el código actual.

El resultado deberá guardarse como:

`audits/consolidated/latest.md`

Antes de sobrescribir una consolidación anterior, archívala, cuando sea posible, en:

`audits/consolidated/history/YYYY-MM-DD-HHMM.md`

---

# 1. Principio fundamental

La coincidencia entre dos auditores aumenta el interés de un hallazgo, pero **no constituye por sí misma una confirmación**.

La ausencia de un hallazgo en uno de los informes tampoco invalida automáticamente el hallazgo del otro.

Cada conclusión consolidada deberá basarse en evidencia.

---

# 2. Proceso de consolidación

## Fase 1 — Lectura

Lee ambos informes completos.

Extrae:

- hallazgos;
- identificadores;
- ubicaciones;
- evidencia;
- severidad;
- puntuación;
- confianza;
- prioridad;
- recomendaciones.

---

# 3. Normalización

Normaliza nombres y conceptos.

Dos hallazgos deberán considerarse candidatos a equivalencia cuando compartan razonablemente:

- misma causa raíz;
- mismo código;
- mismo flujo;
- mismo impacto;
- misma remediación.

No te bases únicamente en títulos similares.

---

# 4. Clasificación cruzada

Clasifica cada resultado como:

### Confirmado por ambos

Ambos auditores identificaron sustancialmente el mismo problema y la evidencia actual lo respalda.

### Exclusivo Claude

Solo Claude lo reportó y la verificación actual lo respalda.

### Exclusivo OpenAI

Solo OpenAI lo reportó y la verificación actual lo respalda.

### Parcialmente coincidente

Ambos detectaron el mismo fenómeno general, pero difieren en causa, alcance o impacto.

### Falso positivo Claude

El código actual no respalda el hallazgo de Claude.

### Falso positivo OpenAI

El código actual no respalda el hallazgo de OpenAI.

### No verificable

No existe información suficiente para confirmar o descartar razonablemente el problema.

---

# 5. Verificación obligatoria

Para:

- discrepancias de severidad;
- hallazgos críticos;
- hallazgos altos;
- P0;
- P1;
- hallazgos exclusivos relevantes;

revisa directamente el código antes de adoptar una conclusión final.

Cuando sea seguro y útil, ejecuta comprobaciones locales.

No asumas que un hallazgo es correcto porque contiene referencias de línea.

---

# 6. Severidad final

Utiliza la misma matriz:

| Dimensión | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Impacto (I) | Sin impacto | Menor | Moderado | Significativo | Crítico |
| Alcance (A) | Ninguno | Aislado | Varios componentes | Flujo principal | Sistema/datos críticos |
| Probabilidad (P) | Prácticamente imposible | Poco probable | Posible | Probable | Recurrente |
| Activación (E) | No activable | Excepcional | Específica | Fácil | Trivial |
| Recuperación (R) | No necesaria | Inmediata | Sencilla | Compleja | Irreversible |
| Controles (C) | Neutralizan | Fuertes | Parciales | Débiles | Ausentes |

Fórmula:

`Puntuación = (I × 30 + A × 20 + P × 20 + E × 15 + R × 10 + C × 5) / 4`

Rangos:

- 90–100: Crítica
- 70–89,9: Alta
- 40–69,9: Media
- 15–39,9: Baja
- 0–14,9: Informativa

No promedies automáticamente las puntuaciones de Claude y OpenAI.

Calcula una puntuación consolidada nueva a partir de la evidencia actual.

---

# 7. Confianza consolidada

Asigna:

### Alta

La evidencia actual confirma directamente el problema.

### Media

El problema está sólidamente sustentado, pero existe alguna condición no verificable.

### Baja

La conclusión requiere validación adicional.

No eleves automáticamente la confianza solo porque dos auditores coincidan.

---

# 8. Causa raíz

Prioriza causas raíz sobre síntomas.

Si Claude reporta cinco síntomas y OpenAI reporta una causa común que explica los cinco, considera consolidarlos en un único hallazgo cuando la evidencia lo respalde.

---

# 9. Backlog técnico definitivo

El informe consolidado debe producir un backlog accionable.

Para cada hallazgo final incluye:

- ID consolidado;
- origen;
- título;
- categoría;
- área;
- severidad;
- puntuación;
- prioridad;
- confianza;
- ubicación;
- evidencia;
- causa raíz;
- impacto;
- recomendación;
- criterio de aceptación;
- prueba de regresión;
- estado.

Utiliza IDs:

`AUD-001`

`AUD-002`

etc.

---

# 10. Estados

Utiliza:

- Abierto
- En corrección
- Pendiente de validación
- Corregido
- Aceptado como riesgo
- No aplicable

Durante una consolidación nueva, no marques automáticamente como corregido un hallazgo histórico. Debe existir evidencia.

---

# 11. Prioridad de implementación

Ordena las acciones principalmente según:

1. P0;
2. P1;
3. P2;
4. P3;
5. P4.

Dentro de cada prioridad utiliza:

1. mayor severidad;
2. mayor confianza;
3. mayor alcance;
4. dependencias entre correcciones.

Identifica cuando una corrección desbloquea varias otras.

---

# 12. Plan de remediación por fases

Genera:

## Fase 0 — Emergencia

P0 y problemas críticos que requieran intervención inmediata.

## Fase 1 — Riesgo elevado

P1 y hallazgos altos suficientemente confirmados.

## Fase 2 — Estabilización

Hallazgos medios, robustez y pruebas críticas.

## Fase 3 — Calidad estructural

Deuda técnica significativa y mantenibilidad.

## Fase 4 — Mejoras

Problemas bajos y oportunidades.

No propongas cambios masivos cuando una solución localizada y segura sea suficiente.

---

# 13. Reglas para correcciones posteriores

El objetivo de esta consolidación es producir el backlog; no corregir automáticamente todos los hallazgos.

Cada corrección futura debería seguir:

1. seleccionar un hallazgo;
2. reproducir o verificar;
3. identificar causa raíz;
4. realizar el cambio mínimo correcto;
5. añadir o mejorar prueba cuando corresponda;
6. ejecutar tests relevantes;
7. verificar criterio de aceptación;
8. marcar como pendiente de validación o corregido;
9. evitar mezclar cambios no relacionados.

---

# 14. Auditorías históricas

Si existe:

`audits/consolidated/latest.md`

de una ejecución anterior, compáralo después de consolidar el estado actual.

Clasifica hallazgos históricos:

- Nuevo
- Persistente
- Corregido
- Regresión
- No verificable
- Reemplazado por causa raíz consolidada

---

# 15. Métricas

Incluye:

- total de hallazgos;
- críticos;
- altos;
- medios;
- bajos;
- informativos;
- P0;
- P1;
- coincidentes;
- exclusivos Claude;
- exclusivos OpenAI;
- falsos positivos Claude;
- falsos positivos OpenAI;
- no verificables;
- nuevos;
- persistentes;
- corregidos;
- regresiones.

No utilices estas métricas para evaluar cuál modelo es “mejor”. Sirven para evaluar el estado del proyecto y la complementariedad de las auditorías.

---

# 16. Tabla maestra consolidada

Incluye:

| ID | Hallazgo | Origen | Categoría | Área | Puntuación | Severidad | Prioridad | Confianza | Estado | Ubicación |
|---|---|---|---|---|---:|---|---|---|---|---|

---

# 17. Discrepancias

Incluye una sección específica:

## Discrepancias entre auditores

Para cada discrepancia importante indica:

- posición Claude;
- posición OpenAI;
- evidencia revisada;
- conclusión consolidada;
- justificación.

---

# 18. Falsos positivos

Documenta los falsos positivos detectados para evitar que reaparezcan innecesariamente en futuras revisiones.

No conviertas esta información en una instrucción para ignorar permanentemente ese patrón. El código puede cambiar.

---

# 19. Entregable

Guarda:

`audits/consolidated/latest.md`

Estructura:

1. Resumen ejecutivo
2. Fuentes analizadas
3. Metodología de consolidación
4. Limitaciones
5. Estado técnico general
6. Métricas
7. Tabla maestra
8. P0
9. P1
10. P2
11. P3/P4
12. Coincidencias
13. Hallazgos exclusivos
14. Discrepancias
15. Falsos positivos
16. No verificables
17. Causas raíz principales
18. Plan de remediación por fases
19. Pruebas de regresión recomendadas
20. Comparación histórica
21. Conclusiones

El resultado deberá constituir el **backlog técnico de auditoría de referencia** para el proyecto.

Al finalizar, informa únicamente:

- ruta del informe consolidado;
- P0;
- P1;
- críticos;
- altos;
- cantidad de discrepancias;
- cantidad de falsos positivos descartados.