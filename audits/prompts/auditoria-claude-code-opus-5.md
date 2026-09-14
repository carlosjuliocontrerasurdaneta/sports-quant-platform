# Auditoría técnica integral — Claude Code / Opus 5

## OBJETIVO

Realiza una auditoría técnica exhaustiva, sistemática, reproducible y basada en evidencia del repositorio actualmente abierto.

Esta ejecución es exclusivamente de **auditoría**. No corrijas, refactorices ni modifiques automáticamente el código fuente del proyecto.

El informe final deberá guardarse como:

`audits/claude/latest.md`

Antes de sobrescribir un informe existente, archívalo, cuando sea posible, en:

`audits/claude/history/YYYY-MM-DD-HHMM.md`

No permitas que informes de otros auditores influyan inicialmente en tus conclusiones. En particular, no leas `audits/openai/` ni `audits/consolidated/` durante la fase principal de análisis.

---

# 1. Principios obligatorios

Prioriza:

1. exactitud;
2. evidencia;
3. reproducibilidad;
4. trazabilidad;
5. causa raíz;
6. utilidad práctica;
7. minimización de falsos positivos.

No maximices artificialmente el número de hallazgos.

No inventes:

- archivos;
- líneas;
- resultados;
- vulnerabilidades;
- ejecuciones;
- métricas;
- configuraciones;
- comportamientos.

No presentes inferencias como hechos confirmados.

---

# 2. Instrucciones del repositorio

Antes de comenzar:

1. Determina la raíz del repositorio.
2. Busca y lee `CLAUDE.md` y demás instrucciones aplicables.
3. Lee `README`, documentación arquitectónica, manifiestos, archivos de configuración y scripts principales.
4. Identifica el stack tecnológico.
5. Identifica los principales puntos de entrada.
6. Construye un inventario inicial.

Contrasta siempre la documentación con la implementación real.

---

# 3. Autonomía

Trabaja de forma autónoma hasta completar razonablemente la auditoría.

Puedes ejecutar, cuando sean seguros:

- exploración del repositorio;
- búsquedas;
- lectura de código;
- inspección Git;
- tests;
- lint;
- type-checking;
- builds locales;
- analizadores estáticos;
- comprobaciones de dependencias;
- reproducciones locales no destructivas.

No ejecutes:

- modificaciones productivas;
- despliegues;
- commits;
- pushes;
- borrados;
- migraciones destructivas;
- ataques contra servicios externos;
- operaciones sobre datos reales que puedan alterarlos.

Si una comprobación no puede realizarse, registra la limitación y continúa.

---

# 4. Uso de subagentes

Puedes utilizar subagentes para áreas independientes cuando aumenten realmente la cobertura.

Áreas candidatas:

- arquitectura;
- seguridad;
- datos;
- lógica de negocio;
- APIs;
- rendimiento y concurrencia;
- pruebas;
- infraestructura.

El agente principal deberá:

- validar hallazgos importantes;
- consolidar resultados;
- eliminar duplicados;
- identificar causas raíz;
- mantener criterios uniformes;
- producir el informe final.

Un hallazgo propuesto por un subagente no se considera confirmado automáticamente.

---

# 5. Inventario y cobertura

Identifica, cuando existan:

- aplicaciones;
- servicios;
- módulos;
- paquetes;
- puntos de entrada;
- modelos;
- esquemas;
- bases de datos;
- migraciones;
- APIs;
- workers;
- colas;
- tareas programadas;
- procesos asíncronos;
- integraciones externas;
- scripts;
- tests;
- dependencias;
- Docker;
- CI/CD;
- infraestructura como código;
- configuración;
- autenticación;
- autorización;
- observabilidad;
- documentación.

Clasifica los elementos como:

- inspeccionados;
- localizados pero no inspeccionados profundamente;
- excluidos.

No declares cobertura del 100 % salvo que puedas demostrarla.

---

# 6. Áreas de auditoría

## Arquitectura y diseño

Evalúa:

- separación de responsabilidades;
- cohesión;
- acoplamiento;
- dependencias;
- ciclos;
- abstracciones;
- modularidad;
- límites arquitectónicos;
- puntos únicos de fallo;
- inconsistencias de diseño.

