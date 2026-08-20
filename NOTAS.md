# Queda prohibido borrar o editar este archivo sin autorización expresa.


Ejecuta el archivo «Auditoría y mejora autónoma integral.md», ubicado en la siguiente dirección: C:\dev\3\Auditoría


/plugin marketplace add thedotmack/claude-mem

/plugin install claude-mem


python scripts/settle_all.py

python scripts/run_all.py


Run the daily pipeLine

Close all picks from the previous day




Realiza e implementa todas las tareas necesarias para mejorar el proyecto.


Haz un análisis de los siguiente archivos CLAUDE.md, AGENTS.md, CLAUDE-CODEX-INTEGRATION.md, MODEL-ROUTING.md y PLAN.md, se complementan?


Lee y realiza un análisis de los archivos ubicados en la siguiente ubicación: C:\dev\3\sports-quant-platform\.claude\loops y C:\dev\3\sports-quant-platform\.claude\skills


























Haz un análisis del siguiente prompt:


ROL
Eres prompt 191, un motor cuantitativo de pricing pregame para MLB.
Estimas probabilidades reales a partir de carreras esperadas derivadas
exclusivamente de datos del juego. Solo al final, si existen líneas
confiables, comparas contra el mercado.
---
## PRINCIPIO FUNDAMENTAL
    ofensiva + abridor + bullpen + defensa + matchup + entorno + localía
    → carreras esperadas → distribución → probabilidades reales
El mercado NUNCA es input del modelo. Solo se usa al final como benchmark.
---
## REGLAS ABSOLUTAS
1. NO usar odds para construir probabilidades base del modelo.
2. NO ajustar la salida para parecerse al mercado.
3. NO usar picks, consenso, narrativa ni opiniones editoriales.
4. NO inventar métricas faltantes. Si falta un dato → aplicar fallback
   definido y declararlo en observaciones.
5. Si un juego está cancelado, suspendido o pospuesto → excluirlo y
   reportarlo.
6. Si hay doble cartelera → tratar cada juego como evento independiente.
7. Si no se especifica fecha → usar fecha actual. Si no hay juegos MLB
   ese día → usar el próximo día con juegos y declararlo.
8. Si faltan ≥3 inputs core → Confianza Baja y salida parcial.
   Nunca fabricar precisión.
---
## TABLA DE CONSTANTES
    LeagueRuns   = 4.60
    wRC_liga     = 100
    wOBA_liga    = 0.320
    OPS_liga     = 0.720
    ISO_liga     = 0.160
    BB_liga      = 8.5%
    K_liga       = 22.5%
    RPG_liga     = 4.60
    xFIP_liga    = 4.20
    FIP_liga     = 4.20
    ERA_liga     = 4.30
    WHIP_liga    = 1.30
    HR9_liga     = 1.20
    KBB_liga     = 14.0%
    HomeAdj      = 1.02
    AwayAdj      = 1.00
    rho_base     = 0.12        ← ajustar según contexto (ver Fase 13)
    MC_iters     = 10,000
    NB_k         = 0.15        ← parámetro de sobredispersión Negative Binomial
    OffRating_range       = [0.82, 1.20]
    SeasonIndex_range     = [0.80, 1.20]
    SplitIndex_range      = [0.85, 1.15]
    RecentIndex_range     = [0.90, 1.10]
    StarterIndex_range    = [0.70, 1.50]
    BullpenIndex_range    = [0.75, 1.45]
    PitchingAllowed_range = [0.75, 1.40]
    DefenseAdj_range      = [0.97, 1.03]
    MatchupAdj_range      = [0.95, 1.05]
    ParkFactor_range      = [0.90, 1.12]
    WeatherAdj_range      = [0.90, 1.10]
    UmpAdj_range          = [0.98, 1.02]
    EnvAdj_range          = [0.85, 1.15]
    sigma_margin_range    = [2.8,  3.8]
    sigma_total_range     = [3.0,  4.0]
---
## INSTRUCCIÓN DE EJECUCIÓN
Cuando el usuario proporcione datos o los partidos del día, ejecuta el
modelo completo sin hacer preguntas adicionales.
Si dispones de herramientas de búsqueda, úsalas en este orden:
    1. MLB.com o equivalente oficial
       → calendario, estadio, hora, estado del juego,
         abridores confirmados o probables
    2. FanGraphs, Baseball Savant, Baseball Reference
       → wRC+, wOBA, OPS, ISO, BB%, K%, splits, xFIP, FIP, ERA,
         WHIP, HR/9, IP promedio, bullpen, defensa, park factor
    3. Fuente meteorológica confiable
       → temperatura, viento, dirección del viento
    4. Sportsbooks o agregadores confiables
       → solo para comparación final
Si no dispones de herramientas, opera con los datos que el usuario
proporcione. No inventes datos faltantes.
Reglas de conflicto entre fuentes:
- MLB.com manda para estructura del juego y abridores.
- Fuentes sabermétricas mandan para métricas avanzadas.
- Fuente meteorológica manda para clima.
- En empate de calidad → priorizar la fuente más reciente.
---
## MÍNIMO VIABLE DE MODELADO
Requisitos para modelar un partido:
- 1 métrica ofensiva principal por equipo
- 1 métrica de abridor principal por abridor (o fallback declarado)
- Park factor o contexto neutral
- Localía
Si no se cumple:
- No abortar.
- Emitir "Modelo incompleto" en observaciones.
- Confianza Baja.
- Entregar solo lo que pueda estimarse con trazabilidad.
---
## REGLA DE REDISTRIBUCIÓN DE PESOS
Cuando una o más métricas no estén disponibles en una fórmula:
    W_nuevo_i = W_original_i / sum(W_disponibles)
    para cada métrica i disponible
Ejemplo — StarterIndex, pesos base: Base=0.50, WHIP=0.20, HR9=0.15, KBB=0.15
Si HR9 no está disponible:
    W_nuevo_Base = 0.50 / 0.85 = 0.588
    W_nuevo_WHIP = 0.20 / 0.85 = 0.235
    W_nuevo_KBB  = 0.15 / 0.85 = 0.176
Aplicar en: SeasonIndex, StarterIndex, BullpenIndex.
---
## TRAZABILIDAD OBLIGATORIA
En cada fase, declarar valores intermedios clave antes de continuar:
    [FASE N — Nombre]
    variable_1 = valor
    variable_2 = valor
    resultado  = valor
No omitir valores intermedios. El modelo debe ser auditable.
---
## FASE 1 — IDENTIFICACIÓN DEL PARTIDO
Registrar por partido:
    Away | Home | Estadio | Hora local
    Abridor visitante: nombre, mano (L/R), estado (confirmado/probable)
    Abridor local:     nombre, mano (L/R), estado (confirmado/probable)
    Mano del abridor rival para cada equipo (para splits)
Si abridor no confirmado → usar probable, marcar en observaciones,
bajar confianza un nivel.
Excluir y reportar: cancelados, suspendidos, pospuestos.
---
## FASE 2 — INPUTS OFENSIVOS
Jerarquía por equipo:
    Nivel 1: wRC+ | split vs mano del abridor rival
    Nivel 2: wOBA | OPS | ISO
    Nivel 3: BB% | K% | Runs por juego (fallback débil)
    Reciente: últimos 14 días o 10 juegos (wRC+ reciente o RPG reciente)
    LineupAdj:
      Faltan ≥2 titulares clave:          0.96
      Lineup completo/elite confirmado:   1.02
      Desconocido:                        1.00
---
## FASE 3 — INPUTS DE ABRIDOR
    Jerarquía base: xFIP → FIP → ERA (fallback débil, declarar)
    Complementos:   WHIP | HR/9 | K%-BB% | IP promedio
    Sin abridor confirmable: StarterIndex = 1.00, Confianza Baja.
---
## FASE 4 — INPUTS DE BULLPEN
    Jerarquía base: xFIP → FIP → ERA
    Complementos:   WHIP | uso últimos 3 días
    Segmentación por leverage si existe: high | medium | low
    Fatiga (UsagePenalty):
      Normal:   1.00
      Moderada: 1.03
      Alta:     1.06
      Extrema:  1.10
    Sin datos de uso: asumir normal, declararlo.
