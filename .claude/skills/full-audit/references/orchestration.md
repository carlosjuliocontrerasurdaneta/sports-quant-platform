# Modo orquestado

Esta referencia aplica cuando la auditoría abarca todo el sistema, el usuario solicita una auditoría orquestada o el alcance requiere especialidades independientes.

---

# Modo orquestado

Activar cuando:

- la auditoría abarque todo el sistema;
- el usuario solicite `full system audit`;
- el usuario solicite una auditoría orquestada;
- el alcance requiera especialidades independientes.

Usar `principal-orchestrator` cuando esté disponible.

Delegar únicamente áreas aplicables entre especialistas disponibles, por ejemplo:

- `repository-cartographer`
- `backend-architect`
- `data-engineer`
- `feature-engineer`
- `leakage-detector`
- `ml-engineer`
- `calibration-auditor`
- `backtest-reviewer`
- `odds-market-auditor`
- `risk-manager`
- `qa-engineer`
- `security-reviewer`

No asumir que un especialista existe por estar nombrado.

Si un especialista no está disponible:

1. continuar con los especialistas disponibles;
2. realizar localmente la revisión equivalente cuando sea posible;
3. indicar qué área no pudo delegarse;
4. no reducir silenciosamente la cobertura.

## Ownership y solapamiento

Antes de delegar:

- asignar un `primary reviewer` por área;
- definir validadores independientes cuando corresponda;
- identificar solapamientos intencionales;
- evitar duplicación no coordinada.

Un especialista puede actuar como:

- `PRIMARY REVIEWER`
- `INDEPENDENT VALIDATOR`

No utilizar dos agentes para repetir exactamente el mismo análisis sin propósito de validación cruzada.

## Instrucciones mínimas para cada especialista

Proporcionar:

- alcance exacto;
- archivos o componentes asignados;
- exclusiones;
- prohibición de modificar;
- taxonomía de severidad;
- niveles de confianza;
- estados de evidencia;
- formato obligatorio;
- comandos permitidos;
- límites de ejecución;
- relación con otros especialistas.

## Responsabilidades del orquestador

El orquestador debe:

- verificar la evidencia de cada especialista;
- deduplicar hallazgos;
- consolidar causas raíz;
- resolver inconsistencias;
- unificar severidad;
- unificar confianza;
- descartar falsos positivos;
- conservar trazabilidad;
- identificar áreas sin cobertura;
- diferenciar opinión técnica de defecto demostrado;
- no aceptar automáticamente las conclusiones de especialistas.
