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
| `prompt-191-mlb-pricing-v2.md` | MLB | Negative Binomial + cópula | v2 |
| `prompt-basket-pricing-v1.md` | NBA, WNBA, NCAAB, WNCAAB | Normal bivariante | v1 |
| `prompt-football-pricing-v1.md` | NFL, NCAAF | Normal + números clave | v1 |
| `prompt-nhl-pricing-v1.md` | NHL | Poisson bivariante + OT/EN | v1 |
| `prompt-soccer-pricing-v1.md` | 12 competiciones | Poisson + Dixon-Coles | v1 |
| `prompt-tenis-pricing-v1.md` | ATP, WTA | Elo / Markov jerárquico | v1 |

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

## Estado de sincronización

Los cinco motores por deporte son **posteriores a la v1 de MLB y anteriores a la
v2**, así que cada rama tiene mejoras que la otra no:

- **Solo en los cinco**: Fase 0 (motor de cálculo declarado), regla anti doble
  conteo explícita, bandera de outlier, fase de sanity checks, dos modos de
  trazabilidad.
- **Solo en MLB v2**: `EV_por_unidad` como variable de decisión, ranking
  lexicográfico (sin mezclar unidades), "convicción" en vez de edge para
  `|p−0.50|`, lenguaje epistémico ("probabilidades justas estimadas"),
  disciplina point-in-time y procedencia, "candidato a valor" en vez de "CLV
  positivo" antes del cierre.
- **En ninguno de los seis**: una fase de calibración que confronte las
  probabilidades emitidas con lo ocurrido.

## Análisis

En la bóveda Obsidian, no aquí:

- `Obsidian/Conocimiento/Prompt 191 - origen del modelo.md` — origen, mapa
  fase→módulo, y análisis de las versiones v1 y v2 de MLB.
- `Obsidian/Conocimiento/Motores de pricing por deporte - analisis.md` — análisis
  de los cinco motores por deporte, defectos encontrados y trabajo sugerido.

## Convención

Nombre: `prompt-<deporte>-pricing-v<N>.md`. Al corregir un motor, **añadir una
versión nueva**, no sobrescribir: el historial de estos documentos es parte del
registro del proyecto.