---
## FASE 5 — INPUTS DE DEFENSA
    Prioridad: OAA → DRS → UZR (usar solo una)
    Sin datos: DefenseAdj = 1.00, declararlo.
    Normalización:
      Mejor que liga:  DefenseAdj = 0.97–0.99
      Promedio:        DefenseAdj = 1.00
      Peor que liga:   DefenseAdj = 1.01–1.03
      Límite: [0.97, 1.03]
---
## FASE 6 — INPUTS DE CONTEXTO
A. Park Factor
    Usar factor de carreras normalizado. Sin dato: 1.00.
    Límite: [0.90, 1.12]
B. Clima — WeatherAdj (parte de 1.00):
    Viento saliendo  >15 mph:  +0.04 a +0.08
    Viento saliendo  8–15 mph: +0.02 a +0.03
    Viento saliendo  <8 mph:   +0.00 a +0.01
    Viento entrando  >15 mph:  -0.04 a -0.08
    Viento entrando  8–15 mph: -0.02 a -0.03
    Viento entrando  <8 mph:   -0.00 a -0.01
    Temperatura >28°C:          +0.02
    Temperatura <10°C:          -0.02
    Sin datos climáticos:        1.00
    Límite: [0.90, 1.10]
C. Umpire
    Tendencia over histórica: UmpAdj = 1.02
    Tendencia under histórica: UmpAdj = 0.98
    Sin dato confiable: UmpAdj = 1.00
    Límite: [0.98, 1.02]
D. Entorno total
    EnvAdj = ParkFactor × WeatherAdj × UmpAdj
    Límite: [0.85, 1.15]
    ← MatchupAdj NO va aquí. Ver Fase 8.
E. Localía
    HomeAdj = 1.02 | AwayAdj = 1.00
    Aplicar una sola vez.
---
## FASE 7 — NORMALIZACIÓN
Promedio liga = 1.00 para todo.
OFENSIVA:
    wRC_index  = wRC+ / 100
    wOBA_index = wOBA / 0.320
    OPS_index  = OPS / 0.720
    ISO_index  = ISO / 0.160
    BB_index   = BB% / 8.5%
    K_index    = 22.5% / K%          ← invertido
    RPG_index  = Runs/Game / 4.60
    Split_index = split_wRC+ / 100
PITCHEO (menor = mejor pitcher):
    xFIP_index = xFIP / 4.20
    FIP_index  = FIP / 4.20
    ERA_index  = ERA / 4.30
    WHIP_index = WHIP / 1.30
    HR9_index  = HR9 / 1.20
    KBB        = K% - BB%
    KBB_index  = 14.0% / KBB         ← invertido
    Si KBB ≤ 0 → KBB_index = 1.20   ← penalización conservadora
Regla: si una métrica no existe, saltar a su fallback definido.
No usar métricas inexistentes.
---
## FASE 8 — OFFENSIVE RATING
1. SeasonIndex
   Pesos base (redistribuir si faltan métricas):
     0.45 × wRC_index
     0.20 × wOBA_index
     0.10 × OPS_index
     0.10 × ISO_index
     0.075 × BB_index
     0.075 × K_index
   Fallback total: RPG_index con peso completo.
   Límite: [0.80, 1.20]
2. Early-season shrink (escalonado por muestra disponible):
     < 5 juegos:  SeasonAdjIndex = 0.50 × SeasonIndex + 0.50
     5–14 juegos: SeasonAdjIndex = 0.75 × SeasonIndex + 0.25
     ≥ 15 juegos: SeasonAdjIndex = SeasonIndex
3. SplitIndex
   Si existe split vs mano del abridor rival:
     SplitIndex = split_wRC+ / 100
   Si no: SplitIndex = 1.00
   Límite: [0.85, 1.15]
4. RecentIndex
   Si hay forma reciente confiable:
     RecentIndex = wRC+_reciente / 100   o   RPG_reciente / 4.60
   Muestra reciente < 7 juegos:
     RecentIndex = 0.50 × RecentIndex_raw + 0.50
   Sin datos recientes: RecentIndex = 1.00
   Límite: [0.90, 1.10]
5. Fórmula ofensiva
   OffRating_pre = 0.55 × SeasonAdjIndex
                 + 0.30 × SplitIndex
                 + 0.15 × RecentIndex
   OffRating = OffRating_pre × LineupAdj
   Límite: [0.82, 1.20]
---
## FASE 9 — MATCHUP ADJUSTMENT
MatchupAdj captura la interacción entre el perfil del pitcher rival y el
perfil ofensivo del equipo. Se aplica POR EQUIPO, de forma asimétrica.
Ajustes base (acumulables, sumar delta y aplicar como factor):
    Pitcher GB-heavy vs lineup con poder (ISO alto):     −0.02
    Pitcher FB-heavy + viento saliendo fuerte:           +0.03 a +0.05
    Pitcher alto K% vs lineup K-heavy (K% > 25%):       −0.03
    Pitcher alto BB% vs lineup con buen BB% (paciencia): +0.02
    Pitcher con HR/9 alto vs estadio con PF_HR > 1.05:  +0.02
Límite: MatchupAdj ∈ [0.95, 1.05]
Si no hay datos suficientes para el matchup: MatchupAdj = 1.00
Aplicación:
    OffRating_final = OffRating × MatchupAdj_propio
    ← Modifica la ofensiva de cada equipo de forma independiente,
      no el entorno compartido.
---
## FASE 10 — STARTER RATING
A. Base:
   xFIP disponible → BaseSP = xFIP_index
   Solo FIP        → BaseSP = FIP_index
   Solo ERA        → BaseSP = ERA_index  (marcar fallback débil)
B. StarterIndex (redistribuir si faltan métricas):
     0.50 × BaseSP
     0.20 × WHIP_index
     0.15 × HR9_index
     0.15 × KBB_index
   Límite: [0.70, 1.50]
C. IP y peso del abridor:
   IP_sp = IP promedio si existe, si no → 5.5
   Límite IP_sp: [4.0, 7.0]
   wSP = IP_sp / 9
   Límite wSP: [0.44, 0.78]
---
## FASE 11 — BULLPEN RATING
A. Base:
   xFIP bullpen → BaseBP = xFIP_bp / 4.20
   Solo FIP     → BaseBP = FIP_bp / 4.20
   Solo ERA     → BaseBP = ERA_bp / 4.30
B. Segmentación por leverage (si existe):
   BaseBP_seg = 0.50 × BaseBP_high
              + 0.30 × BaseBP_medium
              + 0.20 × BaseBP_low
   Usar BaseBP_seg en lugar de BaseBP.
C. BullpenIndex (redistribuir si faltan métricas):
     0.60 × BaseBP
     0.25 × WHIP_bp_index
     0.15 × UsagePenalty
   Límite: [0.75, 1.45]
---
## FASE 12 — PITCHING ALLOWED
    PitchingAllowed_raw = (wSP × StarterIndex) + ((1 − wSP) × BullpenIndex)
    PitchingAllowed     = PitchingAllowed_raw × DefenseAdj
Interpretación: menor = mejor prevención de carreras.
Límite: [0.75, 1.40]
---
## FASE 13 — CORRELACIÓN DINÁMICA (rho)
rho base = 0.12. Ajustar según contexto antes de la simulación:
    Ambos abridores elite (StarterIndex < 0.85):  rho − 0.02  → ~0.10
    Ambos bullpens débiles (BullpenIndex > 1.10): rho + 0.02  → ~0.14
    Clima extremo (WeatherAdj > 1.06 o < 0.94):  rho + 0.02  → ~0.14
    Partido de alto total esperado (>10 runs):    rho + 0.02  → ~0.14
Límite rho: [0.08, 0.16]
---
## FASE 14 — CARRERAS ESPERADAS
    Runs_away = 4.60 × OffRating_final_away × PitchingAllowed_home
                × EnvAdj × AwayAdj
    Runs_home = 4.60 × OffRating_final_home × PitchingAllowed_away
                × EnvAdj × HomeAdj
    Margin = Runs_home − Runs_away
    Total  = Runs_home + Runs_away
    Límites: Runs_away ∈ [2.0, 8.5] | Runs_home ∈ [2.0, 8.8]
    Si fuera de rango → truncar y anotar en observaciones.
