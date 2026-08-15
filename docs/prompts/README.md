# Motores de pricing pregame — especificaciones fuente

Los documentos que originaron este proyecto. Cada uno especifica un motor
cuantitativo de pricing pregame para un deporte: estima probabilidades justas a
partir de datos del juego y **solo consulta el mercado al final**, como
benchmark.

Se versionan aquí porque son la **fuente** de la que deriva `src/sqp`, no una
nota sobre él. Antes vivían fuera del repositorio (`C:\dev\4` y la raíz), donde
no había historial ni respaldo.

## Inventario

| Archivo | Deportes | Distribución | Versión |
|---|---|---|---|
| `prompt-191-mlb-pricing-v3.md` | MLB | Negative Binomial + cópula | v3 |
| `prompt-basket-pricing-v2.md` | NBA, WNBA, NCAAB, WNCAAB | Normal bivariante | v2 |
| `prompt-football-pricing-v2.md` | NFL, NCAAF | Normal + números clave | v2 |
| `prompt-nhl-pricing-v2.md` | NHL | Poisson bivariante + OT/EN | v2 |
| `prompt-soccer-pricing-v2.md` | 12 competiciones | Poisson + Dixon-Coles | v2 |
| `prompt-tenis-pricing-v2.md` | ATP, WTA | Elo / Markov jerárquico | v2 |

Los seis quedaron sincronizados el 2026-08-15. Cada archivo lleva su propio
registro de cambios en la cabecera.

## El origen

**Prompt 191** (MLB) es el documento fundacional del proyecto. La hipótesis de
la que nació todo, en palabras del operador:

> "Yo pensaba que si podía determinar las probabilidades con bastante exactitud
> podría llegar a ganar dinero apostando en los resultados de los partidos."

Sus 21 fases **son** los módulos de `src/sqp`: features y adaptadores por
deporte → `simulation/` y `models/distributions.py` (con `nbinom`) →
`markets/odds.py` y `markets/edge.py` → gate de CLV → ranking de edges.

La **v1 de prompt 191 no existe como archivo**: se conserva únicamente citada y
analizada en las notas de la bóveda. Este directorio guarda la v2 corregida.

## Sincronización de 2026-08-15

Las dos ramas habían divergido: los cinco motores por deporte eran posteriores a
la v1 de MLB pero anteriores a su v2, así que cada una tenía mecanismos que la
otra no. Se cruzaron en ambos sentidos.

**A los cinco por deporte (v1 → v2), desde MLB v2:**

1. `EV_por_unidad` como variable de decisión — ninguno lo calculaba.
2. Ranking lexicográfico. El `Score = 0.65×EDGE + 0.20×Conf + 0.15×MarketConf`
   era ambiguo en unidades: con el edge como proporción aportaba ~7% del total
   y **el ranking ordenaba de facto por confianza**.
3. `|p − 0.50|` pasa a llamarse "convicción del modelo" y sale del ranking.
4. Lenguaje epistémico: "probabilidades justas estimadas".
5. Disciplina point-in-time y procedencia (reglas 10–12).
6. "Candidato a valor pregame" en vez de "CLV positivo" antes del cierre —
   el CLV no existe hasta que existe el cierre.

**A MLB (v2 → v3), desde los cinco:**

1. Fase 0 — motor de cálculo declarado; prohibido afirmar simulaciones no
   ejecutadas.
2. Regla anti doble conteo explícita (regla 12), con los siete solapamientos
   propios de este modelo.
3. Bandera de outlier: `|Edge_pp| > 6.0` → revisar inputs y bajar
   `CalidadMercado`. Es la defensa contra selección adversa.
4. Fase 22 — sanity checks obligatorios antes de imprimir.
5. Dos modos de trazabilidad (auditoría / resumen).

**A los seis: fase de calibración**, que no tenía ninguno. Brier y log loss
contra el mercado, curva de fiabilidad por banda, sesgo de localía, dispersión
realizada vs. simulada, y CLV tras el cierre.

### Defectos cerrados en esta pasada

- **Tenis**: la tabla Bo3→Bo5 contradecía a las fórmulas del propio prompt
  (83.5% vs 85.4% al 80%). Recalculada desde las fórmulas; la duda de si el
  amortiguamiento era deliberado queda registrada y se resuelve con datos.
- **Baloncesto** (`SOSAdj`) y **NHL** (`STAdj`): dos fórmulas quedaban cortadas
  a media frase con puntos suspensivos literales. Cerradas.
- **rho sin procedencia**: anotada en baloncesto, NHL, fútbol y MLB.

### Lo que deliberadamente NO se cambió

Ninguna constante. En particular, las dos sospechas cuantitativas de MLB
—`HomeAdj = 1.02` y `NB_alpha = 0.15`— **siguen intactas**. Se han añadido los
sanity checks que las detectan y la fase de calibración que las resolvería, pero
corregirlas a ojo sería exactamente el error que este proyecto ya aprendió a no
cometer. Se cambian con la medición delante, o no se cambian.

## Análisis

En la bóveda Obsidian, no aquí:

- `Obsidian/Conocimiento/Prompt 191 - origen del modelo.md` — origen, mapa
  fase→módulo, y análisis de las versiones v1 y v2 de MLB.
- `Obsidian/Conocimiento/Motores de pricing por deporte - analisis.md` — análisis
  de los cinco motores por deporte, defectos encontrados y trabajo sugerido.

## Convención

Nombre: `prompt-<deporte>-pricing-v<N>.md`, donde `<N>` es la **versión
vigente**. Al corregir un motor: renombrar al número siguiente y editar en
sitio, con un bloque de cambios en la cabecera del propio archivo.

**El historial lo lleva git**, no copias paralelas. Mantener seis archivos
casi idénticos para un delta del 5% invita a que alguien edite el equivocado y
a que las versiones deriven en silencio — que es exactamente el problema que
tuvo esta familia hasta el 2026-08-15. Para ver una versión anterior:
`git log --follow docs/prompts/<archivo>`.
