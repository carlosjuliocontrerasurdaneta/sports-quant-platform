# Cambios — optimización local 2026-09-10

Base: `a401f0644417036f22a13d866c9a56dae2cdc324`. Autorización: solicitud explícita
del usuario de optimizar el repositorio y entregar un paquete implementable.
Alcance: optimización técnica comprobable y modo independiente opcional; no
despliegue, no publicación GitHub y no recalibración especulativa.

| ID | Evidencia y severidad | Cambio |
|---|---|---|
| SQP-MEDIUM-001 | REPRODUCED, confianza alta. `normal_margin_probs(NaN,12,-3.5)` y sigma=0 devolvían NaN; `score_pmf(-1)` también. `dc_rho=NaN` suprimía celdas y daba cifras finitas engañosas. | Guardas finitas, tasa no negativa, sigma positivo, tamaño entero de rejilla y masa positiva. Pruebas con parámetros inválidos. |
| SQP-MEDIUM-002 | REPRODUCED, confianza alta. Cuatro pruebas de fechas fallaban con TZ=Asia/Jakarta porque comparaban la fecha local de servicio con una fecha UTC fija. | Expectativas calculadas desde la hora del partido en la zona local. Conservan la detección de usar fecha de generación y los filtros por liga/mercado. No se cambia el código de fechas de producción. |
| SQP-PERF-001 | MEASURED. Cada llamada a score_pmf hacía una llamada SciPy por marcador. | Una llamada vectorizada y retorno list compatible. La acumulación conjunta original permanece. Pruebas de igualdad exacta Poisson/NB, rho, Dixon-Coles y líneas enteras/medias; benchmark emparejado. |
| SQP-FEATURE-001 | Brecha funcional, no incidente atribuido a producción. | Modo offline con modelo inmutable, freeze persistido antes de abrir cuotas, hashes, trazabilidad, settlement de cinco estados, EV con devolución y cuartos exactos, no-vig emparejado y salida sin stake. |
| SQP-OPS-001 | STATICALLY_VERIFIED: los BAT originales tienen una ruta Python específica de una máquina. | Instalador nuevo portable, `.venv` y constraints del lock; demostración sin API. Se utiliza el override existente SQP_PYTHON para operar scripts originales, sin cambiar esos scripts. |

Los casos válidos del modelo vigente conservan sus resultados en las pruebas de
equivalencia; la nueva validación convierte entradas inválidas en errores explícitos.
No se cambiaron configuración, K de Elo, shrinkage al mercado, calibradores,
parámetros deportivos, Kelly, gates, datos históricos ni contratos CSV del diario.
El módulo de settlement nuevo es independiente del ledger original.

Las tolerancias nuevas son controles numéricos o de recursos del modo offline,
declarados en su contrato. No son umbrales predictivos ajustados sobre resultados.
Los 90 minutos de la demo son un argumento explícito que coincide con la política
de revalidation del commit base, no un cambio a esa política.

Se corrige README para describir binomial negativa MLB y 11 ligas de fútbol,
tal como figuran en registry/configs. Se incorporan instrucciones, ejemplos
sintéticos, pruebas y benchmark. Los informes de auditorías anteriores se conservan.
No se ejecutó un hook de autoformato ni se aplicaron cambios cosméticos masivos.

Quedan fuera del alcance acreditado: rentabilidad, mejora de calibración, funcionamiento
del equipo Windows del usuario, disponibilidad de APIs privadas y copia de su estado
productivo. No existe evidencia nueva para cerrar esos puntos.
