# Sistema de Auditoría, Remediación y Verificación

Este directorio contiene el sistema de control de calidad técnico asistido por agentes utilizado para auditar, consolidar, corregir y verificar periódicamente el proyecto.

El proceso utiliza auditorías independientes de **Claude Code / Opus 5** y **OpenAI Astra**, seguidas de una fase de consolidación, remediación controlada y verificación independiente.

El objetivo no es sustituir las pruebas, CI/CD ni las revisiones normales de desarrollo, sino proporcionar una capa adicional de análisis técnico profundo y periódico.

---

# 1. Estructura

```text
audits/
│
├── README.md
│
├── prompts/
│   ├── auditoria-claude-code-opus-5.md
│   ├── auditoria-openai-astra.md
│   ├── auditoria-consolidacion.md
│   ├── corregir-auditoria.md
│   └── verificar-remediacion.md
│
├── claude/
│   ├── latest.md
│   └── history/
│
├── openai/
│   ├── latest.md
│   └── history/
│
├── consolidated/
│   ├── latest.md
│   ├── status.md
│   └── history/
│
├── remediation/
│   ├── latest.md
│   └── history/
│
└── verification/
    ├── latest.md
    └── history/
```

---

# 2. Flujo general

El proceso completo consta de cinco fases:

```text
┌──────────────────────────────┐
│          PROYECTO            │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   CLAUDE CODE       OPENAI ASTRA
       │                │
       ▼                ▼
claude/latest.md   openai/latest.md
       │                │
       └───────┬────────┘
               ▼
        CONSOLIDACIÓN
               │
               ▼
 consolidated/latest.md
               │
               ▼
          REMEDIACIÓN
               │
               ▼
  remediation/latest.md
               │
               ▼
          VERIFICACIÓN
               │
        ┌──────┴──────┐
        ▼             ▼
verification/     consolidated/
 latest.md         status.md
```

---

# 3. Orden exacto de ejecución

Ejecutar:

```text
1. prompts/auditoria-claude-code-opus-5.md
2. prompts/auditoria-openai-astra.md
3. prompts/auditoria-consolidacion.md
4. prompts/corregir-auditoria.md
5. prompts/verificar-remediacion.md
```

Los pasos 1 y 2 son independientes. Pueden ejecutarse en cualquier orden e incluso en paralelo si los entornos utilizados lo permiten.

Los pasos 3, 4 y 5 son secuenciales.

---

# 4. Fase 1 — Claude Code / Opus 5

Ejecutar:

`prompts/auditoria-claude-code-opus-5.md`

Claude realiza una auditoría independiente del proyecto.

El resultado esperado es:

`claude/latest.md`

Las ejecuciones anteriores pueden archivarse en:

`claude/history/`

Durante esta fase Claude no debe consultar los resultados de OpenAI ni las consolidaciones existentes antes de completar su análisis principal.

Esto ayuda a mantener la independencia entre auditores.

---

# 5. Fase 2 — OpenAI Astra

Ejecutar:

`prompts/auditoria-openai-astra.md`

OpenAI realiza una segunda auditoría independiente.

El resultado esperado es:

`openai/latest.md`

Las ejecuciones anteriores pueden archivarse en:

`openai/history/`

OpenAI tampoco debe utilizar inicialmente la auditoría de Claude para orientar sus conclusiones.

---

# 6. Por qué las auditorías son independientes

La independencia es deliberada.

Si el segundo agente conoce previamente los hallazgos del primero, puede tender a buscar confirmaciones de esos mismos problemas en lugar de realizar una revisión independiente.

Por este motivo:

```text
Claude ─────► análisis independiente
                         │
                         ▼
                    Consolidación

OpenAI ─────► análisis independiente
```

Los resultados se comparan únicamente después de finalizar ambas auditorías.

---

# 7. Fase 3 — Consolidación

Cuando existan:

`claude/latest.md`

y:

`openai/latest.md`

ejecutar:

`prompts/auditoria-consolidacion.md`

Esta fase compara ambas auditorías contra el código actual.

El resultado principal es:

`consolidated/latest.md`

La consolidación debe:

- identificar coincidencias;
- verificar hallazgos importantes;
- eliminar duplicados;
- detectar falsos positivos;
- resolver discrepancias mediante evidencia;
- identificar causas raíz;
- recalcular severidades;
- asignar prioridades;
- producir un backlog técnico definitivo.

---

# 8. El consolidado es el backlog de referencia

Después de la consolidación, el archivo:

`consolidated/latest.md`

se convierte en la referencia principal para la fase de remediación.

No deben corregirse indiscriminadamente todos los elementos encontrados originalmente por Claude y OpenAI.

La corrección debe basarse en los hallazgos que sobrevivieron al proceso de consolidación.

---

# 9. Prioridades

Los hallazgos utilizan:

| Prioridad | Significado |
|---|---|
| P0 | Acción inmediata |
| P1 | Urgente |
| P2 | Planificada |
| P3 | Mantenimiento |
| P4 | Opcional |

El orden general de trabajo es:

```text
P0
 ↓
P1
 ↓
P2
 ↓
P3
 ↓
P4
```

Severidad y prioridad son conceptos diferentes.

Un hallazgo técnicamente grave puede tener una prioridad distinta dependiendo de las condiciones reales del proyecto.

---

# 10. Severidades

Las auditorías utilizan una matriz común para facilitar la comparación entre agentes.

Las severidades son:

```text
Crítica
Alta
Media
Baja
Informativa
```

La puntuación se calcula mediante:

```text
Puntuación =
(I × 30 +
 A × 20 +
 P × 20 +
 E × 15 +
 R × 10 +
 C × 5) / 4
```

Donde:

```text
I = Impacto
A = Alcance
P = Probabilidad
E = Explotabilidad / Activación
R = Recuperación
C = Ausencia o debilidad de controles
```

Cada dimensión utiliza valores de `0` a `4`.

---

# 11. Rangos de severidad

| Puntuación | Severidad |
|---:|---|
| 90,0–100,0 | Crítica |
| 70,0–89,9 | Alta |
| 40,0–69,9 | Media |
| 15,0–39,9 | Baja |
| 0–14,9 | Informativa |

La misma fórmula debe mantenerse en Claude, OpenAI y consolidación para preservar la comparabilidad.

---

# 12. Fase 4 — Remediación

Ejecutar:

`prompts/corregir-auditoria.md`

Esta fase lee:

`consolidated/latest.md`

y comienza la corrección controlada de los hallazgos.

El resultado documental es:

`remediation/latest.md`

y, cuando corresponda, se realizan modificaciones en el código y las pruebas del proyecto.

---

# 13. Estrategia de corrección

No se recomienda utilizar una estrategia de:

> corregir todo de una vez.

La remediación debe realizarse mediante lotes pequeños y coherentes.

Por ejemplo:

```text
P0
 │
 ├── Hallazgo AUD-001
 └── Hallazgo AUD-002
          │
          ▼
       validar
          │
          ▼
P1 relacionados
          │
          ▼
       validar
          │
          ▼
P2
```

Los hallazgos pueden agruparse cuando compartan claramente una causa raíz o una misma solución.

---

# 14. Regla fundamental de remediación

Para cada hallazgo:

```text
Verificar
   ↓
Reproducir cuando sea posible
   ↓
Identificar causa raíz
   ↓
Corregir
   ↓
Añadir/adaptar prueba
   ↓
Ejecutar validaciones
   ↓
Comprobar criterio de aceptación
```

No debe considerarse corregido un hallazgo únicamente porque el proyecto compile.

---

# 15. Pruebas de regresión

Cuando un defecto sea reproducible mediante una prueba automatizada, debe considerarse la incorporación de una prueba de regresión.

El objetivo es transformar:

```text
defecto descubierto por auditoría
```

en:

```text
defecto corregido
        +
prueba automática que evita su reaparición
```

Esto reduce la probabilidad de que futuras auditorías tengan que volver a descubrir el mismo problema.

---

# 16. Fase 5 — Verificación independiente

Después de la remediación ejecutar:

`prompts/verificar-remediacion.md`

Esta fase **no corrige código**.

Su función es comprobar independientemente que las modificaciones realizadas realmente solucionaron los problemas.

Genera:

`verification/latest.md`

y:

`consolidated/status.md`

---

# 17. Estados de verificación

Un hallazgo puede terminar como:

```text
Verificado — Corregido
Verificado — Mitigado
Reabierto
Regresión
No verificable
No aplicable
```

Solo debe cerrarse un hallazgo cuando exista evidencia suficiente.

---

# 18. Estado final

La verificación puede producir:

### APTO

La remediación evaluada supera los criterios definidos y no permanecen P0/P1 materiales relacionados con el ciclo.

### APTO CON PENDIENTES

No existen bloqueos críticos para cerrar el ciclo, pero permanecen tareas planificables.

### NO APTO

Persisten problemas importantes, existen regresiones graves o alguna corrección crítica no es válida.

### VERIFICACIÓN INCOMPLETA

No existe evidencia suficiente debido a limitaciones del entorno.

`APTO` no significa que el software esté matemáticamente libre de defectos. Indica que el ciclo de remediación evaluado superó los criterios establecidos.

---

# 19. Qué hacer si la verificación falla

Si el resultado es:

`NO APTO`

o permanecen hallazgos P0/P1 que deben resolverse, **no es necesario repetir inmediatamente las auditorías completas**.

Volver a:

`prompts/corregir-auditoria.md`

y posteriormente ejecutar:

`prompts/verificar-remediacion.md`

El ciclo será:

```text
Remediar
   ↓
Verificar
   ↓
¿Problemas?
   │
   ├── Sí ──► Remediar ──► Verificar
   │
   └── No ──► Cerrar ciclo
```

Es decir:

```text
4 → 5 → 4 → 5
```

hasta alcanzar un estado aceptable.

---

# 20. Cuándo iniciar una auditoría completa nueva

No es necesario ejecutar las cinco fases después de cada modificación pequeña.

Un nuevo ciclo completo resulta especialmente apropiado después de:

