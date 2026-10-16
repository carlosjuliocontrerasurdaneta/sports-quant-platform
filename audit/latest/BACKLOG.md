# Backlog - audit-2026-10-15

Todos OPEN; remediacion no ejecutada. Prioridad independiente de severidad. Sin P0.

Revision 2 (2026-10-16, consolidacion independiente Claude): anade AUD-013 y precisa AUD-002/AUD-003; v1 preservada en
`history/consolidacion-claude-20261016T104941Z/`. Orden recomendado dentro de P2: AUD-002 -> AUD-013 -> resto.
Autorizacion pendiente en todos: el operador debe aprobar cada remediacion. AUD-003 toca la evidencia del
`prediction_gate` y los precios servidos: clase de escalado (MODEL_ROUTING), revision Fable antes del commit, y la
decision sobre las filas NHL h2h ya servidas desde 2026-09-23 es del operador.

## AUD-003 - P1 - Un mercado h2h de dos vias incorpora Draw y cuotas incompatibles

- Origen: CLAUDE-001; severidad HIGH.
- Cambio minimo: Separar contratos por casa antes del consenso, exigir lados exactos y aplicar elegibilidad coherente en conteos, ejecucion y revalidacion.
- Pruebas: Mixto dos/tres vias, solo dos, futbol tres, casa incompleta, conteos y precios ejecutables.
- Aceptacion: Dos desenlaces complementarios suman 1 con cuotas del mismo contrato, o mercado rechazado.
- Dependencias/control: Gates limitan stakes; no reparan probabilidades servidas.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-001 - P2 - El backtest asigna cuotas del dia siguiente al resultado anterior

- Origen: OPENAI-001; severidad MEDIUM.
- Cambio minimo: Resolver identidad/calendario y reservar matches exactos antes de fallback ambiguo.
- Pruebas: Series consecutivas, cuota faltante, orden de filas, UTC y abstencion.
- Aceptacion: Emparejar la identidad correcta: +20 para junio 11, o abstenerse.
- Dependencias/control: Settlement productivo usa otra ruta de identidad.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-002 - P2 - CI exige un tag que checkout no obtiene

- Origen: OPENAI-002 + CLAUDE-002; relacionado AUD-013 (CLAUDE-003); severidad MEDIUM.
- Cambio minimo: Proveer referencias verificables necesarias en CI o aislar fixture unitario; conservar comprobacion de ancla real separada.
- Pruebas: Clone limpio sin tags; adquisicion explicita; tag incorrecto debe fallar; verificar ejecucion pip-audit.
- Aceptacion: Checkout reproducible con objetos requeridos y pruebas discriminantes aprobadas; escaneo de seguridad ejecutado.
- Dependencias/control: Tag existe localmente, dos pruebas locales pasan. Publicar los tags (accion del operador, escritura externa) no basta sin adquirirlos en el checkout (`ci.yml:34,91`).
- Archivos: `.github/workflows/ci.yml`; `tests/research/test_measure_tier_a_gap.py`.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-013 - P2 - pip-audit depende del exito de pytest y no corre desde 2026-09-26

- Origen: CLAUDE-003 (revision 2); severidad MEDIUM. Depende de: ninguno (se puede hacer antes o junto a AUD-002).
- Cambio minimo: Job o paso de pip-audit independiente del resultado de pytest (`if: always()` o job propio) y version de pip-audit fijada.
- Archivos: `.github/workflows/ci.yml:75-83`.
- Pruebas: Run de rama con un test rojo deliberado: pip-audit se ejecuta y su veredicto es visible.
- Aceptacion: pip-audit nunca `skipped` en main.
- Dependencias/control: Sin compensacion local; pip check no sustituye.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-004 - P2 - Capture close comunica exito tras fallar una etapa habilitada

- Origen: CLAUDE-006; severidad MEDIUM.
- Cambio minimo: Acumular fallos por etapa/liga y propagar codigo o contrato de degradacion al BAT.
- Pruebas: Fallo de captura, revalidacion, starters y exito; sentinel no se limpia en fallo.
- Aceptacion: Estado degradado observable y rc no exitoso cuando falla una etapa requerida.
- Dependencias/control: Logs contienen warning; siguientes ejecuciones pueden recuperar.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-005 - P2 - Liquidacion tenis confia en resultados parciales de un proveedor degradado

