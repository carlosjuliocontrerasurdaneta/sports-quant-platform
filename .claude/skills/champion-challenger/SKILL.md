---
name: champion-challenger
description: Usar para comparar un modelo candidato contra el campeón activo —
  "evaluar nuevo modelo", "champion vs challenger", "¿es mejor el candidato?",
  comparación OOS, validate_oos, compare_models, o decidir REJECT / CONTINUE_SHADOW
  / CANDIDATE_FOR_APPROVAL. Nunca promueve automáticamente.
---

# Champion–Challenger Evaluation

## Reglas comunes

- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` según las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.

## Objetivo
Comparar candidato y campeón activo bajo el mismo protocolo temporal.

## Criterio previo obligatorio
Pre-registrar métrica primaria, mejora mínima, muestra mínima, método de incertidumbre y tolerancias de guardrail antes de ejecutar la comparación. Sin esa regla no puede emitirse `CANDIDATE_FOR_APPROVAL`; el resultado es `BLOCKED`.

## Flujo
1. Congelar hipótesis, target, cohortes y métricas. Identificar tipo de candidato,
   rutas, claves, versiones y hashes de candidato y campeón, incluyendo sus
   parámetros y períodos de entrenamiento. Un campeón raw/no-op se registra
   explícitamente como transformación identidad.
2. Seleccionar un evaluador que consuma exactamente esos dos objetos sobre los
   mismos eventos y conjunto de información disponible (para calibradores,
   las mismas probabilidades base), con un período de evaluación
   posterior al entrenamiento de ambos y ajeno a la selección del candidato.
   Verificar identidad/hash antes y después; no sustituir el campeón congelado
   por un registro live que haya cambiado durante la evaluación.
3. Usar comandos únicamente dentro de su alcance real:
   - `scripts/validate_oos.py` (o `VALIDATE_OOS.bat`) compara parámetros de
     ratings congelados en train, full-history y defaults. No evalúa un
     calibrador de staging ni un artefacto candidato arbitrario.
   - `scripts/compare_models.py` compara simulación, un ML entrenado por el
     propio script y mezclas; no carga el calibrador candidato del loop 10.
   - Para calibradores, evaluar las predicciones de ambos artefactos congelados.
     `cross_evaluate_on_settled` en `src/sqp/calibration/pergame.py` ofrece una
     comparación preliminar del candidato `*_h2h_pergame` con el live; no prueba
     por sí sola independencia OOS, identidad del campeón congelado ni todas
     las métricas exigidas. No volver a entrenar para obtener el comparativo.
   Si no existe una evaluación que satisfaga el contrato, registrar `BLOCKED`
   y el evaluador o evidencia faltante. No emitir `CANDIDATE_FOR_APPROVAL` usando
   métricas de objetos distintos.
4. Comparar Brier, Log Loss, ECE, discriminación y cobertura con sus conteos;
   ROI/yield solo cuando el protocolo congelado defina stakes; CLV cuando haya
   precios de entrada y cierre emparejados, aunque el stake sea cero.
   Enlazar cada resultado con los hashes
   de ambos objetos y la cohorte evaluada.
5. Revisar estabilidad temporal, leakage y segmentos.
6. Con evidencia suficiente, emitir `REJECT`, `CONTINUE_SHADOW` o
   `CANDIDATE_FOR_APPROVAL` según el criterio pre-registrado; si falta evidencia
   obligatoria, cerrar `BLOCKED` sin sustituirla por un veredicto del candidato.
7. Nunca promover automáticamente.