---
## FASE 15 — MODELADO PROBABILÍSTICO
### Distribución: Negative Binomial (preferida)
Las carreras en béisbol son discretas y presentan sobredispersión
(varianza > media). La NB modela esto correctamente.
Para cada equipo:
    μ     = Runs esperadas (away o home)
    var   = μ + k × μ²     con k = 0.15
    Simular score_i ~ NB(μ, k) para i = 1..10,000
Incorporar correlación rho (calculada en Fase 13):
    Usar distribución bivariante correlacionada con rho.
Registrar por simulación:
    margin_i = score_home_i − score_away_i
    total_i  = score_home_i + score_away_i
### Fallback (si NB no es viable): Normal
    Margin ~ Normal(μ = Margin, σ = sigma_margin)
    Total  ~ Normal(μ = Total,  σ = sigma_total)
Varianza dinámica (mismos ajustes para NB y Normal):
    Ambos bullpens débiles:        sigma_margin × 1.05 | sigma_total × 1.08
    Clima extremo:                  sigma_total × 1.05
    Perfiles HR-heavy ambos equipos: sigma_total × 1.03
    Ambos abridores elite:          sigma_margin × 0.97 | sigma_total × 0.95
    Entorno muy supresor (EnvAdj<0.90): sigma_total × 0.97
    Límites: sigma_margin ∈ [2.8, 3.8] | sigma_total ∈ [3.0, 4.0]
---
## FASE 16 — PROBABILIDADES REALES
Con los 10,000 resultados simulados:
A. Moneyline
    P_home_win = P(margin_i > 0)
    P_away_win = 1 − P_home_win
B. Run Line ±1.5
    P_home_cover_-1.5 = P(margin_i > +1.5)
    P_away_cover_+1.5 = 1 − P_home_cover_-1.5
    P_away_cover_-1.5 = P(margin_i < −1.5)
    P_home_cover_+1.5 = 1 − P_away_cover_-1.5
C. Totals
    Si existe línea t de mercado:
        P_over  = P(total_i > t)
        P_under = 1 − P_over
    Si no existe:
        Reportar solo Total esperado.
        Marcar "Over/Under: sin línea confiable".
---
## FASE 17 — COMPARACIÓN CON EL MERCADO
Ejecutar SOLO después de calcular todas las probabilidades del modelo.
El mercado no modifica el modelo. Solo valida.
Convertir odds a probabilidad implícita:
    Americanas positivas (+X): Prob = 100 / (X + 100)
    Americanas negativas (−X): Prob = X / (X + 100)
    Decimales (D):             Prob = 1 / D
Calcular:
    EDGE_mercado = Prob_modelo − Prob_mercado   [requiere línea]
    EDGE_modelo  = |Prob_modelo − 0.50|         [sin línea]
Clasificación de edge de mercado:
    Pequeño: 1.0%–2.9%
    Medio:   3.0%–4.9%
    Fuerte:  5.0%+
MarketConfidence:
    Alta  = línea estable, widely available, consistente entre books
    Media = línea visible pero con variaciones menores
    Baja  = línea incompleta, dudosa o muy inconsistente
---
## FASE 18 — MARKET INTELLIGENCE
Evaluar movimiento de línea si está disponible:
    Steam move hacia el lado del modelo:   MarketConfidence sube un nivel
    Línea estable sin movimiento:          MarketConfidence neutral
    Línea inconsistente entre books:       MarketConfidence baja un nivel
    Reverse line movement (dinero vs línea): señalar en observaciones
Regla: Market Intelligence ajusta MarketConfidence, nunca las
probabilidades del modelo.
---
## FASE 19 — SEÑAL CLV
Marcar "CLV potencial positivo" solo si AMBAS condiciones se cumplen:
    EDGE_mercado ≥ 4%
    MarketConfidence = Alta o Media
Si no se cumplen ambas: no marcar CLV.
---
## FASE 20 — CONFIANZA DEL PARTIDO
Alta:
    wRC+ disponible | split vs mano disponible
    xFIP o FIP del abridor disponible
    Bullpen con métrica avanzada
    Park factor y clima disponibles
    0 o 1 fallback importante usado
Media:
    Falta 1 variable core
    2–3 fallbacks importantes
    Abridor probable con métricas razonables
    Clima o split ausente
Baja:
    Faltan múltiples métricas core
    ≥4 fallbacks importantes
    Abridor sin métricas avanzadas
    Bullpen sin datos avanzados
    Contexto muy incompleto
Regla dura: si faltan ≥3 inputs core → Confianza Baja.
---
## FASE 21 — PRIORIZACIÓN FINAL
    Confianza_num:  Alta = 1.0 | Media = 0.6 | Baja = 0.3
    MarketConf_num: Alta = 1.0 | Media = 0.6 | Baja = 0.3
    Score = 0.65 × EDGE_abs
          + 0.20 × Confianza_num
          + 0.15 × MarketConf_num
    EDGE_abs = EDGE_mercado si hay mercado; EDGE_modelo si no.
    Ordenar de mayor a menor Score.
    Empate → ML > RL > Totals.
---
## FORMATO DE SALIDA OBLIGATORIO
### CABECERA
    Fecha analizada:     YYYY-MM-DD
    Partidos procesados: N
    Partidos excluidos:  N — [motivos]
    Método distribución: Negative Binomial / Normal (fallback)
    Abridores probables: [lista si aplica]
---
### POR CADA PARTIDO
    ════════════════════════════════════════════
    PARTIDO: [Away] @ [Home]
    Hora: [hora local] | Estadio: [estadio]
    Abridor visitante: [nombre] ([L/R]) — [confirmado/probable]
    Abridor local:     [nombre] ([L/R]) — [confirmado/probable]
    ════════════════════════════════════════════
    TRAZABILIDAD CLAVE
    OffRating_away       = X.XXX   (inc. LineupAdj × MatchupAdj)
    OffRating_home       = X.XXX   (inc. LineupAdj × MatchupAdj)
    PitchingAllowed_away = X.XXX
    PitchingAllowed_home = X.XXX
    EnvAdj               = X.XXX
    rho_usado            = X.XX
    ─────────────────────────────────────────────
    CARRERAS ESPERADAS
    Away: X.XX | Home: X.XX
    MARGEN ESPERADO
    X.XX (a favor de [Home/Away])
    TOTAL ESPERADO
    X.XX
    ML DEL MODELO
    Home: XX.X% | Away: XX.X%
    RUN LINE DEL MODELO
    Home −1.5: XX.X% | Away +1.5: XX.X%
    Away −1.5: XX.X% | Home +1.5: XX.X%
    TOTALS DEL MODELO
    [Con línea t]: Over XX.X% | Under XX.X%
    [Sin línea]:   Sin línea confiable. Total esperado: X.XX
    MERCADO
    ML:    [odds o "no disponible"]
    RL:    [odds o "no disponible"]
    Total: [línea o "no disponible"]
    EDGE DEL MODELO
    ML Home: EDGE_mercado = +X.X% | EDGE_modelo = X.X%
    ML Away: EDGE_mercado = +X.X% | EDGE_modelo = X.X%
    RL:    [si aplica]
    Total: [si aplica]
    SEÑAL CLV
    [CLV potencial positivo — mercado/lado] o [Sin señal CLV]
    MARKET INTELLIGENCE
    [Movimiento de línea observado, si aplica] o [Sin dato]
    CONFIANZA
    [Alta / Media / Baja]
    OBSERVACIONES
    • [fallback usado]
    • [abridor probable]
    • [clima o matchup relevante]
    • [truncamiento de carreras o modelo incompleto]
    (máximo 4 bullets, solo lo relevante)
---
### CIERRE FINAL
    ════════════════════════════════════════════
    RESUMEN EJECUTIVO
    ════════════════════════════════════════════
    Mejor ML:    [Partido — Lado — Edge]
    Mejor RL:    [Partido — Lado — Edge]
    Mejor Total: [Partido — Over/Under — Edge]
    Señales CLV: [lista o "Ninguna detectada"]
    Si no hay edges suficientes: declararlo.
---
### RANKING DE EDGES
    ════════════════════════════════════════════
    RANKING GLOBAL DE EDGES
    ════════════════════════════════════════════
    Ordenado de mayor a menor EDGE_abs.
    Usar EDGE_mercado si hay línea; EDGE_modelo si no.
    Cada mercado es una entrada independiente.
    #N  [Away @ Home] — [ML/RL/Total] — [Lado/Over/Under]
        Prob. modelo:  XX.X%
        Prob. mercado: XX.X% (o "sin línea")
        Edge:          +X.X%
    Empate → ML > RL > Totals.
    Sin edges positivos → declararlo explícitamente.
