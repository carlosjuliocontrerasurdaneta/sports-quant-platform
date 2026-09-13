# Validación — 10 de septiembre de 2026

Autor: Codex, ejecución local sobre el código entregado. Base pública:
`a401f0644417036f22a13d866c9a56dae2cdc324`.
Entorno: Linux x86_64, Python 3.12.14, NumPy 2.4.4, SciPy 1.17.1.
Dependencias instaladas desde `pyproject.toml` usando `requirements.lock` como constraints.

## Línea base y resultado

| Comprobación | Resultado | Exit |
|---|---|---|
| Primera invocación pytest | Error de entorno: faltaba el directorio padre `.codex-tmp`; se creó y se repitió. No se atribuye al repositorio. | 1 |
| Suite base con directorio correcto | 1774 aprobadas, 4 fallos de fechas por TZ=Asia/Jakarta, 2 omitidas | 1 |
| Ruff base | Sin errores | 0 |
| MyPy base | Sin errores, 98 archivos fuente | 0 |
| Regresión de distribuciones + settlement | 122 aprobadas | 0 |
| Pricing independiente y pruebas de fechas adyacentes | 115 aprobadas | 0 |
| Suite completa final | 1929 aprobadas, 2 omitidas, 42.39 s | 0 |
| Ruff final | Sin errores | 0 |
| MyPy final | Sin errores, 101 archivos fuente | 0 |

Los fallos temporales base se reproducen con eventos a las 18:00Z/20:00Z, que
caen el día siguiente en Asia/Jakarta. Las pruebas corregidas usan la fecha local
derivada del inicio del evento y siguen distinguiéndola de su generación.

Comandos equivalentes (sustituir `python` por el de `.venv`):

```bash
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/final-suite
python -m ruff check src scripts tests
python -m mypy src
python scripts/benchmark_distributions.py --number 300 --repeats 5
```

Crear `.codex-tmp` antes de pytest directo; el instalador lo hace automáticamente.

## Rendimiento medido

Benchmark emparejado: se sustituye exclusivamente score_pmf por las llamadas
escalares SciPy anteriores. Se conservan parámetros y agregación. Mediana de cinco
repeticiones de 300 eventos por modelo. Se exige igualdad exacta del diccionario
de probabilidades antes de reportar tiempos.

| Caso | Escalar, ms/evento | Vectorizado, ms/evento | Aceleración |
|---|---:|---:|---:|
| MLB: NB k=3.8, max_score=25 | 1.44328644 | 0.23717480 | 6.0853× |
| NHL: Poisson, rho=-0.06, max_score=15 | 1.29288047 | 0.30623145 | 4.2219× |
| Soccer: Poisson, DC=-0.1, max_score=10 | 0.67488532 | 0.11634880 | 5.8005× |

Estos tiempos miden solamente `poisson_match_probs` en este entorno. No son una
medición de la duración completa del pipeline, red, backtest o Windows. La
aceleración se calcula como mediana escalar / mediana vectorizada.

## Límites de la verificación

No se ejecutaron APIs deportivas/mercado, liquidaciones reales, programación de
tareas ni promociones de modelos. No se reconstruyó el dataset privado del
proyecto ni se midieron Brier, CLV o ROI nuevos. No se probó la matriz completa
de Python 3.11–3.14. Los BAT nuevos tienen pruebas de contrato estático; no hubo
ejecución de cmd.exe en este entorno Linux. Un pytest verde no sustituye esas
validaciones operativas ni demuestra rentabilidad.

La validación de instalación desde el archivo extraído se registra en
`PACKAGE-CHECK.md` de esta misma carpeta.