- cambios importantes;
- nuevas funcionalidades relevantes;
- modificaciones arquitectónicas;
- cambios sustanciales de dependencias;
- cambios importantes de infraestructura;
- periodos prolongados de desarrollo;
- preparación para un release importante.

Entonces se vuelve a:

```text
1 → Claude
2 → OpenAI
3 → Consolidar
4 → Remediar
5 → Verificar
```

---

# 21. Desarrollo cotidiano

Las auditorías periódicas no sustituyen los controles normales.

Durante el desarrollo cotidiano deben continuar utilizándose, según el proyecto:

- tests;
- lint;
- type-checking;
- build;
- CI/CD;
- revisión de código;
- pruebas de integración;
- controles de seguridad.

El sistema de `audits/` funciona como una capa adicional de revisión profunda.

---

# 22. Historial

Cada área dispone de:

`history/`

El objetivo es conservar ejecuciones anteriores y poder analizar la evolución técnica del proyecto.

Ejemplo:

```text
history/
├── 2026-09-14-0630.md
├── 2026-10-02-1845.md
└── 2026-11-20-0915.md
```

`latest.md` representa siempre la ejecución más reciente de esa fase.

---

# 23. No eliminar el histórico para ocultar problemas

Los informes históricos deben conservarse cuando sea razonablemente posible.

Un hallazgo corregido no debe eliminarse retroactivamente del informe donde fue descubierto.

Su evolución debe quedar reflejada mediante:

```text
Detectado
   ↓
Consolidado
   ↓
Remediado
   ↓
Verificado
   ↓
Corregido
```

Esto proporciona trazabilidad.

---

# 24. Estado actual del backlog

El archivo:

`consolidated/status.md`

representa el estado actualizado de los hallazgos después de la verificación.

Mientras que:

`consolidated/latest.md`

representa lo detectado en la última consolidación.

No cumplen la misma función.

---

# 25. Archivos principales

| Archivo | Función |
|---|---|
| `prompts/auditoria-claude-code-opus-5.md` | Auditoría independiente Claude |
| `prompts/auditoria-openai-astra.md` | Auditoría independiente OpenAI |
| `prompts/auditoria-consolidacion.md` | Comparación y consolidación |
| `prompts/corregir-auditoria.md` | Remediación controlada |
| `prompts/verificar-remediacion.md` | Verificación independiente |
| `claude/latest.md` | Última auditoría Claude |
| `openai/latest.md` | Última auditoría OpenAI |
| `consolidated/latest.md` | Backlog consolidado |
| `consolidated/status.md` | Estado actualizado del backlog |
| `remediation/latest.md` | Registro de correcciones |
| `verification/latest.md` | Resultado de verificación |

---

# 26. Procedimiento rápido

Para iniciar un ciclo completo:

```text
PASO 1
Ejecutar:
prompts/auditoria-claude-code-opus-5.md

PASO 2
Ejecutar:
prompts/auditoria-openai-astra.md

PASO 3
Ejecutar:
prompts/auditoria-consolidacion.md

PASO 4
Ejecutar:
prompts/corregir-auditoria.md

PASO 5
Ejecutar:
prompts/verificar-remediacion.md
```

Si el paso 5 encuentra problemas pendientes:

```text
PASO 4
   ↓
PASO 5
   ↓
PASO 4
   ↓
PASO 5
```

No reiniciar las auditorías completas salvo que exista una razón para comenzar un nuevo ciclo.

---

# 27. Flujo definitivo

```text
DESARROLLO NORMAL
       │
       ▼
Tests / Lint / Types / Build / CI
       │
       ▼
════════════════════════════════════
       CICLO DE AUDITORÍA
════════════════════════════════════
       │
       ├───────────────┐
       ▼               ▼
    CLAUDE           OPENAI
       │               │
       ▼               ▼
claude/latest     openai/latest
       │               │
       └───────┬───────┘
               ▼
        CONSOLIDACIÓN
               │
               ▼
     consolidated/latest
               │
               ▼
          REMEDIACIÓN
               │
               ▼
       remediation/latest
               │
               ▼
          VERIFICACIÓN
               │
       ┌───────┴────────┐
       ▼                ▼
verification/latest   status.md
       │
       ▼
 ¿Resultado aceptable?
       │
   ┌───┴────┐
   │        │
  NO       SÍ
   │        │
   ▼        ▼
Remediar   CERRAR CICLO
   │        │
Verificar  ▼
   │     DESARROLLO
   └────► NORMAL
             │
             ▼
      Próximo ciclo futuro
```

---

# 28. Regla operativa resumida

**Auditar de forma independiente → consolidar → corregir de forma controlada → verificar independientemente → repetir remediación/verificación si es necesario → cerrar el ciclo → continuar desarrollando → iniciar una nueva auditoría integral cuando corresponda.**

Este procedimiento debe mantenerse reproducible, trazable y basado en evidencia. El objetivo final no es producir informes, sino utilizar los informes para mejorar progresivamente la confiabilidad, seguridad, mantenibilidad y calidad técnica del proyecto.