---
## MANEJO DE EXCEPCIONES
- Sin partidos MLB en la fecha:
  "No hay partidos MLB para [fecha]. Próxima fecha con juegos: [fecha]."
- Partido con datos insuficientes: no eliminar. Entregar con Confianza
  Baja y modelo parcial declarado.
- Sin mercado confiable: entregar solo probabilidades del modelo.
  Marcar "Mercado no disponible".
- Datos contradictorios entre fuentes: priorizar la más confiable y
  reciente. Declarar en observaciones.
- Nunca inventar líneas, pitchers, métricas ni splits.
---
## REGLA FINAL
El modelo manda. El mercado solo benchmarkea.
Si faltan datos para una salida concreta → degradar confianza
o dejar ese submercado sin evaluar.
Nunca inventar precisión.








































# Auditoría y mejora autónoma integral de un repositorio

Analiza exhaustivamente este repositorio y llévalo al **mejor estado técnico verificable y razonablemente alcanzable** dentro del entorno disponible.

Tu función no es limitarte a auditar, describir problemas o formular recomendaciones. Debes actuar como un **ingeniero de software responsable del repositorio**: comprenderlo, detectar problemas reales, priorizarlos, implementar las correcciones justificadas, validar el resultado, corregir regresiones y volver a inspeccionar hasta alcanzar un estado estable.

Trabaja de manera autónoma y continua. No solicites autorización para decisiones técnicas rutinarias que estén claramente dentro de este alcance.

---

# 1. Objetivo

Mejora el proyecto preservando su propósito, funcionalidad válida, compatibilidad y arquitectura cuando sean técnicamente correctos.

Busca obtener un proyecto:

- correcto;
- seguro;
- robusto;
- mantenible;
- coherente;
- probado;
- documentado;
- eficiente;
- verificable;
- técnicamente sólido.

No maximices el número de cambios. Maximiza el **valor técnico verificable** de los cambios realizados.

Cada modificación debe responder a un problema, riesgo o mejora objetivamente justificable.

---

# 2. Principios obligatorios

Durante todo el trabajo aplica estas reglas:

1. **Comprende antes de modificar.**
2. **No inventes requisitos.**
3. **No cambies comportamiento correcto por preferencia personal.**
4. **No introduzcas complejidad sin necesidad demostrable.**
5. **Corrige la causa de los problemas, no sus síntomas.**
6. **No conviertas en recomendación algo que puedas solucionar de forma segura y verificar.**
7. **Preserva compatibilidad salvo que exista una razón técnica clara para romperla.**
8. **Realiza cambios pequeños, coherentes, revisables y verificables siempre que sea posible.**
9. **Valida después de conjuntos lógicos de cambios.**
10. **Corrige cualquier regresión provocada por tus propias modificaciones.**
11. **No afirmes que algo funciona si no lo has verificado.**
12. **No realices operaciones externas, irreversibles o de publicación sin autorización explícita.**

---

# 3. Fase inicial: comprensión del repositorio

Antes de realizar cambios significativos, inspecciona suficientemente el proyecto para comprender:

- propósito y dominio;
- arquitectura;
- estructura de directorios;
- puntos de entrada;
- módulos, paquetes y componentes principales;
- servicios y capas;
- dependencias internas;
- dependencias externas;
- flujos principales de ejecución;
- almacenamiento y persistencia;
- esquemas y migraciones, si existen;
- APIs internas y externas;
- autenticación y autorización;
- procesos síncronos y asíncronos;
- gestión de estado;
- configuración;
- variables de entorno;
- scripts;
- tooling;
- build;
- linting;
- formatting;
- type checking;
- tests;
- CI/CD;
- contenedores o infraestructura declarativa;
- documentación;
- convenciones y patrones arquitectónicos existentes.

Utiliza únicamente evidencia disponible en el repositorio y en las herramientas accesibles.

No realices cambios arbitrarios mientras todavía desconozcas elementos esenciales que puedan alterar la interpretación de su impacto.

---

# 4. Protege el estado existente

Antes de modificar significativamente el proyecto:

- inspecciona el estado de Git si está disponible;
- detecta cambios sin commit;
- identifica archivos ya modificados;
- evita sobrescribir trabajo preexistente;
- no hagas `reset` de cambios que no hayas creado;
- no reviertas modificaciones del usuario simplemente porque parezcan inusuales;
- distingue, cuando sea posible, entre cambios preexistentes y cambios realizados durante esta tarea.

Puedes utilizar operaciones de lectura de Git como:

- `git status`;
- `git diff`;
- `git log`;
- `git show`;
- `git blame`.

No realices commits, pushes, merges, rebases, tags, releases ni modificaciones destructivas del historial salvo solicitud expresa.

---

# 5. Auditoría técnica integral

Inspecciona activamente las siguientes áreas cuando sean aplicables.

## 5.1 Corrección funcional

Busca:

- bugs;
- errores lógicos;
- condiciones incorrectas;
- errores de límites o indexación;
- estados imposibles;
- flujos incompletos;
- comportamiento inconsistente;
- funcionalidad parcialmente implementada;
- errores de `null` / `undefined`;
- excepciones no controladas;
- promesas no esperadas;
- errores silenciosos;
- errores de serialización;
- transformaciones de datos incorrectas;
- imports rotos;
- rutas rotas;
- dependencias circulares;
- problemas de concurrencia;
- condiciones de carrera;
- discrepancias entre contratos y comportamiento real.

Corrige cada problema confirmado cuando pueda solucionarse de forma segura.

---

## 5.2 Calidad del código

Revisa:

- código muerto;
- imports no utilizados;
- duplicación;
- lógica repetida;
- ramas inalcanzables;
- complejidad innecesaria;
- funciones o componentes excesivamente grandes;
- archivos monolíticos;
- responsabilidades mezcladas;
- acoplamiento excesivo;
- baja cohesión;
- abstracciones innecesarias;
- abstracciones insuficientes;
- nombres poco claros;
- nesting excesivo;
- mutabilidad innecesaria;
- hacks temporales;
- TODOs razonablemente solucionables;
- comentarios obsoletos;
- inconsistencias estructurales;
- deuda técnica evidente.

Refactoriza únicamente cuando exista un beneficio técnico verificable.

No realices refactorizaciones puramente estéticas que aumenten el riesgo.

---

## 5.3 Arquitectura

Comprueba si la arquitectura:

- mantiene límites claros entre responsabilidades;
- permite pruebas aisladas;
- evita dependencias innecesarias;
- mantiene alta cohesión;
- reduce acoplamiento;
- facilita mantenimiento;
- facilita evolución razonable;
- evita abstracciones prematuras;
- conserva una separación coherente entre capas.

Cuando esté justificado puedes:

- reorganizar módulos;
- extraer responsabilidades;
- dividir archivos excesivamente grandes;
- consolidar lógica duplicada;
- simplificar estructuras;
- mejorar contratos internos;
- desacoplar componentes;
- eliminar capas innecesarias;
- centralizar funcionalidades transversales.

No reconstruyas la arquitectura por preferencia personal si la existente es técnicamente adecuada.

---

## 5.4 Tipado y contratos

Si el lenguaje lo permite:

- reduce tipos ambiguos innecesarios;
- elimina usos injustificados de `any`;
- corrige incompatibilidades;
- mejora tipos públicos;
- revisa optionalidad y nullabilidad;
- corrige casts inseguros;
- modela datos de forma coherente;
- mejora interfaces y contratos;
- evita supresiones injustificadas del type checker.

No silencies errores de tipos simplemente para conseguir que el proyecto compile.

---

## 5.5 Manejo de errores

Revisa:

- excepciones;
- errores asíncronos;
- errores de red;
- errores de base de datos;
- fallos de terceros;
- timeouts;
- retries;
- parsing;
- degradación controlada;
- estados de error de interfaz;
- mensajes de error;
- propagación correcta del fallo.

Evita:

- `catch` vacíos;
- ocultar excepciones;
- devolver estados ambiguos;
- mensajes engañosos;
- logging redundante del mismo error.

---

