# Selección de modelos Claude por complejidad de tarea

Política activa del proyecto (`CLAUDE.md`): **Opus 5.5 por defecto** y para arquitectura, auditoría e incidentes; Sonnet 5 para trabajo diario de ingeniería; Haiku para lookups acotados; **Fable 5.1 reservado para máxima capacidad de razonamiento**.

> El punto de partida pasó de Opus 5 a **Opus 5.5** el 2026-09-22 (decisión del operador). Opus 5 sigue servido pero la documentación oficial ya lo clasifica como **legacy**.

---

## Haiku 4.5 — tareas mecánicas y acotadas

**Cuándo:** lookup puntual, clasificación binaria, extracción de campos, resumen de un archivo delimitado, validación de esquemas.

**Por qué funciona bien:** responde rápido y es barato. No necesita razonar; solo recupera o clasifica. En este proyecto, el subagente Explore usa modelos ligeros para búsquedas de código precisas.

**Ejemplos concretos:**
- "¿Qué línea define `is_usable_price`?"
- "¿Existe este archivo?"
- Resumen de un CSV ya localizado

---

## Sonnet 5 — trabajo diario de ingeniería

**Cuándo:** la mayoría del tiempo — implementar funciones, añadir tests, corregir bugs, revisar código con contexto claro, analizar un módulo concreto, generar configuraciones o scripts pequeños.

**Por qué es el default:** equilibra calidad e inteligencia con coste razonable. Soporta adaptive thinking, 1 M de contexto, y sigue instrucciones con precisión. Para el 90 % de lo que ocurre en este repo, Sonnet es suficiente.

**Ejemplos concretos:**
- Fix en `markets/vig.py`
- Añadir test para `prediction_gate`
- Análisis de `pipeline/daily.py`
- Editar configuración en `configs/default.yaml`

---

## Opus 5.5 — punto de partida y decisiones de alto impacto

**Cuándo activarlo explícitamente:**
- **Arquitectura crítica:** rediseñar el flujo de `pipeline/daily.py`, decidir cómo separar el `prediction_gate` de producción
- **Auditorías cuantitativas exhaustivas:** leakage temporal en features, calibración cross-liga, backtest walk-forward end-to-end
- **Incidentes en producción:** un pick con stake real se marcó incorrectamente, el gate dejó pasar algo que no debería
- **Refactors estructurales grandes:** mover de CSV a Parquet en toda la capa de storage, cambiar el modelo de Elo en todos los adaptadores
- **Análisis de riesgo irreversible:** antes de tocar el Task Scheduler, cambiar `bankroll_adjustments.csv`, promover un modelo de calibración a producción

**Por qué es el punto de partida:** es el modelo que la documentación oficial recomienda para la mayoría de las cargas (*"start with Claude Opus 5.5 for most workloads"*), a $4/$20 por MTok — más barato que el Opus 5 al que sustituye ($5/$25). Su `effort` por defecto es `medium`, un escalón por debajo del `high` de Opus 5; este proyecto fija `effortLevel: max` en `settings.json`, así que ese defecto no decide aquí. Contexto 1M, salida máxima 128K, thinking adaptativo siempre activo, corte de conocimiento fiable jun-2026.

**Activar con:** `/model claude-opus-5-5` o `claude --model claude-opus-5-5`

---

## Fable 5.1 — máxima capacidad de razonamiento

**Cuándo:** tareas que exigen el máximo nivel de razonamiento disponible. Es el destino del disparador de escalado de `.claude/automation/MODEL_ROUTING.md`, no el punto de partida: se llega aquí subiendo desde Opus 5, no arrancando.

Es el modelo más capaz de Anthropic. Cuesta 2,5x lo que Opus 5.5 ($10/$50 frente a $4/$20 por MTok), y por eso no es el defecto: la mayoría del volumen no lo necesita. La documentación oficial lo sitúa para *"demanding reasoning and long-horizon agentic work, or when your evals on Claude Opus 5.5 at higher effort still fall short"*. Contexto de 1M, thinking adaptativo siempre activo, corte de conocimiento jun-2026.

> **El ID lleva guiones: `claude-fable-5-1`, no `claude-fable-5.1`.** El punto es la forma de escribir el NOMBRE ("Claude Fable 5.1"), no el identificador de API. Con punto, `claude --model` falla. `claude-fable-5` (sin sufijo) es un modelo distinto y ya **legacy**; verificado contra el catálogo vivo el 2026-09-04.

**Activar con:** `/model fable` o `claude --model claude-fable-5-1`

---

## Cómo cambiar el modelo activo

**Para una sesión puntual:**
```
/model opus
/model sonnet
/model haiku
/model fable
```

**Desde la CLI:**
```
claude --model claude-opus-5-5
claude --model claude-sonnet-5
claude --model claude-haiku-4-5
claude --model claude-fable-5-1
```

**El modelo del proyecto** vive en `.claude/settings.json` → `"model": "claude-opus-5-5"` (decisión del operador, 2026-09-22; antes `claude-opus-5` desde el 2026-08-30). Tiene precedencia sobre la configuración global (`~/.claude/settings.json`). Editarlo **no** cambia el modelo de una sesión ya abierta: rige en la siguiente, o antes con `/model`.

---

## Tabla de decisión rápida

| Señal | Modelo |
|---|---|
| "¿Qué hace X?", "¿dónde está Y?" | Haiku |
| Fix, test, feature, explicación, análisis de módulo | Sonnet |
| "¿Debería rediseñar Z?", auditoría cuantitativa, incidente producción | Opus 5.5 |
| Tarea larga multi-dominio, sesión con mucho contexto | Opus 5.5 |
| Máximo razonamiento: decisión irreversible, parámetros de riesgo, cifras publicables | Fable |
