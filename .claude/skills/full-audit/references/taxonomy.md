# Taxonomía — estados, severidad, confianza y registro

## Estados de evidencia

Cada candidato tiene exactamente uno:

- `REPRODUCIDO`: activado de forma controlada y observado el resultado incorrecto.
- `VERIFICADO_ESTATICAMENTE`: demostrado directamente por código, configuración, contrato o datos inspeccionables.
- `DETECTADO_POR_HERRAMIENTA`: reportado por una herramienta; aplicabilidad e impacto sin confirmar.
- `INFERIDO`: evidencia razonable, pero falta una condición necesaria.
- `EVIDENCIA_NO_VERIFICABLE`: el entorno carece de una condición necesaria.
- `DESCARTADO`: revisión adicional refutó la sospecha.

Sólo `REPRODUCIDO` y `VERIFICADO_ESTATICAMENTE` son hallazgos confirmados.

Un `INFERIDO` puede promoverse a confirmado **únicamente** si la Fase 2 aporta un
segundo método independiente que elimine la condición faltante; en ese caso pasa
a `VERIFICADO_ESTATICAMENTE` o `REPRODUCIDO` según el método, y se registra cuál
fue. `DETECTADO_POR_HERRAMIENTA` nunca se promueve por sí solo: exige revisión
manual que establezca la ruta causal.

## Severidad

Cinco niveles. El ID debe coincidir y ser único dentro de la auditoría.

| Nivel | ID | Definición |
|---|---|---|
| `CRÍTICO` | `C-n` | Pérdida o corrupción significativa de datos, exposición crítica de credenciales, ejecución arbitraria, vulnerabilidad crítica explotable, indisponibilidad completa, o resultado principal sistemáticamente incorrecto. |
| `ALTO` | `A-n` | Bug material, fallo frecuente, degradación importante, vulnerabilidad considerable, regresión importante o riesgo sustancial de datos. |
| `MEDIO` | `M-n` | Defecto real de impacto limitado o condicionado, degradación parcial, validación relevante ausente, o mantenibilidad con riesgo material. |
| `BAJO` | `B-n` | Deuda técnica acotada, duplicación, documentación incorrecta, inconsistencia o mejora defensiva de bajo impacto. |
| `INFORMATIVO` | `I-n` | Observación sin defecto: decisión deliberada del proyecto, limitación aceptada, o dato de contexto necesario para interpretar el informe. |

`INFORMATIVO` no es un defecto y **nunca** entra en el plan de corrección como
acción obligatoria. Existe para no inflar `BAJO` con observaciones que no lo son.

No elevar severidad por posibilidad teórica sin ruta causal demostrable.

Este esquema es el que usan `audit/latest/FINDINGS.md` y `MANIFEST.json`. No
introducir prefijos alternativos: rompe la trazabilidad entre auditorías.

**Equivalencia con IDs históricos.** La auditoría del 2026-08-29 no persistió
informe y usó el esquema `AUD-<NIVEL>-NNN`, que sobrevive en mensajes de commit
y en `.claude/memory/known-issues.md`. Al encontrarlo, resolverlo así y no
renumerarlo retroactivamente:

| Histórico | Actual |
|---|---|
| `AUD-CRIT-NNN` | `C-n` |
| `AUD-HIGH-NNN` | `A-n` |
| `AUD-MED-NNN` | `M-n` |
| `AUD-LOW-NNN` | `B-n` |

Un ID citado en un commit debe poder resolverse contra un informe. Si no existe
informe para ese ID, la auditoría que lo emitió incumplió la persistencia
obligatoria: registrarlo como hallazgo de trazabilidad, no ignorarlo.

## Confianza

Independiente de la severidad:

- `ALTA`: evidencia inequívoca.
- `MEDIA`: evidencia sólida pero incompleta.
- `BAJA`: hipótesis plausible dependiente de información o condiciones ausentes.

Reglas:

- confianza `BAJA` nunca se presenta como defecto confirmado;
- `DETECTADO_POR_HERRAMIENTA` no obtiene `ALTA` sólo por la herramienta;
- `REPRODUCIDO` normalmente es `ALTA` si demuestra causalidad;
- `VERIFICADO_ESTATICAMENTE` es `ALTA` si la ruta causal es inequívoca; en caso contrario `MEDIA`.

## Registro por hallazgo

Registrar, y si un dato no existe indicarlo expresamente:

- ID, título, estado, severidad, confianza y categoría;
- componente, archivos y líneas;
- evidencia y condición de activación;
- reproducción o comprobación;
- esperado frente a observado;
- causa raíz, impacto y alcance;
- solución mínima y alternativas relevantes;
- riesgo de regresión y pruebas necesarias;
- limitaciones.

## Correspondencia entre vocabularios

Este repositorio usa cuatro vocabularios en capas distintas. No son
intercambiables:

| Capa | Vocabulario | Dónde vive |
|---|---|---|
| Cobertura de un área | `REVISADA` · `PARCIAL` · `NO_APLICA` · `COBERTURA_NO_VERIFICABLE` · `EXCLUIDA` | matriz de cobertura, Fase 0 |
| Evidencia de un hallazgo | `REPRODUCIDO` · `VERIFICADO_ESTATICAMENTE` · `DETECTADO_POR_HERRAMIENTA` · `INFERIDO` · `EVIDENCIA_NO_VERIFICABLE` · `DESCARTADO` | este archivo |
| Comprobación de la Fase 5 | `PASO` · `FALLO` · `FALLO_PREEXISTENTE` · `REGRESIÓN_INTRODUCIDA` · `NO_EJECUTADA` | skill `audit-remediation` |
| Resultado del loop | `PASS` · `DEGRADED` · `BLOCKED` · `DONE` | `.claude/loops/quant/STATES.md` |

`COBERTURA_NO_VERIFICABLE` (no se pudo auditar el área) y
`EVIDENCIA_NO_VERIFICABLE` (no se pudo confirmar un hallazgo concreto) son
distintos a propósito: confundirlos oculta si el hueco es de alcance o de prueba.

Cierre del loop en `current-task.md`, según `STATES.md`:

- auditoría `COMPLETA` sin bloqueos → `PASS`;
- auditoría `PARCIAL` por limitación acotada y nombrada → `DEGRADED`;
- evidencia insuficiente para decidir, o una acción necesaria requiere aprobación humana → `BLOCKED`;
- `DONE` sólo tras `/verification-gate` y con la documentación obligatoria cerrada.

Un hallazgo `CRÍTICO` abierto **no** convierte el resultado en `BLOCKED` si la
auditoría cumplió su objetivo: el objetivo es diagnosticar, no arreglar. La
corrección pendiente se registra bajo `Next decision`.