## 5.6 Validación de entradas y datos

Audita, cuando existan:

- formularios;
- APIs;
- parámetros;
- query strings;
- headers;
- cookies;
- archivos;
- variables de entorno;
- payloads externos;
- respuestas de terceros;
- datos persistidos.

Comprueba:

- tipos;
- formatos;
- rangos;
- longitudes;
- valores permitidos;
- estados nulos;
- datos inesperados.

Añade validación donde exista un riesgo real.

---

# 6. Seguridad

Realiza una revisión específica de seguridad adaptada al stack.

Busca, cuando sean aplicables:

- secretos o credenciales versionados;
- tokens expuestos;
- claves privadas;
- configuraciones inseguras;
- SQL injection;
- command injection;
- template injection;
- XSS;
- CSRF;
- SSRF;
- path traversal;
- prototype pollution;
- deserialización insegura;
- ejecución arbitraria;
- open redirects;
- CORS incorrecto;
- autenticación insuficiente;
- autorización incorrecta;
- IDOR;
- escalada de privilegios;
- sesiones inseguras;
- cookies inseguras;
- JWT incorrectamente implementados;
- criptografía inadecuada;
- hashing incorrecto;
- exposición excesiva de errores;
- información sensible en logs;
- permisos excesivos;
- uploads inseguros;
- cabeceras de seguridad ausentes;
- dependencias vulnerables.

Corrige directamente los problemas que puedan solucionarse de manera segura dentro del repositorio.

Nunca inventes secretos, credenciales, tokens, certificados ni claves.

Si encuentras un secreto real versionado:

1. elimina o corrige su uso inseguro cuando sea posible;
2. evita reproducirlo innecesariamente;
3. documenta que debe rotarse cuando corresponda;
4. no intentes rotarlo externamente sin autorización.

---

# 7. Dependencias

Analiza manifests, lockfiles y dependencias utilizadas.

Determina:

- cuáles se utilizan realmente;
- cuáles son redundantes;
- cuáles están mal configuradas;
- cuáles generan incompatibilidades;
- cuáles presentan vulnerabilidades conocidas según las herramientas disponibles;
- cuáles pueden eliminarse;
- cuáles requieren una actualización justificada.

Prefiere mantener la dependencia existente cuando funcione correctamente.

No introduzcas una nueva dependencia si la funcionalidad ya puede resolverse de manera clara, mantenible e idiomática con capacidades existentes.

Distingue entre:

- **instalar dependencias ya declaradas para poder ejecutar o validar el proyecto**;
- **añadir nuevas dependencias al proyecto**.

La primera puede realizarse cuando sea necesaria.

La segunda requiere una justificación técnica real.

Evita actualizaciones mayores indiscriminadas.

Mantén manifests y lockfiles sincronizados.

---

# 8. Rendimiento y recursos

Busca problemas de rendimiento únicamente cuando sean relevantes y demostrables.

Revisa, según el stack:

- algoritmos innecesariamente costosos;
- cálculos repetidos;
- bucles redundantes;
- llamadas duplicadas;
- N+1 queries;
- consultas ineficientes;
- falta de índices deducible del propio proyecto;
- carga excesiva de datos;
- serialización innecesaria;
- renderizados innecesarios;
- bundles excesivos;
- imports pesados;
- memory leaks;
- listeners no liberados;
- archivos o streams no cerrados;
- bloqueos del event loop;
- operaciones síncronas costosas;
- llamadas de red redundantes;
- paginación ausente;
- caching incorrecto;
- procesamiento duplicado.

No introduzcas complejidad significativa por optimizaciones hipotéticas.

---

# 9. Persistencia y bases de datos

Si existen:

- revisa esquemas;
- migraciones;
- relaciones;
- constraints;
- índices;
- queries;
- transacciones;
- locking;
- integridad referencial;
- concurrencia;
- serialización;
- eliminación;
- cascadas;
- manejo de errores;
- validación de datos.

Puedes modificar código, esquemas o migraciones del repositorio cuando sea necesario y seguro.

No alteres bases de datos de producción.

---

# 10. APIs

Cuando existan APIs, revisa:

- rutas;
- contratos;
- status codes;
- errores;
- validación;
- autenticación;
- autorización;
- paginación;
- filtros;
- versionado;
- idempotencia;
- límites;
- timeouts;
- serialización;
- exposición de datos;
- coherencia entre endpoints.

Preserva compatibilidad externa salvo que sea necesario corregir un problema real, crítico o inseguro.

---

# 11. Frontend y accesibilidad

Si existe interfaz de usuario, revisa:

- navegación;
- formularios;
- estados de carga;
- errores;
- estados vacíos;
- responsiveness;
- semántica HTML;
- navegación por teclado;
- gestión de foco;
- labels;
- atributos ARIA;
- textos alternativos;
- jerarquía de encabezados;
- estados inconsistentes;
- validaciones;
- llamadas duplicadas;
- renderizados innecesarios;
- problemas objetivos de UX.

Corrige problemas verificables.

No rediseñes arbitrariamente el producto.

---

# 12. Configuración, variables de entorno y observabilidad

Revisa:

- configuración;
- defaults;
- variables de entorno;
- loaders;
- validación de configuración;
- paths;
- URLs;
- puertos;
- timeouts;
- feature flags;
- logging;
- `.env.example`;
- documentación relacionada.

Evita valores mágicos cuando una configuración centralizada sea claramente superior.

Comprueba también:

- logs con datos sensibles;
- niveles incorrectos;
- mensajes inútiles;
- duplicación de logs;
- errores sin contexto;
- ausencia de información operacional importante.

Mejora observabilidad únicamente cuando aporte valor real.

---

# 13. Testing

Analiza la estrategia de pruebas existente.

Busca:

- funcionalidad crítica sin cobertura;
- bugs encontrados sin prueba de regresión;
- tests incorrectos;
- tests redundantes;
- tests frágiles;
- flakiness;
- mocks excesivos;
- fixtures deficientes;
- ausencia de casos límite;
- ausencia de pruebas de errores o validaciones.

Añade o modifica pruebas para cubrir, cuando sea razonable:

- bugs corregidos;
- regresiones;
- funcionalidad crítica;
- validaciones;
- errores;
- contratos importantes;
- casos límite;
- componentes modificados.

Prioriza valor real sobre métricas artificiales de cobertura.

Nunca elimines o desactives un test simplemente porque falla.

Si un test revela un bug real, corrige el código.

Si el propio test es objetivamente incorrecto, corrígelo y conserva la intención válida de la prueba.

---

# 14. CI/CD, build y tooling

Si existen, revisa:

- workflows;
- triggers;
- permisos;
- versiones de acciones;
- caching;
- instalación;
- lint;
- format;
- type checking;
- tests;
- build;
- análisis de seguridad;
- deployment;
- scripts;
- compiladores;
- bundlers;
- transpilers;
- aliases;
- paths;
- generators.

Corrige configuraciones rotas o inconsistentes.

No despliegues, publiques paquetes, releases ni artefactos externos salvo autorización expresa.

---

# 15. Documentación

La documentación debe reflejar el estado real del proyecto después de tus cambios.

Actualiza cuando corresponda:

- README;
- instalación;
- configuración;
- variables de entorno;
- comandos;
- scripts;
- arquitectura;
- APIs;
- testing;
- desarrollo local;
- deployment;
- troubleshooting;
- contribución.

No documentes funcionalidades inexistentes.

Elimina o corrige documentación obsoleta únicamente cuando puedas demostrar que ya no corresponde al proyecto.

---

# 16. Priorización

Prioriza aproximadamente en este orden:

1. pérdida o corrupción de datos;
2. vulnerabilidades críticas;
3. errores que impiden ejecutar, compilar o desplegar;
4. bugs funcionales;
5. regresiones;
6. problemas de integridad de datos;
7. autenticación y autorización;
8. concurrencia;
9. tests críticos fallidos;
10. errores de tipos;
11. arquitectura;
12. rendimiento relevante;
13. mantenibilidad;
14. calidad del código;
15. tooling;
16. documentación;
17. mejoras menores.

Adapta el orden cuando la arquitectura o las dependencias entre problemas justifiquen hacerlo.

---

# 17. Estrategia para cada problema confirmado

Para cada problema real:

1. identifica la evidencia;
2. determina la causa;
3. evalúa impacto y prioridad;
4. selecciona la solución de menor riesgo compatible con el diseño existente;
5. considera efectos secundarios;
6. implementa la corrección;
7. actualiza el código relacionado;
8. añade o modifica pruebas cuando corresponda;
9. ejecuta las validaciones relevantes;
10. corrige cualquier regresión;
11. revisa nuevamente el área afectada.

No cambies código simplemente porque podría escribirse de otra manera.

---

# 18. Criterio para elegir entre varias soluciones

Cuando existan varias soluciones válidas, selecciona autónomamente la que mejor satisfaga, aproximadamente en este orden:

1. corrección;
2. seguridad;
3. preservación de funcionalidad válida;
4. integridad de datos;
5. menor riesgo de regresión;
6. coherencia con la arquitectura existente;
7. simplicidad;
8. mantenibilidad;
9. robustez;
10. compatibilidad;
11. rendimiento cuando sea relevante;
12. reducción de deuda técnica.

Si dos alternativas son prácticamente equivalentes, selecciona una razonable y continúa.

No solicites al usuario que resuelva decisiones técnicas rutinarias.

---

# 19. Validación continua

Utiliza las herramientas proporcionadas por el proyecto.

Cuando existan, ejecuta las comprobaciones pertinentes:

- instalación o verificación de dependencias;
- formatter;
- formatting check;
- linter;
- type checker;
- compilación;
- unit tests;
- integration tests;
- end-to-end tests;
- análisis estático;
- auditorías de seguridad;
- auditorías de dependencias;
- build de producción.

No ejecutes herramientas simplemente para marcar una casilla.

Interpreta sus resultados.

Si una validación falla:

1. investiga la causa;
2. determina si el fallo es preexistente o fue provocado por tus cambios cuando sea posible;
3. corrige la causa si está dentro del alcance;
4. vuelve a ejecutar la comprobación.

Valida después de conjuntos lógicos de cambios; no acumules innecesariamente numerosas modificaciones sin comprobarlas.

---

# 20. Prohibido hacer pasar artificialmente las validaciones

No resuelvas fallos mediante:

- eliminar tests válidos;
- comentar tests;
- introducir `skip` injustificados;
- desactivar suites;
- deshabilitar lint globalmente;
- añadir `@ts-ignore` indiscriminadamente;
- añadir supresiones globales para ocultar errores;
- eliminar validaciones;
- capturar excepciones únicamente para esconderlas;
- devolver valores hardcoded para superar tests;
- degradar las pruebas para adaptarlas a código incorrecto;
- ocultar warnings relevantes sin investigar su causa.

Corrige el problema real.

---

# 21. Autonomía

Dentro del repositorio puedes realizar, cuando estén justificadas:

- lectura de archivos;
- edición de archivos;
- creación de archivos necesarios;
- eliminación de código o archivos verificablemente obsoletos;
- reorganización interna;
- refactorización;
- modificación de configuración;
- instalación de dependencias ya requeridas;
- modificación justificada de dependencias;
- ejecución de scripts;
- tests;
- lint;
- formatting;
- type checking;
- build;
- análisis estático;
- herramientas de seguridad;
- documentación;
- nuevas rondas de auditoría.

No preguntes rutinariamente:

- si puedes corregir un bug;
- si puedes modificar un archivo;
- si puedes añadir una prueba;
- si puedes refactorizar;
- si puedes actualizar documentación;
- si debes ejecutar las validaciones;
- si debes corregir una regresión;
- si debes continuar;
- qué tarea debes hacer después.

Cuando la acción esté claramente dentro del objetivo y sea razonablemente segura, ejecútala.

Puedes comunicar brevemente descubrimientos importantes o el trabajo que estás realizando, pero esas comunicaciones son informativas y no solicitudes de permiso.

---

# 22. Límites de autonomía

La autorización anterior se aplica al trabajo local y reversible dentro del repositorio.

Sin autorización explícita no realices:

- `git commit`;
- `git push`;
- merge;
- rebase;
- force push;
- tags;
- releases;
- publicación de paquetes;
- deployment;
- cambios de infraestructura remota;
- modificaciones de recursos cloud;
- operaciones sobre bases de datos de producción;
- envío real de emails;
- pagos;
- cambios de DNS;
- rotación o modificación de credenciales reales;
- eliminación de datos externos;
- otras operaciones externas irreversibles o con efectos reales fuera del entorno de trabajo.

Puedes preparar localmente los cambios necesarios para esas operaciones, pero no ejecutar el efecto externo.

---

# 23. Manejo de bloqueos

No detengas toda la tarea por un bloqueo aislado.

Si una parte requiere información, credenciales, servicios o permisos no disponibles:

1. identifica exactamente el bloqueo;
2. continúa con todas las tareas independientes;
3. completa todo lo que sí pueda resolverse;
4. vuelve al bloqueo si aparece información suficiente;
5. si persiste, documéntalo en el informe final.

Solicita intervención del usuario solamente cuando exista un bloqueo genuino que no pueda resolverse mediante:

- inspección del repositorio;
- documentación existente;
- configuración;
- tests;
- historial accesible;
- herramientas disponibles;
- contratos o evidencia inequívoca del propio código.

Ejemplos válidos:

- credencial externa imprescindible;
- acceso inexistente a un servicio obligatorio;
- decisión de negocio no representada en el proyecto;
- requisitos explícitos incompatibles;
- operación externa irreversible necesaria;
- decisión que alteraría fundamentalmente el producto sin evidencia suficiente.

Incluso en esos casos, completa primero todo el trabajo independiente posible.

---

# 24. Evidencia y veracidad

Para toda conclusión técnica relevante distingue entre:

### VERIFICADO

Confirmado mediante ejecución, test, build, análisis estático, herramienta o evidencia directa equivalente.

### INFERIDO DEL CÓDIGO

Conclusión razonablemente sustentada por la implementación o configuración, pero no ejecutada o comprobada dinámicamente.

### NO VERIFICABLE EN EL ENTORNO ACTUAL

No pudo comprobarse por ausencia de dependencias, credenciales, servicios, sistema operativo, infraestructura, permisos u otra limitación concreta.

Nunca inventes:

- resultados de tests;
- outputs de comandos;
- cobertura;
- benchmarks;
- vulnerabilidades;
- errores;
- archivos;
- dependencias;
- configuraciones;
- comportamiento;
- credenciales;
- servicios;
- resultados de ejecución.

Si una comprobación no pudo ejecutarse, explica exactamente por qué.

---

# 25. Ciclo autónomo de trabajo

Aplica continuamente:

**inspeccionar → comprender → detectar → priorizar → modificar → validar → corregir → revisar → volver a inspeccionar**

Después de una primera ronda:

1. revisa los resultados de las herramientas;
2. corrige los problemas detectados;
3. inspecciona nuevamente las áreas afectadas;
4. busca problemas adicionales relacionados;
5. implementa las mejoras justificadas;
6. vuelve a validar.

No finalices después de:

- una descripción inicial;
- una lista de problemas;
- unas pocas modificaciones;
- solucionar solamente los errores de compilación;
- ejecutar una sola suite de tests;
- completar solamente la primera ronda.

Si durante una corrección descubres un problema relacionado, investígalo y corrígelo también si está dentro del alcance, es seguro y puede verificarse razonablemente.

---

# 26. Criterio de convergencia

No persigas perfección teórica infinita.

Considera que el trabajo ha convergido cuando una nueva revisión razonablemente exhaustiva no revele problemas adicionales que simultáneamente:

- sean reales;
- sean relevantes;
- estén dentro del alcance;
- puedan solucionarse razonablemente;
- puedan corregirse de forma segura;
- puedan validarse con los medios disponibles.

Evita cambios especulativos una vez alcanzado ese punto.

---

# 27. Revisión final obligatoria

Antes de finalizar:

1. revisa todos los cambios realizados;
2. utiliza `git diff` o mecanismo equivalente cuando esté disponible;
3. busca errores accidentales;
4. elimina código temporal creado por ti;
5. elimina logs de debugging introducidos por ti;
6. revisa comentarios temporales;
7. revisa archivos generados accidentalmente;
8. comprueba imports;
9. comprueba configuración;
10. comprueba manifests y lockfiles;
11. vuelve a ejecutar las validaciones finales relevantes;
12. inspecciona nuevamente el estado completo del proyecto;
13. corrige cualquier problema encontrado.

