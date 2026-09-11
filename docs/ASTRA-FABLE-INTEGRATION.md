# Integración Fable 5.1 ↔ GPT-6 Astra

## Objetivo

Sports Quant Platform mantiene dos funciones separadas:

- Claude/Fable 5.1: razonamiento y ejecución de trabajo de máxima criticidad
  según `.claude/automation/MODEL_ROUTING.md`.
- GPT-6 Astra: revisión independiente mediante Codex.

El motor cuantitativo de `src/sqp/` no llama a ninguno de estos modelos. Esta
integración pertenece a la capa de ingeniería y auditoría, no al pipeline de
predicción.

## Cableado

Hay dos caminos de Codex y ambos quedan fijados explícitamente:

1. `codex review`
   - `.codex/config.toml` establece `review_model = "gpt-6-astra"`.
   - El centinela `.claude/hooks/crossreview-on-stop.sh` sigue ejecutando
     `codex review`, por lo que utiliza el modelo de revisión configurado.

2. Cross Review Protocol V2
   - `scripts/ai/codex_review.py` ejecuta
     `codex exec --model gpt-6-astra -`.
   - El modelo no depende del default local del usuario.

No existe fallback silencioso a otro modelo. Si Astra no está disponible para
la cuenta, la revisión debe fallar y quedar registrada como no ejecutada, en vez
de producir una aprobación atribuida a Astra.

## Flujo

```text
Trabajo normal
  └─ Claude según routing

Trabajo de máxima criticidad
  └─ Fable 5.1
       ├─ medición / implementación / tests
       └─ GPT-6 Astra (revisión independiente)
            ├─ PASS con verificación
            └─ findings → corregir o refutar con evidencia
```

La política existente sigue gobernando cuándo escalar a Fable 5.1. Este cambio
no altera umbrales, riesgo, modelos estadísticos, calibración, picks ni
settlement.

## Requisitos

- Codex CLI 0.153.0 o posterior para GPT-6 Astra.
- Acceso a GPT-6 Astra habilitado en la cuenta que autentica Codex.
- El repositorio debe ser confiable para que Codex cargue la configuración
  `.codex/config.toml`.

## Validación

Después de aplicar:

```bash
codex --version
python -m pytest -q tests/test_astra_codex_integration.py tests/test_codex_review.py
python -m ruff check scripts/ai/codex_review.py tests/test_astra_codex_integration.py
python -m mypy src
```

La suite específica comprueba:

- `review_model = "gpt-6-astra"`;
- el launcher V2 pasa `--model gpt-6-astra`;
- el hook conserva `codex review`;
- no se codifica un fallback silencioso a modelos anteriores.

## Fuente externa verificada al implementar

OpenAI, documentación vigente consultada el 2026-09-10:

- GPT-6 Astra usa el slug `gpt-6-astra`.
- Astra requiere Codex CLI 0.153.0 o posterior.
- Codex dispone de `review_model` para seleccionar el modelo de las sesiones
  de revisión.
