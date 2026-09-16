# Estado al cerrar la sesión — 2026-09-15

## Guardado en disco

- Análisis de 21 ligas: `audit/feature_blocks_20260915.json` y `.md`.
- Selección: `audit/feature_candidates_20260915.json`.
- Experimento vigente: `data/models/feature_shadow_20260915_v2/`.
  Contiene 12 parejas candidato/referencia, históricos, código/configuración
  congelados, protocolo y capturas. Primera captura: 101 predicciones sobre
  96 eventos. Ventana: 2026-09-16 a 2027-09-16 UTC; horizonte siete días.
- Implementación aislada: `outputs/feature-shadow-runtime-20260915/`.
  Guía: `docs/FEATURE-SHADOW.md`. Resumen: `audit/feature_shadow_20260915.md`.
- Publicación recuperada: `data/predictions/report_latest.html`,
  `report_20260915.html`, `picks_ranked_20260915.md`,
  `picks_margen_positivo.md`, `picks_seleccion.md`, `picks_tipster.md`.
  Al regenerarla había 35 selecciones vigentes. No se consultaron cuotas ni
  se asignaron apuestas. Se verificaron 63 archivos protegidos sin cambios.
  Evidencia: `.codex-tmp/publication-recovery-20260915/verification.json`.

## Proceso que queda activo

Capturador PID 2456, último estado comprobado `RUNNING` a las 23:51 UTC.
Su estado actual está en `data/models/feature_shadow_20260915_v2/heartbeat.json`.
Depende del flujo habitual de cuotas/resultados. No reinicia automáticamente
con Windows. Crear `STOP` dentro de esa carpeta solicita su detención.
Cerrar esta conversación no solicita detenerlo. Apagar el equipo detiene la
captura; los archivos ya guardados permanecen.

## Pendientes y cautelas para retomar

- Durante la sesión se retiraron concurrentemente módulos/scripts nuevos del
  árbol principal y se revirtieron sus modificaciones. No se restauraron.
  El código funcional se conserva aislado; los tests nuevos requieren ese
  runtime. No asumir que las mejoras están integradas en `src/` del proyecto.
- No se hicieron commits ni pushes. Informes, documentación y tests nuevos
  siguen sin seguimiento Git; modelos y runtime están en carpetas ignoradas.
- El pipeline de las 12:00 abortó por cambios sin confirmar en código.
  El intento de las 20:06 produjo 178 candidatos sin stake y se interrumpió
  después del diagnóstico por segmentos, antes de confirmar CLV/publicación.
  La causa exacta de esa interrupción no quedó registrada.
- Se recuperaron solo las vistas. El centinela del fallo anterior permanece:
  no se ha declarado completado el pipeline entero ni se han cambiado gates.
- No hay evidencia prospectiva de mejora todavía. La evaluación exige
  resultados finales con los mismos IDs/proveedor y queda reservada al cierre.