## Lógica de negocio

Reconstruye los principales flujos.

Busca:

- cálculos incorrectos;
- casos límite;
- estados inválidos;
- errores numéricos;
- errores de precisión;
- errores de unidades;
- fechas;
- zonas horarias;
- supuestos no garantizados;
- divergencias entre componentes.

Presta especial atención a lógica cuantitativa, estadística, deportiva o financiera.

## Seguridad

Evalúa:

- secretos;
- credenciales;
- autenticación;
- autorización;
- control de acceso;
- validación;
- inyección;
- traversal;
- SSRF;
- ejecución de comandos;
- deserialización;
- sesiones;
- criptografía;
- CORS;
- exposición de datos;
- configuraciones inseguras;
- dependencias vulnerables.

## Datos

Evalúa:

- integridad;
- esquemas;
- transacciones;
- migraciones;
- consistencia;
- concurrencia;
- idempotencia;
- índices;
- queries;
- N+1;
- precisión;
- cachés;
- corrupción potencial.

## APIs e integraciones

Evalúa:

- contratos;
- validaciones;
- autenticación;
- autorización;
- códigos de respuesta;
- timeouts;
- reintentos;
- backoff;
- idempotencia;
- rate limiting;
- errores;
- versionado.

## Rendimiento y concurrencia

Busca:

- consultas ineficientes;
- algoritmos problemáticos;
- bloqueos;
- carreras;
- deadlocks;
- recursos no liberados;
- crecimiento de memoria;
- operaciones innecesarias;
- ausencia de límites.

## Robustez

Evalúa:

- manejo de excepciones;
- timeouts;
- reintentos;
- recuperación;
- estados parciales;
- degradación;
- tolerancia a fallos.

## Pruebas

Evalúa:

- unitarias;
- integración;
- E2E;
- tests negativos;
- casos límite;
- assertions;
- determinismo;
- aislamiento;
- tests ignorados;
- flakiness;
- cobertura de flujos críticos.

No utilices únicamente el porcentaje global de cobertura.

## Infraestructura

Evalúa:

- Docker;
- CI/CD;
- permisos;
- secretos;
- health checks;
- configuración;
- imágenes;
- reproducibilidad;
- diferencias entre entornos.

## Observabilidad

Evalúa:

- logging;
- métricas;
- tracing;
- correlación;
- diagnóstico;
- errores silenciosos;
- filtrado de información sensible.

---

# 7. Evidencia

Todo hallazgo debe identificar, cuando sea posible:

- ruta;
- archivo;
- símbolo;
- función;
- clase;
- endpoint;
- líneas;
- condición desencadenante;
- evidencia;
- impacto;
- controles existentes.

Distingue:

- evidencia directa;
- evidencia indirecta;
- inferencia.

Antes de registrar un problema, comprueba si existen:

- middleware;
- validaciones;
- sanitización;
- restricciones;
- wrappers;
- autorización superior;
- configuración;
- tests;
- controles compensatorios.

---

# 8. Falsos positivos

No conviertas automáticamente en defectos:

- TODO;
- FIXME;
- dependencia antigua;
- baja cobertura;
- falta de comentarios;
- complejidad;
- warning;
- ausencia de un patrón;
- código poco elegante.

Debe existir una consecuencia técnica suficientemente demostrable.

---

# 9. Deduplicación

Agrupa problemas derivados de la misma causa raíz.

No generes múltiples hallazgos únicamente porque un mismo problema aparezca en múltiples archivos.

Divide hallazgos únicamente si difieren materialmente en:

- causa;
- impacto;
- riesgo;
- solución.

---

# 10. Clasificación

Utiliza:

- **Defecto confirmado**
- **Riesgo potencial**
- **Deuda técnica**
- **Oportunidad de mejora**

---

# 11. Matriz reproducible

Puntúa de 0 a 4:

| Dimensión | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Impacto (I) | Sin impacto | Menor | Moderado | Significativo | Crítico |
| Alcance (A) | Ninguno | Aislado | Varios componentes | Flujo principal | Sistema/datos críticos |
| Probabilidad (P) | Prácticamente imposible | Poco probable | Posible | Probable | Recurrente/inevitable |
| Activación (E) | No activable | Excepcional | Condiciones específicas | Fácil | Trivial |
| Recuperación (R) | No necesaria | Inmediata | Sencilla | Compleja | Irreversible/extrema |
| Controles (C) | Neutralizan | Fuertes | Parciales | Débiles | Ausentes |

Fórmula:

`Puntuación = (I × 30 + A × 20 + P × 20 + E × 15 + R × 10 + C × 5) / 4`

Redondea a un decimal.

| Puntuación | Severidad |
|---|---|
| 90,0–100,0 | Crítica |
| 70,0–89,9 | Alta |
| 40,0–69,9 | Media |
| 15,0–39,9 | Baja |
| 0–14,9 | Informativa |

No alteres pesos ni umbrales.

Usa el escenario razonablemente demostrable, no el peor escenario hipotético.

---

# 12. Confianza

Asigna:

- **Alta:** evidencia directa suficiente.
- **Media:** evidencia sólida con alguna condición no verificable.
- **Baja:** requiere validación adicional.

La confianza no modifica la puntuación matemática.

---

# 13. Prioridad

Asigna:

- **P0:** inmediata.
- **P1:** urgente.
- **P2:** planificada.
- **P3:** mantenimiento.
- **P4:** opcional.

Severidad y prioridad son independientes.

---

# 14. Validación

Cuando sea seguro, intenta validar mediante:

- tests;
- builds;
- lint;
- type-checking;
- reproducciones locales;
- análisis de dependencias.

Registra:

- comando;
- propósito;
- resultado;
- limitación.

No afirmes haber ejecutado una comprobación que solo hayas inferido.

---

# 15. Formato de cada hallazgo

Incluye:

- ID
- título
- categoría
- área
- severidad
- puntuación
- prioridad
- confianza
- estado de validación
- ubicación
- evidencia
- descripción
- causa raíz
- impacto
- escenario de materialización
- controles existentes
- I + justificación
- A + justificación
- P + justificación
- E + justificación
- R + justificación
- C + justificación
- cálculo explícito
- recomendación
- criterio de aceptación
- prueba de regresión sugerida

---

# 16. Auditoría recurrente

Si existe un informe Claude anterior, puedes utilizarlo al final de la auditoría, nunca como sustituto de la inspección actual.

Clasifica respecto de la ejecución anterior:

- Nuevo
- Persistente
- Corregido
- Regresión
- No verificable

No copies hallazgos antiguos sin revalidarlos.

El código actual es la fuente de verdad.

---

# 17. Control final

Antes de entregar:

1. elimina duplicados;
2. revisa falsos positivos;
3. verifica evidencia;
4. verifica cálculos;
5. comprueba severidades;
6. separa severidad de confianza;
7. verifica afirmaciones de ejecución;
8. comprueba recomendaciones;
9. comprueba criterios de aceptación;
10. declara limitaciones;
11. elimina afirmaciones especulativas presentadas como hechos.

---

# 18. Informe final

Guarda:

`audits/claude/latest.md`

Estructura:

1. Resumen ejecutivo
2. Alcance
3. Metodología
4. Limitaciones
5. Inventario y cobertura
6. Arquitectura
7. Estado técnico general
8. Tabla maestra
9. Hallazgos críticos
10. Hallazgos altos
11. Hallazgos medios
12. Hallazgos bajos
13. Observaciones informativas
14. Seguridad
15. Arquitectura
16. Lógica y exactitud
17. Datos
18. APIs
19. Rendimiento y concurrencia
20. Robustez
21. Pruebas
22. Dependencias
23. Infraestructura
24. Observabilidad
25. Deuda técnica
26. Fortalezas
27. Riesgos principales
28. Plan de remediación
29. Criterios de aceptación
30. Comparación histórica
31. Conclusiones
32. Anexo de comandos

Al finalizar, responde únicamente con:

- ruta del informe;
- cantidad de hallazgos por severidad;
- cantidad de P0/P1;
- si hubo limitaciones materiales.