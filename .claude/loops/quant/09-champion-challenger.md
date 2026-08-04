# Champion–Challenger Evaluation Loop

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
1. Congelar hipótesis, target, cohortes y métricas.
2. Ejecutar `VALIDATE_OOS.bat` o `scripts/validate_oos.py`.
3. Ejecutar `scripts/compare_models.py` cuando aplique.
4. Comparar Brier, Log Loss, ECE, discriminación, cobertura, ROI/yield y CLV.
5. Revisar estabilidad temporal, leakage y segmentos.
6. Emitir `REJECT`, `CONTINUE_SHADOW` o `CANDIDATE_FOR_APPROVAL`.
7. Nunca promover automáticamente.
