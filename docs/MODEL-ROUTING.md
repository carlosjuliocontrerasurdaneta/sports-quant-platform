# Selección de modelos Claude por complejidad de tarea

Política activa del proyecto (`CLAUDE.md`): Opus 5 por defecto, Opus para arquitectura/auditoría/incidentes, Sonnet 5 para trabajo diario de ingeniería, Haiku para lookups acotados y Fable 5 para máxima capacidad de razonamiento.

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

## Opus 5 — decisiones de alto impacto

**Cuándo activarlo explícitamente:**
- **Arquitectura crítica:** rediseñar el flujo de `pipeline/daily.py`, decidir cómo separar el `prediction_gate` de producción
- **Auditorías cuantitativas exhaustivas:** leakage temporal en features, calibración cross-liga, backtest walk-forward end-to-end
- **Incidentes en producción:** un pick con stake real se marcó incorrectamente, el gate dejó pasar algo que no debería
- **Refactors estructurales grandes:** mover de CSV a Parquet en toda la capa de storage, cambiar el modelo de Elo en todos los adaptadores
- **Análisis de riesgo irreversible:** antes de tocar el Task Scheduler, cambiar `bankroll_adjustments.csv`, promover un modelo de calibración a producción

**Por qué reservarlo:** más lento, más caro, y la calidad marginal solo justifica el coste cuando el problema genuinamente requiere razonamiento profundo y multi-paso.

---

## Fable 5 — trabajo complejo de larga duración

**Cuándo:** tareas que combinan múltiples dominios, sesiones largas con mucho contexto acumulado, o cuando se necesita máximo razonamiento sobre decisiones complejas de arquitectura o cuantitativas.

**Activar con:** `/model fable` o `claude --model claude-fable-5`

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
claude --model claude-opus-5
claude --model claude-sonnet-5
claude --model claude-haiku-4-5
claude --model claude-fable-5
```

**El modelo del proyecto** vive en `.claude/settings.json` → `"model": "sonnet"`. Tiene precedencia sobre la configuración global (`~/.claude/settings.json`).

---

## Tabla de decisión rápida

| Señal | Modelo |
|---|---|
| "¿Qué hace X?", "¿dónde está Y?" | Haiku |
| Fix, test, feature, explicación, análisis de módulo | Sonnet |
| "¿Debería rediseñar Z?", auditoría cuantitativa, incidente producción | Opus |
| Tarea larga multi-dominio, sesión con mucho contexto | Fable |
