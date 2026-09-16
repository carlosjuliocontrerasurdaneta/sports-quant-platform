# Experimento prospectivo de features — 2026-09-15

## Resultado de preparación

- 12 candidatos y 12 referencias entrenados en aislamiento.
- Los 12 archivos de parejas tienen el mismo SHA-256 que el primer entrenamiento: no cambió la selección ni el ajuste de modelos.
- Ventana: 2026-09-16T00:00:00+00:00 hasta 2027-09-16T00:00:00+00:00, extremo final excluido.
- Horizonte de captura: 7 días.
- Primera verificación: 101 predicciones de candidatos sobre 96 eventos únicos; cada una incluye referencia y adaptador.
- Todas las capturas verificadas son anteriores al inicio; las probabilidades están dentro de [0,1].
- Siete pruebas de integración/guardas aprobadas; Ruff y mypy de la implementación aislada aprobados.

## Modelos

| Candidato | Partidos de entrenamiento | Último día |
|---|---:|---|
| atp/h2h/schedule | 8141 | 2026-09-13 |
| atp/h2h/opponent_form | 8141 | 2026-09-13 |
| nba/h2h/opponent_form | 34064 | 2026-06-14 |
| nba/total_score/opponent_form | 34065 | 2026-06-14 |
| ncaab/h2h/schedule | 6331 | 2026-04-07 |
| ncaaf/h2h/schedule | 3074 | 2026-09-13 |
| nfl/total_score/opponent_form | 8028 | 2026-09-14 |
| nhl/total_score/opponent_form | 32837 | 2026-06-15 |
| wncaab/h2h/schedule | 6125 | 2026-04-05 |
| wncaab/h2h/opponent_form | 6125 | 2026-04-05 |
| wta/h2h/schedule | 10988 | 2026-09-14 |
| wta/h2h/opponent_form | 10988 | 2026-09-14 |

## Primera captura por liga

| Liga | Eventos | Predicciones de candidatos |
|---|---:|---:|
| ncaaf | 75 | 75 |
| nfl | 16 | 16 |
| wta | 5 | 10 |

## Estado y límites

Todavía no hay evidencia prospectiva de calidad: los resultados futuros no han ocurrido. La evaluación queda reservada al cierre de la ventana, con 24 contrastes, alfa familiar 0,05 y bootstrap por fecha. No se han promovido modelos ni enviado apuestas.

Durante el trabajo desaparecieron de forma concurrente los módulos/scripts nuevos y se revirtieron los cambios del árbol principal. Se preservó ese árbol y se continuó desde la copia aislada. El código vigente está en `outputs/feature-shadow-runtime-20260915` y en el `frozen/` del experimento; no está integrado en los módulos del árbol principal.

La captura depende de que el flujo habitual actualice cuotas/resultados locales y de que siga vivo el proceso. No instala un servicio ni arranca automáticamente después de reiniciar Windows. `heartbeat.json` muestra el estado actual; crear `STOP` en la carpeta del experimento detiene el capturador.

Para evaluar hacen falta resultados finales con los mismos IDs/proveedor. No hay emparejamiento supuesto entre ESPN y Odds API, ni conclusión de ventaja contra el mercado.

## Artefactos

- [Protocolo](../data/models/feature_shadow_20260915_v2/protocol.json)
- [Estado del capturador](../data/models/feature_shadow_20260915_v2/heartbeat.json)
- [Guía de ejecución](../docs/FEATURE-SHADOW.md)
- [Código congelado](../data/models/feature_shadow_20260915_v2/frozen/src/sqp/evaluation/feature_shadow.py)

Código/configuración SHA-256: `627604a0265160980462ed9a205165afa4a288883696579b4579915952b19915`.
