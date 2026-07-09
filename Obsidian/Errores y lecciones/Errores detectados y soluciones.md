---
tags: [errores, bugs, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Errores detectados y soluciones

Fuente canónica: `.claude/memory/known-issues.md` (KI-001…KI-018, con estado). Aquí, los errores más instructivos y su solución. Todos los KI están RESUELTOS o mitigados al 2026-07-08, salvo KI-002 (nombres soccer, verificable ~post 19-jul), KI-005 (vendor Frauen-Bundesliga) y KI-006 parcial (moneyline MLB/NHL sin señal específica).

## Integridad de datos

- **Empates 0-0 fabricados (MLB)**: statsapi marca pospuestos como Final SIN score; el default `.get("score", 0)` fabricó 24 empates que contaminaron Elo y backtest. Fix: score obligatorio + filtro de detailedState. *Lección: nunca rellenar datos ausentes.*
- **Doubleheaders colapsados**: la clave (date, home, away) perdía 21 juegos MLB reales. Fix: game_id del vendor en la clave de dedup (esquema v2).
- **Desalineación de esquema en settled_*.csv (KI-011)**: append a ciegas con esquema nuevo bajo header viejo desalineaba cada valor al releer, corrompiendo ROI y calibración en silencio. Fix: unión de columnas + reescritura alineada + escritura atómica.

## Fallos silenciosos

- **Pitchers no adjuntados (KI-009)**: match por nombres crudos entre vendors con grafías distintas → "starter unknown" → sin candidatos MLB, todo en silencio. Fix: normalizar ambos lados. *Lección: toda frontera entre vendors necesita normalización.*
- **Liga descartada en silencio**: ante fallo del chequeo `/sports`, una parte asumía activa y otra descartaba → un blip dejó a MLB fuera del run. Fix: asumir activa ante error en ambas.
- **Picks viejos como del día**: fallo transitorio de una liga dejaba su CSV anterior visible en el reporte. Fix: archivar y limpiar en el except.

## Metodología cuantitativa

- **ECE inflado en ligas 3-way**: evaluar P(local) incondicional contra outcomes sin empates es inválido; fix: P(local | no empate) + calibración del empate aparte (Liga MX 0.162→0.057 con los mismos datos).
- **Calibrador isotónico degenerado re-persistido** (regresión 2026-06-30): step function sobreajustada que el gate monótono no detectaba; favoritos a 0.92–0.99 → edges fantasma. Fix: gate de Brier OOS. Ver [[Conocimiento/Calibración]].
- **Mismatch train/serve**: entrenar anclado a cierre y servir anclado a apertura hacía la miscalibración inaprendible. Fix: entrenar sobre la distribución de servicio.

## UI / cobertura (cerrados 2026-07-08)

- **KI-018**: columna Línea renderizaba "nan" para h2h → `_fmt_cell` devuelve "—" (`11bd999`).
- **KI-017**: liquidación de tenis sin test e2e → `tests/settlement/test_settle_tennis_e2e.py`, 4 tests (`7471ce4`).

Relacionado: [[Errores y lecciones/Lecciones aprendidas]].
