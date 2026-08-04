# Quantitative Incident Loop

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
Contener incidentes como leakage, picks posteriores al inicio, liquidación incorrecta, duplicación o modelo equivocado.

## Flujo
1. Declarar alcance e impacto.
2. Detener de forma reversible la operación afectada.
3. Preservar logs, snapshots, hashes y configuración.
4. Identificar última ejecución correcta.
5. Reconciliar picks y resultados afectados.
6. Ejecutar el loop técnico correspondiente como loop de apoyo conforme al protocolo del `ORCHESTRATOR.md`.
7. Añadir regresión y postmortem.
8. Reanudar solo tras verificación y aprobación cuando aplique.