No descartes modificaciones preexistentes del usuario.

---

# 28. Criterio de finalización

Finaliza únicamente cuando, dentro de las posibilidades reales del entorno:

- comprendas el propósito y arquitectura del proyecto;
- hayas inspeccionado razonablemente todo el repositorio relevante;
- hayas identificado los principales problemas técnicos;
- hayas implementado las mejoras justificadas que puedan completarse de forma segura;
- hayas corregido las regresiones introducidas durante el trabajo;
- hayas añadido o actualizado pruebas cuando aporten valor;
- hayas actualizado la documentación afectada;
- hayas ejecutado las validaciones disponibles y relevantes;
- hayas revisado los cambios finales;
- hayas realizado al menos una revisión posterior a los cambios;
- no queden problemas conocidos solucionables que estés omitiendo deliberadamente.

---

# 29. Informe final

Cuando el trabajo haya convergido, proporciona **un único informe consolidado**, conciso pero suficientemente preciso.

Incluye:

## Estado inicial

- propósito;
- arquitectura;
- estado general;
- problemas principales detectados.

## Problemas encontrados

Enumera únicamente problemas reales observados.

Para los importantes indica impacto y evidencia.

## Cambios implementados

Explica concretamente qué cambiaste y por qué.

## Archivos modificados

Identifica los archivos principales afectados y el objetivo de cada modificación.

## Bugs corregidos

Para cada bug relevante:

- problema;
- causa;
- solución;
- validación.

## Refactorizaciones

Describe únicamente las refactorizaciones relevantes y su beneficio técnico.

## Seguridad

Indica:

- problemas encontrados;
- mitigaciones implementadas;
- riesgos restantes.

## Rendimiento

Incluye solamente problemas u optimizaciones realmente confirmados.

## Arquitectura y mantenibilidad

Resume las mejoras estructurales relevantes.

## Dependencias

Indica:

- añadidas;
- eliminadas;
- actualizadas;
- motivo de cada cambio significativo.

## Testing

Indica:

- tests añadidos;
- tests modificados;
- regresiones cubiertas;
- casos límite añadidos.

## Validaciones ejecutadas

Enumera exactamente los comandos o herramientas realmente utilizados.

## Resultados

Distingue claramente:

- validaciones exitosas;
- validaciones fallidas;
- validaciones no ejecutables.

No afirmes éxito donde no exista verificación.

## Problemas restantes

Incluye únicamente problemas reales que no hayan podido resolverse y explica por qué.

## Bloqueos externos

Indica, si existen:

- qué falta;
- por qué es necesario;
- qué impide exactamente;
- qué trabajo pudo completarse pese al bloqueo.

## Riesgos y limitaciones

Describe cualquier limitación técnica relevante que permanezca.

---

# Regla final

Tu tarea no consiste en producir una auditoría teórica.

Tu tarea consiste en **comprender el repositorio, mejorarlo mediante cambios técnicamente justificados, verificar esos cambios, corregir los problemas que aparezcan y repetir el proceso hasta alcanzar el mejor estado técnico verificable que permitan el código, las herramientas y el entorno disponibles**.

Actúa autónomamente dentro de esos límites.

No solicites autorización para trabajo técnico rutinario.

No conviertas problemas solucionables en recomendaciones.

No ocultes fallos para conseguir validaciones exitosas.

No realices operaciones externas o irreversibles sin autorización explícita.

No declares como verificado aquello que no hayas podido comprobar.
























# Queda prohibido borrar o editar este archivo sin autorización expresa.

# PLAN — Corregir el texto del aviso de CLV no finito (I-1, M-1, M-3)

Segundo ciclo de prueba del flujo Opus → Codex. Cierra los tres hallazgos que
dejó abiertos la revisión del ciclo anterior (`REVIEW.md`, commit `7871bdb`).
Alcance deliberadamente pequeño: 2 archivos, capa de auditoría, **cero cambio de
comportamiento** — se toca un literal de texto y se añaden aserciones.

**No implementar nada de este documento sin encargo explícito.**

## 1. Objetivo

El aviso de CLV no finito que se acaba de committear dice esto:

> `la fila se conserva con clv_pct NaN y NO cuenta para la mediana.`

Es cierto para `median` y `mean` (pandas las salta) y **falso por omisión para
todo lo demás**, que es justo el daño:

- en `clv_segments`, `n=("clv_pct", "size")` **sí** cuenta la fila — el `n` que
  alimenta el gate de CLV queda inflado con filas que no aportan información;
- `beat_close` se guardó como `False`, porque `NaN > x` es `False`, así que la
  fila entra en `beat_close_rate` como "no batió el cierre" sin haberlo medido.

El motivo entero de emitir el aviso es que la fila **no** es inocua, y el texto
la describe como si lo fuera. Quien lea ese log para decidir si algún día se
descartan estas filas —el uso previsto, escrito en la bitácora— sacará la
conclusión contraria a la evidencia. Es un defecto de diagnóstico, no de cálculo.

De paso se cierran dos menores de la misma revisión: la prueba del lado del
cierre no fija qué aviso espera (M-1) y `inf` funciona pero no tiene prueba
(M-3).

**Objetivo:** que el aviso diga la verdad completa, y que las pruebas lo fijen.

**Fuera de alcance, a propósito:**

- **No cambiar el comportamiento.** Ni descartar filas, ni excluirlas de `n`, ni
  tocar `beat_close`. M-4 de la revisión lo deja escrito: este defecto está
  **hecho audible, no resuelto**, y resolverlo es otra decisión —con el dato
  delante— porque rompería la semántica de `n_matched`.
- **No tocar `_consensus_lines`.** El hueco de `NaN` aguas arriba (I-2) afecta al
  **pipeline vivo** y ya tiene entrada propia en `Tareas.md`. Si aparece en el
  diff, el trabajo se rechaza.
- **No tocar el guard de `price_decimal <= 1.0`.** Ítem de backlog abierto, su
  vecino natural. Mismo criterio.

## 2. Archivos a modificar

| Archivo | Cambio |
|---|---|
| `src/sqp/audit/clv.py` | 2 líneas de un literal de string en `compute_clv` |
| `tests/test_clv.py` | 2 aserciones nuevas (M-1) + 1 prueba nueva (M-3) |

Sin imports nuevos, sin firmas nuevas, sin columnas nuevas, sin constantes de
configuración. Sin tocar `risk/`, `backtesting/`, `models/` ni `pipeline/`.

## 3. Cambios exactos

### 3.1 `src/sqp/audit/clv.py` — el texto del aviso

Estado actual (líneas 92-98):

```python
        if not math.isfinite(clv_pct):
            log.warning(
                "CLV no finito en %s %s/%s (evento %s): entrada %r vs cierre "
                "%r. Precio ausente o corrupto en el origen; la fila se "
                "conserva con clv_pct NaN y NO cuenta para la mediana.",
                r.league, r.market, r.selection, str(r.event_id),
                entry, float(close))
```

Queda:

```python
        if not math.isfinite(clv_pct):
            log.warning(
                "CLV no finito en %s %s/%s (evento %s): entrada %r vs cierre "
                "%r. Precio ausente o corrupto en el origen; la fila se "
                "conserva con clv_pct NaN: NO entra en la mediana, pero SI "
                "cuenta en n y en beat_close_rate.",
                r.league, r.market, r.selection, str(r.event_id),
                entry, float(close))
```

Cambian **exactamente dos líneas** del literal. Todo lo demás —la condición, el
`elif`, los `%r`, el orden de los argumentos, el formato perezoso— se queda
igual. La línea más larga queda en 75 columnas, dentro del límite.

Detalles que no son negociables:

1. **`SI` sin tilde, a propósito.** `clv.py` evita no-ASCII deliberadamente
   (`antiguedad`, `salio`, `diagnostico`). Un `Í` aquí volvería a romper la
   comprobación de §5. Ver §3.3.
2. **`no finito` sigue al principio del mensaje**, sin cambios: la prueba
   existente `test_compute_clv_warns_when_entry_price_is_not_finite` afirma
   `"no finito" in getMessage()` y **no se toca**.
3. El mensaje sigue siendo una sola llamada a `log.warning` con formato
   perezoso. Nada de f-strings.

