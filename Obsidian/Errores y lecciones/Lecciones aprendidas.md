---
tags: [lecciones, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Lecciones aprendidas

Principios destilados de la experiencia real del proyecto, en orden de importancia.

1. **Batir al baseline trivial no es batir al mercado.** El modelo puede estar bien calibrado per-game (ECE 0.019) y aun así perder dinero: lo que importa es el ROI realizado sobre los picks SELECCIONADOS, y ahí opera la selección adversa. El CLV es el detector.

2. **La selección adversa es más peligrosa que la sobreconfianza.** Con n=71 apuestas reales, hasta la probabilidad justa del mercado perdía en nuestros picks. Un sistema puede elegir sistemáticamente los precios equivocados aunque estime bien.

3. **La disciplina OOS funciona en ambos sentidos.** De 3 señales construidas, 2 se rechazaron (abridor MLB ×2 versiones, rest/B2B) y 1 se activó (park factor). Ventana completa fuerte + held-out débil = ruido. No activar nada que no generalice.

4. **Muestras chicas mienten con apariencia de calibración.** WNBA (n≈170) y tenis (3-9/torneo) no pueden validar nada; parámetros en frontera de grilla con curva plana = ajustar ruido. Solo MLB ha tenido muestra OOS confiable.

5. **Los fallos silenciosos son los caros.** Nombres sin normalizar entre vendors, defaults que fabrican datos, appends que desalinean esquemas: ninguno lanza excepción y todos corrompen la cadena aguas abajo. Guardas: normalización en fronteras, campos obligatorios, escritura con reconciliación, tests e2e.

6. **Todo lo que se auto-reentrenar necesita un gate OOS auto-sanador.** El retrain diario re-persistió un calibrador degenerado; el gate monótono no bastó, hizo falta gate de Brier OOS que además borra entradas que dejan de ayudar.

7. **Entrenar y servir deben ver la misma distribución.** (train/serve mismatch de calibración.)

8. **Config sobre código, reversibilidad siempre.** Parámetros por liga en YAML, flags default-off, default-deny en gates: el rollback de casi todo es borrar una línea o un archivo.

9. **Costo antes que convicción.** Verificar endpoints con requests reales antes de asumir (el histórico "401" resultó disponible); autorizar gasto por tramos; lo gratis (forward capture, ESPN, football-data) primero.

10. **Comunicación operativa**: para el usuario, "loops" = solo lo llamado literalmente "Loop", NO los BAT de orquestación (incidente 2026-07-08: borrado excesivo, hubo que restaurar 6 BATs). Ante ambigüedad de alcance destructivo, confirmar el sustantivo exacto.

Relacionado: [[Errores y lecciones/Errores detectados y soluciones]], [[Decisiones/Registro de decisiones]].
