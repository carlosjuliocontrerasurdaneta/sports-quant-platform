# Resultado — clima en totales MLB: RECHAZADO

**Fecha:** 2026-09-26. Ejecución única del pre-registro
`2026-09-26-preregistro-clima-mlb.md`, con sus enmiendas E1–E13.
Script: `scripts/research/measure_weather_mlb.py` (commit `99c9548`). Datos de
entrada: `fetch_weather_mlb.py` (calendario MLB y `gfs_seamless`, pronóstico a
24 h), descargados el 2026-09-26. La paridad con `engine.walk_forward_backtest`
pasó en las tres líneas: probabilidades con tolerancia 1e-12 y resultados
idénticos.

## Veredicto: RECHAZA (0 de 5 criterios)

| Criterio | Exigido | Obtenido | ¿Cumple? |
|---|---|---|---|
| 1. Δ log loss en afectados, test combinado | ≤ −0,002 | **+0,0075** (IC95 por días: [+0,0014; +0,0148]) | No |
| 2. Δ < 0 en afectados de cada partición | A y B < 0 | A +0,0154 · B +0,0002 | No |
| 3. ECE del universo no empeora | ≤ 0,0156 | 0,0166 | No |
| 4. Coeficientes de B negativos | los dos < 0 | viento −0,0006 · lluvia **+0,0013** | No |
| 5. El tratamiento bate al control de intercepto | ll_trat < ll_ctrl | 0,68064 frente a 0,68007 | No |

El intervalo del criterio 1 queda **entero por encima de 0**. Con la forma
funcional de producción, el clima no solo no mejora: **empeora** la predicción
de forma medible en los partidos donde actúa.

## Por qué: lo que se preveía

- **Partición A** (entrenamiento 2024): coeficientes grandes (viento −0,0067
  por km/h, lluvia −0,0053 por mm), con el control de intercepto en −0,031. El
  ajuste absorbió el sesgo de nivel de 2024, no un efecto del clima: es el
  confusor que la revisión de Fable anticipó (E5). Llevado a 2025 empeora el log
  loss en +0,015 en los partidos afectados.
- **Partición B** (entrenamiento 2024–25): coeficientes casi nulos y la lluvia
  con signo positivo. No queda señal estable que transferir.
- **Control:** un simple intercepto constante supera al clima en el test
  combinado. Lo que el tratamiento parecía capturar era sesgo general del modelo.

## Informes secundarios (no deciden)

- **Contra la línea capturada** (2026, 1.282 partidos; 250 afectados): Δ +0,00005
  en todos y +0,00025 en los afectados. Tampoco mejora frente a la línea real del
  mercado.
- **Viento centrado por estadio** (B): Δ −0,0005 en afectados, lejos del margen,
  y el coeficiente de viento cambia de signo (+0,0028). No hay un efecto de viento
  anómalo por estadio que rescatar.

## Cobertura

- Histórico: 9.689 resultados (6.279 con abridor).
- Universo abierto: 5.374 partidos, tras excluir 1.852 por techo, 10 con menos de
  9 entradas y 16 filas de partidos reanudados.
- Test combinado: 3.602 partidos, 661 afectados.

## Consecuencias

- `weather.enabled` sigue en `false` y los coeficientes siguen en 0. No se toca
  producción.
- Reabrir exige una forma funcional **distinta**, pre-registrada sobre datos
  nuevos: dirección del viento respecto al campo, temperatura. Repetir esta con
  otro umbral u otra ventana sería buscar una señal a medida en la misma muestra.
- Límite de alcance: solo MLB. NFL y NCAAF no se han medido, porque faltan las
  coordenadas de sus estadios.