- Origen: CLAUDE-007; severidad MEDIUM.
- Cambio minimo: Propagar failed_windows y usarlo para confianza/expiracion y estado del backfill.
- Pruebas: Una ventana 503 y otra valida; pick vencido, historico presente/ausente; ninguna anulacion atribuible a ventana fallida.
- Aceptacion: Fallo de cobertura conocido impide anular los picks afectados y se comunica degradacion.
- Dependencias/control: Payload totalmente vacio bloquea voids; fallback historico recupera resultados ya descargados.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-006 - P2 - Los hooks posteriores omiten modificaciones hechas por PowerShell

- Origen: CLAUDE-008; severidad MEDIUM.
- Cambio minimo: Agregar PowerShell a los tres hooks y comprobar extraccion de rutas.
- Pruebas: Contrato de matchers y evento PowerShell con Set-Content sobre ruta vigilada.
- Aceptacion: Las herramientas de escritura admitidas disparan los controles previstos.
- Dependencias/control: Un Edit/Write/Bash posterior puede recoger cambios por Git; fable_gate protege algunos commits.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-007 - P3 - El log de pitchers duplica entradas identicas con ausentes

- Origen: CLAUDE-009 (solo duplicacion); severidad LOW.
- Cambio minimo: Normalizar valores ausentes antes de comparar.
- Pruebas: None/NaN/vacio y cambio real de pitcher.
- Aceptacion: Una primera entrada; llamadas identicas siguientes agregan cero.
- Dependencias/control: No se establecio consumo operativo por pipeline de este log.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-008 - P3 - La captura supera el limite diario de creditos

- Origen: CLAUDE-011; severidad LOW.
- Cambio minimo: Comprobar coste conservador antes de pedir y reconciliar coste real.
- Pruebas: Saldo menor/igual/mayor al coste, varias ligas, reanudacion diaria.
- Aceptacion: No iniciar una peticion cuyo coste previsto exceda el saldo del limite.
- Dependencias/control: Tope previo y min_remaining limitan consumo ulterior.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-009 - P3 - Merge de resultados descarta partidos consecutivos reales

- Origen: CLAUDE-012; severidad LOW.
- Cambio minimo: Priorizar ID/calendario exacto; fallback no debe absorber otro partido de una serie.
- Pruebas: Serie dias consecutivos, dobles jornadas y verdadero desplazamiento UTC.
- Aceptacion: Conservar ambos partidos distintos.
- Dependencias/control: Backfill previo de DIARIO normalmente actualiza el historico.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-010 - P3 - Cross-review pierde su pendiente si falta el ejecutable

- Origen: CLAUDE-016; severidad LOW.
- Cambio minimo: Verificar ejecutable antes de borrar; advertir y conservar marker.
- Pruebas: PATH sin codex con marker, fallos y salida vacia existentes.
- Aceptacion: Avisar revision no ejecutada y conservar pendiente para reintento.
- Dependencias/control: Rama posterior de fallos de codex ya restaura marker.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-011 - P3 - Tres pruebas de no-repositorio heredan Git del workspace

- Origen: CLAUDE-017; severidad LOW.
- Cambio minimo: Aislar busqueda Git en fixture/subproceso mediante GIT_CEILING_DIRECTORIES.
- Pruebas: Tres casos bajo scratch interno y fixture con repo propio; mantener restricciones de escritura.
- Aceptacion: Fixtures reproducen un directorio sin repositorio incluso dentro del scratch autorizado.
- Dependencias/control: Clasificacion ENVIRONMENTAL_FAILURE evita atribucion incorrecta al producto.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

## AUD-012 - P3 - La cache da por persistido un snapshot que pudo fallar

- Origen: CLAUDE-013 (solo contrato de persistencia); severidad LOW.
- Cambio minimo: Confirmar persistencia por identidad o persistir idempotentemente preservando timestamp de adquisicion.
- Pruebas: Fallo controlado del primer append, reintento cacheado, cero snapshot duplicado y fecha original.
- Aceptacion: Reintento recupera snapshot faltante sin duplicar ni cambiar timestamp original.
- Dependencias/control: Un fetch posterior fuera del TTL puede aportar otro snapshot, no el omitido.
- Estado: OPEN; verificacion pendiente tras cambio autorizado.

Observaciones P4/no confirmadas se conservan en FINDINGS, sin convertirlas en obligaciones de correccion. No debilitar aserciones ni gates para producir verde. Al remediar, preservar FINDINGS y registrar CHANGES/VALIDATION/STATUS con historico de la misma ronda.
