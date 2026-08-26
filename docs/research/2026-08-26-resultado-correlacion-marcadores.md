# Resultado — correlación entre marcadores (`score_rho`): **RECHAZADO**

**Fecha:** 2026-08-26. Cierra el pre-registro
`2026-08-26-preregistro-correlacion-marcadores.md`, commiteado (`73fede7`) antes
de implementar y antes de medir nada OOS.

## Resultado del gate

Tuner del proyecto con su gate rolling-origin (4 folds), rejilla
`score_rho ∈ {−0,12, −0,09, −0,06, −0,03, 0,0}`, 32.777 partidos evaluados:

| mercado | argmin | vigente | mejora OOS | veredicto del gate |
|---|---:|---:|---:|---|
| `spreads` @ 1,5 | **−0,12** | 0,0 | **+0,0068** | **ACEPTA** (≥ 0,0020) |
| `totals` @ 5,5 | **0,0** | 0,0 | +0,0000 | rechaza |

## Decisión: RECHAZADO

Falla **dos** criterios pre-registrados, cada uno suficiente por sí solo.

**1. No pasa en ambos mercados a la vez.** El pre-registro exige literalmente:
*"ACEPTAR solo si el candidato pasa el gate en AMBOS mercados a la vez. Es el
punto entero de la correlación: si mejora uno y empeora el otro, es
indistinguible de mover `dispersion_k` y no se despliega."* Totals no mejora
nada (0,0000). Se aplica tal cual.

**2. El argmin está en el borde de la rejilla.** El pre-registro dice: *"el ρ que
elige el gate debe caer cerca del medido (≈ −0,06). Un óptimo en el extremo de la
rejilla (−0,12) sin apoyo del diagnóstico sería señal de que el gate está
absorbiendo otro defecto, y se rechaza igualmente."* El argmin es exactamente
−0,12, el extremo, contra un ρ medido de −0,059 por el margen y −0,065 por el
total.

**`configs/leagues/ratings.yaml` intacto. Ninguna liga cambia.**

## Qué significa, sin adornos

El diagnóstico sigue siendo válido y no se retira: la correlación condicional en
NHL es **−0,0873 con p<0,0001 sobre 32.777 partidos**, y los dos ρ implícitos
—por margen y por total— son coherentes entre sí. Eso no era ruido.

Lo que la prueba OOS refuta es la **implementación como ρ constante**. La tesis
era que `ρ<0` ensancha el margen y estrecha el total, moviéndolos en sentidos
opuestos —justo lo que `dispersion_k` no puede hacer—. El gate confirma la mitad
del margen (+0,0068) y **cero** en el total. Si solo ayuda a un lado, no está
haciendo lo que la tesis decía: está ensanchando dispersión del margen, que es
precisamente lo que `dispersion_k` ya sabe hacer.

**Esto estaba anticipado.** El pre-registro dejó escrito este caveat:

> *el ratio del margen en NHL crece con `λ_total` (1,005 → 1,047) mientras el del
> total es plano (0,963 → 0,961). Un `ρ` constante no reproduce ese gradiente.*

El resultado encaja exactamente: el `ρ` constante captura la parte del margen
—que es la que tiene gradiente— y no toca la del total, que es plana. La forma
del defecto no es un `ρ` constante.

## Qué queda en el árbol y por qué

El código **se conserva**, inerte:

- `score_rho` con default `0.0` en `distributions._joint_grid` → sin override,
  toda liga es byte-idéntica. Los tests de distribuciones previos pasan sin
  tocarlos.
- 20 tests en `tests/test_score_correlation.py` que fijan las propiedades
  medidas (preservación de marginales, signo y escala del ρ inducido, y el
  contraste con `dispersion_k`).

Se conserva porque el diagnóstico es real y el mecanismo está validado y probado;
lo que se rechaza es **desplegarlo**. Borrarlo perdería los tests y la medición.

## Pregunta abierta (no se persigue ahora)

El gradiente del ratio del margen con `λ_total` sugiere que la correlación
residual **depende de λ**, no es constante. Un `ρ(λ)` reproduciría el gradiente
del margen y podría además tocar el total.

**No se implementa en esta sesión, y el pre-registro también lo dejó escrito:**
*"si el gate lo acepta, el gradiente residual queda como pregunta abierta
separada, no como justificación para añadir un ρ dependiente de λ en la misma
sesión."* Con más razón ahora que el gate lo rechazó. Exigiría su propio
pre-registro.

## Expectativa declarada, cumplida

El pre-registro decía: *"la expectativa razonable es que esto mejore la
calibración de NHL sin producir ventaja explotable. Mejor dispersión no es
edge."* Ni siquiera llegó a mejorar la calibración de forma aceptable. El
resultado no mueve el hecho dominante del proyecto: el mercado sigue batiendo al
modelo con IC que excluye el cero.
