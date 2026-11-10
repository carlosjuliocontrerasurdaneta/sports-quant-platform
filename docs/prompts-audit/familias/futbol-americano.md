# Familia futbol-americano: PROMPT_191_NFL_v1_0 y PROMPT_191_NCAAF_v1_0

Fecha: 2026-11-10. Informes individuales: `docs/prompts-audit/individual/PROMPT_191_NFL_v1_0.md` y `PROMPT_191_NCAAF_v1_0.md`.

## Diff entre prompts

- [COMPROBADO] Medicion: 491 lineas (NFL) frente a 447 (NCAAF). De las lineas con mas de 25 caracteres, 278 son de NFL y 255 de NCAAF y solo 2 coinciden literalmente. `diff` (tras normalizar NFL/NCAAF) da 636 lineas distintas. [INFERENCIA] No comparten plantilla literal: comparten estructura conceptual (21 fases, congelacion en la fase 18/19, P(H>A), cover/push/loss, over/under/push, mismas tres etiquetas VALIDADO/EXPLORATORIO/INCOMPLETO).
- Comun (conceptual): rol de motor pregame; mercado nunca entra; shrinkage `w = n_eff/(n_eff+tau)` (NFL:133-137; NCAAF:114-118); EPA distinto de puntos; QB con escenarios A/B; distribucion conjunta unica; congelar antes de cuotas; `EV = P_win×(D-1) - P_loss` y `PriceEdge_pp = 100×[P_win - (1-P_push)/D]` (NFL:337-339; NCAAF:278-280); CLV solo con cierre real; `MC_SE`.
- Cambia: NFL tiene regla de empate en regular y playoffs sin empate, OT de 10 minutos (NFL:259); NCAAF no tiene empate y OT por rondas sin reloj (NCAAF:217-221). NCAAF anade SOS jerarquico (Fase 3), priors de roster/portal/transferencias (Fases 4 y 8), FBS/FCS, bowls con opt-outs y CFP, y veto a CFBD (NCAAF:67). NFL anade PROE, Next Gen Stats y pretemporada (NFL:111, 59, 95). NFL tiene 24 pruebas, NCAAF 28. NFL incluye resumen ejecutivo y ranking (NFL:419-426).

## Contradicciones

1. [COMPROBADO] NFL exige un modelo propio de OT o no publicar probabilidades finales (NFL:263), mientras la plataforma (y ambos prompts en su fallback) permite aproximar con Normal; en NCAAF la fase 16 pide documentar la aproximacion (NCAAF:224). No hay contradiccion directa, pero el criterio de "aproximacion aceptable" difiere.
2. [COMPROBADO] Ambos prohiben constantes fijas (NFL:44; NCAAF:34) pero fijan reglas de reglamento con valores concretos: NFL el OT de 2026 (NFL:259), NCAAF la secuencia de prorrogas (NCAAF:217-221). Sin `ruleset_id` en NCAAF (solo NFL lo tiene, NFL:97, 436).
3. [COMPROBADO] NCAAF dice "10.000 iteraciones son prototipo" (NCAAF:234); NFL fija 100 000 como objetivo provisional (NFL:77). Criterios distintos de N sin justificacion.
4. [INFERENCIA] NFL define ML de dos vias con posible devolucion en empate (NFL:43, 341); NCAAF solo dice dos vias sin empate (NCAAF:244), correcto.

## Versiones y obsolescencia

- Ambos 1.0. [COMPROBADO] NFL cita "Reglamento oficial NFL 2026" y OT "2026" (NFL:259, 478); NCAAF cita un enlace de Big Ten con fecha 2026-08-28 (NCAAF:445). Estan fechados en torno a 2026; sin hash ni `ruleset_id` fijo, quedan obsoletos al cambiar reglas. [HIPOTESIS] La URL de overtime NFL apunta a un host Azure de autoria ("umbraco-author", NFL:479), probable fuente inestable.
- Plataforma: los dos prompts no coinciden con ningun modulo existente: la familia `football` es Normal+Elo.

## Tabla comparativa de constantes

| Prompt | Valores numericos calibrados | Regulacion | OT | Empate final | N MC | Tolerancia / otros |
|---|---|---|---|---|---|---|
| NFL | ninguno (NFL:72) | 4x15 = 60 min | 10 min (reg. 2026), playoffs sucesivas | reg. posible, playoffs 0 | 100 000 provisional (NFL:77) | puntos 6/1/2/3/2 (NFL:195) |
| NCAAF | ninguno (NCAAF:48) | 4x15 | por rondas sin reloj; 2pt desde 2.a/3.a | 0 | 10 000 prototipo (NCAAF:234) | sin enumeracion de puntos |
| Plataforma `football` (NFL) | `points_per_elo 0.025`, `margin_sigma 13.5`, `avg_total 44.0`, `total_sigma 13.5`, `elo_k 24`, `elo_home_adv 55` (`registry.py:34-35`) | n/a | no modelado | sin masa de empate | n/a | `market_shrink 0.5` (`default.yaml:17`) |
| Plataforma `ncaaf` | `avg_total 55.0`, `total_sigma 15.5`, `margin_sigma 20.0` (`registry.py:97`), `elo_home_adv 150.0` (`ratings.yaml:42`) | n/a | no modelado | 0 | n/a | idem |