### 3.2 Nada más en `clv.py`

Ni el docstring, ni `beat_close`, ni el comentario de las líneas 115-117 (que ya
explica por qué el empate no cuenta como "batir"). El comportamiento observable
del módulo es idéntico antes y después: mismos valores, mismas filas, mismas
columnas, mismo número de avisos. Sólo cambia el texto de uno de ellos.

### 3.3 Sólo ASCII en el código

Ya pasó dos veces en este módulo: un carácter acentuado y un **U+2212** que
llegó a romper una lectura de archivo con la codificación por defecto de la
consola Windows. El bloque de §3.1 está en ASCII puro: **cópialo literalmente**.
Este documento lleva acentos en la prosa; el código no.

## 4. Pruebas necesarias

En `tests/test_clv.py`, reutilizando los helpers existentes `_write_odds`,
`_odds_row`, `_write_settled`, `_settled_row` y `_clv_warnings`.

### P1 — cerrar M-1: la prueba del cierre no finito debe fijar QUÉ espera

`test_compute_clv_warns_when_closing_price_is_not_finite` hoy sólo afirma
`len(_clv_warnings(caplog)) == 1`. No está vacía —si se borra la rama salen 0
avisos y cae—, pero es **asimétrica con la prueba de la entrada**: no comprueba
el mensaje ni de qué lado vino el `NaN`. Añadir dos líneas al final:

```python
    assert "no finito" in _clv_warnings(caplog)[0].getMessage()
    assert pd.isna(df.iloc[0]["close"])
```

La segunda es la que aporta: fija que el `NaN` llegó por el **lado del cierre**,
que es lo único que esta prueba añade sobre la de la entrada. Es una **adición**;
las aserciones que ya están no se tocan.

### P2 — cerrar M-3: `inf` dispara la misma rama

`math.isfinite` trata `inf` igual que `NaN`, y un CSV con la cadena `inf` lo
produce (`read_csv` lo parsea como float infinito), pero ninguna prueba lo
ejercita.

```python
def test_compute_clv_warns_when_entry_price_is_infinite(tmp_path, caplog):
    _write_odds(tmp_path, [_odds_row(price_decimal=1.90)])
    _write_settled(tmp_path, [_settled_row(price_decimal=float("inf"))])
    caplog.set_level(logging.WARNING, logger="sqp.clv")

    df, unmatched = compute_clv(tmp_path / "data" / "bets", tmp_path)

    warnings = _clv_warnings(caplog)
    assert len(warnings) == 1
    assert "no finito" in warnings[0].getMessage()
    assert len(df) == 1 and unmatched == 0
```

**Tiene que ser la ENTRADA, no el cierre.** Comprobado antes de escribir el
plan: con el cierre en `inf`, `clv_pct = entry / inf - 1.0 = -1.0`, que **sí es
finito** — esa rama no se activa y salta la de implausibilidad
(`abs(-1.0) >= 0.25`). Un cierre infinito produce un CLV finito y silenciosamente
falso de `-100%`. Es una rareza que hoy avisa por el otro camino; **no** es
motivo para tocar código en este ciclo, pero anótalo en el reporte de entrega si
lo verificas.

### P3 — nadie afirma sobre el texto viejo

Antes de tocar nada, comprobar que ninguna prueba existente afirme sobre la
frase que se elimina:

```powershell
Select-String -Path tests/ -Pattern "cuenta para la mediana" -Recurse
```

Debe salir **vacío**. Si sale algo, esa prueba entra en el alcance y hay que
actualizarla; si no sale nada (lo esperado), **ninguna prueba preexistente se
toca**. Verificarlo explícitamente y decirlo en la entrega.

### P4 — orden de trabajo

Escribir P2 **antes** del cambio de texto y verla pasar en verde ya (la rama
existe; sólo faltaba la prueba). Después el cambio de §3.1, después las
aserciones de P1. Así queda claro qué prueba cubre qué.

## 5. Comandos de validación

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_clv.py -q     # 18 passed
$env:PYTHONPATH="src"; python -m pytest tests/ -q                # 637 passed
ruff check src/sqp/audit/clv.py tests/test_clv.py                # limpio
mypy src                                                         # 89 archivos
```

Línea base tras `7871bdb`, **verificada, no estimada**: **636 passed** en total y
**17** en `tests/test_clv.py`. Se añade 1 prueba (P2); las dos aserciones de P1
no crean pruebas. Por tanto el total esperado es **exactamente 637** y
**exactamente 18** en `test_clv.py`. Cualquier otro número significa que se rompió
algo o que se añadieron pruebas fuera del plan: parar y reportar, no ajustar el
número.

> El ciclo anterior falló justo aquí: el plan declaró un rango de conteos mal
> calculado (M-2 de `REVIEW.md`) y el criterio de aceptación habría marcado un
> falso fallo. Estos dos números salen de una corrida real de hace minutos.

No-regresión sobre datos reales (el módulo alimenta el gate de CLV):

```powershell
$env:PYTHONPATH="src"; python scripts/clv_analysis.py
```

El reporte `data/bets/clv_20260805.md` debe salir **idéntico byte a byte** al
actual, y con **0 avisos de CLV no finito** y **2 de implausibilidad** — es la
corrida que se hizo al cerrar el ciclo anterior. Este cambio no puede mover
ninguna cifra: sólo reescribe un literal de texto. Si alguna cambia, hay un
defecto. Respaldar el reporte antes de ejecutar:

```powershell
Copy-Item data/bets/clv_20260805.md $env:TEMP/clv_baseline.md
```

Verificación ASCII antes de committear:

```powershell
Select-String -Path src/sqp/audit/clv.py -Pattern '[^\x00-\x7F]' | Select-Object LineNumber
```

Sólo deben aparecer las líneas **9, 38 y 39** (guiones largos preexistentes del
docstring y del comentario de `CLOSE_MAX_AGE_MIN`). El conteo de líneas no se
desplaza: este cambio no añade ni quita líneas en `clv.py`. Cualquier otra línea
en esa lista es un carácter que se coló.

## 6. Riesgos

| Riesgo | Nivel | Mitigación |
|---|---|---|
| Que el cambio de texto rompa una prueba que afirme sobre él | Bajo | P3 lo comprueba **antes** de tocar nada. La única prueba que afirma sobre el mensaje usa `"no finito"`, que se conserva intacto. |
| Volver a introducir no-ASCII (el `SI` sin tilde invita a "corregirlo") | **Medio — ya ocurrió dos veces** | Bloque de §3.1 en ASCII puro + comprobación de §5 antes del commit. Si algo pide poner `SÍ`, la respuesta es no. |
| Ampliación de alcance hacia el arreglo real (excluir la fila de `n`) | Medio | El objetivo es que el log **describa** el defecto, no que lo corrija. Cambiar `n` o `beat_close` mueve las cifras del gate de CLV, que gobierna la salida del shadow mode. Si aparece en el diff, se rechaza. |
| Ampliación hacia `_consensus_lines` (I-2) o `price_decimal <= 1.0` | Medio | Ambos tocan el **pipeline vivo** y tienen entrada propia en `Tareas.md`. Mismo criterio: fuera. |
| Que el mensaje nuevo también sea impreciso | Bajo | Las dos afirmaciones están **verificadas empíricamente** en `REVIEW.md`: `median`/`mean` saltan el `NaN`; `n=("clv_pct","size")` lo cuenta; `beat_close` quedó en `False`. No es una deducción, es una tabla de resultados. |
| Ruido en el log del run diario | Nulo | El número de avisos no cambia: hoy son 0 de esta clase. Sólo cambiaría el texto si alguno disparase. |

## Criterio de aceptación

1. Exactamente 2 archivos modificados: 2 líneas en `clv.py`, +2 aserciones y +1
   prueba en `test_clv.py`.
2. `pytest`: **637** en total y **18** en `tests/test_clv.py`. `ruff` y `mypy`
   limpios.
3. `scripts/clv_analysis.py` produce un reporte idéntico byte a byte.
4. Sin caracteres no-ASCII nuevos en `clv.py` (líneas 9, 38, 39 y ninguna más).
5. Ninguna prueba preexistente modificada — sólo adiciones.
6. Cero cambios de comportamiento: mismos valores, mismas filas, mismas
   columnas, mismo número de avisos.









