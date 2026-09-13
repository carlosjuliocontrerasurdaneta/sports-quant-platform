# Sports Quant Platform — paquete optimizado

Paquete local preparado el 10 de septiembre de 2026 sobre el commit
`a401f0644417036f22a13d866c9a56dae2cdc324` del
[repositorio de Carlos Contreras](https://github.com/carlosjuliocontrerasurdaneta/sports-quant-platform/tree/a401f0644417036f22a13d866c9a56dae2cdc324).
No es una publicación nueva en GitHub: contiene cambios locales y un parche
para integrarlos. `BUILD_INFO.json` identifica y verifica los archivos incluidos.

## 1. Instalar en Windows

Requisitos: Python 3.11 o posterior, Git y acceso a Internet para descargar las
dependencias. Las pruebas de integración de herramientas también utilizan Bash;
en Windows forma parte de Git for Windows. Esta entrega se validó en Linux con
Python 3.12.14; la ejecución de los BAT en Windows no se verificó aquí.

1. Extrae el ZIP en una carpeta nueva, por ejemplo `C:\SQP-Optimizado`.
2. Abre esa carpeta y ejecuta `INSTALL_LOCAL.bat` desde una consola.
3. El instalador crea `.venv`, instala con las versiones de `requirements.lock`
   y ejecuta comprobación de dependencias, Ruff, MyPy y pytest.
4. Una ejecución correcta termina con `READY`. Si devuelve `SETUP FAILED`, el
   mensaje identifica la etapa que falló; no se ejecuta ningún trabajo diario.

Comando equivalente desde la carpeta extraída:

```bat
py -3 scripts\setup_local.py --verify
```

El entorno virtual se crea en esta carpeta. No hay rutas ligadas al usuario de
la instalación anterior, ni cambios en Python global. El instalador no copia
credenciales, no crea `.env` y no configura tareas programadas.

## 2. Ejecutar la demostración independiente

En Windows:

```bat
DEMO_INDEPENDENT.bat
```

O directamente:

```bat
.venv\Scripts\python.exe scripts\price_independent.py --model examples\independent_model.json --quotes examples\independent_quotes.json --as-of 2026-09-10T12:00:00Z --max-quote-age-min 90
```

La demostración usa un partido y precios **sintéticos**, identificados dentro de
los JSON. No consulta Internet ni gasta créditos de una API. Su reloj fijo hace
que sea reproducible aunque se ejecute otro día. `--as-of` está prohibido para
entradas etiquetadas `user_supplied`.

La consola muestra una carpeta nueva bajo `outputs/` con:

- `model_freeze.json`: parámetros, fuentes declaradas, corte temporal, versión,
  identificador SHA-256 y probabilidades estimadas, guardados antes de abrir cuotas.
- `report.json`: modelo y comparación posterior, con cinco estados de liquidación,
  cuota justa, EV por unidad, no-vig cuando existe contraparte compatible y edge en pp.

Puede omitirse `--quotes` y `--max-quote-age-min`: se obtiene un modelo sin mercado,
con `market: null`; no se inventan edge, cuotas ni EV. Cada ejecución crea una
carpeta distinta. Un `--output-dir` que ya exista se rechaza para preservar el informe.

## 3. Linux o macOS

Desde la carpeta extraída:

```bash
python3 scripts/setup_local.py --verify
.venv/bin/python scripts/price_independent.py --model examples/independent_model.json --quotes examples/independent_quotes.json --as-of 2026-09-10T12:00:00Z --max-quote-age-min 90
```

Para volver a validar sin reinstalar:

```bash
python3 scripts/setup_local.py --check-only
```

## 4. Datos propios

La especificación completa está en [`docs/INDEPENDENT-PRICING.md`](docs/INDEPENDENT-PRICING.md).
Los JSON de ejemplo muestran el formato. Para datos propios, `data_label` debe ser
`user_supplied`, los timestamps deben incluir zona horaria, y el evento debe seguir
en pregame. Se omite `--as-of` para usar la hora real.

**Este modo recibe parámetros deportivos ya estimados.** No descarga automáticamente
wRC+, xFIP, ORtg, EPA, porteros ni lesiones, y no entrena un modelo a partir del
PROMPT 191. La confianza se identifica como `UNVALIDATED` hasta que exista evidencia
histórica. Las fuentes declaradas por el usuario no equivalen a verificación externa.

Los modelos de conteo nuevos son de tiempo reglamentario: no inventan overtime,
shootout ni reparto de empates para un moneyline de MLB/NHL a partido completo.
La implementación antigua del pipeline conserva sus convenciones existentes.

## 5. Integrar en tu repositorio existente

El ZIP incluye `OPTIMIZATION.diff`, con los cambios de código, pruebas y documentos.
El parche está construido contra el commit base indicado arriba. La instalación
actual puede contener cambios posteriores que requieran integración manual.

Desde tu checkout, `git status --short` permite identificar tus cambios antes de
aplicar el parche. En una rama de trabajo que conserve tu configuración y tus datos:

```bash
git apply --check /ruta/al/OPTIMIZATION.diff
git apply /ruta/al/OPTIMIZATION.diff
python scripts/setup_local.py --verify
```

La primera orden verifica si el parche encaja; no modifica archivos. Si falla,
el parche no puede aplicarse directamente a ese árbol. Esta entrega no sustituye
ni reconstruye tus datos privados, calibradores, históricos o ledger de banca.

El guard existente de `DIARIO_COMPLETO.bat` bloquea código operativo con cambios
sin registrar en Git. Este paquete no desactiva ese guard, pero **el guard no
protege un árbol extraído del ZIP**, y conviene decirlo sin rodeos (auditoría
integral 2026-09-10, AUD-MED-019).

El guard falla ABIERTO por diseño: si `git rev-parse --git-dir` falla, avisa y
continúa —«no se puede comprobar» no es «está sucio»—. Un directorio extraído del
ZIP no contiene `.git`, así que **en él el guard se salta en cada ejecución**,
junto con la comprobación de árbol atrasado. Verificado: `git rev-parse
--git-dir` → `fatal: not a git repository`, rc 128.

Consecuencia práctica: extraer este paquete *sobre* un directorio de producción
no sólo deja el guard inoperante, sino que el ZIP no trae `data/` ni `.env`
(están en `.gitignore`). Antes de desplegar, **haz copia de `data/` y `.env`** y
aplica el parche sobre tu checkout con Git, no sobre el árbol que opera. La
garantía de integración la da tu flujo de Git; este documento no puede darla.

## 6. Pipeline diario existente

Los scripts originales siguen incluidos. La operación utiliza tu clave válida de
The Odds API, configuración y datos propios. El ZIP no contiene esos datos ni
una clave operativa. En una instalación nueva, `.env` puede contener únicamente
la clave necesaria, sin copiar valores de riesgo del ejemplo sobre tus parámetros:

```dotenv
ODDS_API_KEY=TU_CLAVE
```

Para usar el nuevo entorno virtual con los BAT originales, la consola de Windows
permite indicar el intérprete que esos scripts ya admiten:

```bat
set "SQP_PYTHON=%CD%\.venv\Scripts\python.exe"
DIARIO_COMPLETO.bat
```

Este último comando **es operación live**: consulta proveedores y escribe datos.
No forma parte del instalador ni de la demostración y no se ejecutó durante esta
entrega. El orden existente se mantiene: liquidación primero, generación después.
No se garantiza un resultado rentable ni que tu máquina ya tenga datos/calibradores
suficientes para habilitar apuestas; los gates existentes siguen decidiéndolo.

## 7. Qué se verificó

Resultados y limitaciones en [`audit/optimization-20260910/VALIDATION.md`](audit/optimization-20260910/VALIDATION.md).
Cambios e invariantes en [`audit/optimization-20260910/CHANGES.md`](audit/optimization-20260910/CHANGES.md).
El benchmark reproducible está en `scripts/benchmark_distributions.py`.
