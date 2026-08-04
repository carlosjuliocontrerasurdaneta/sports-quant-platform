# Project Decisions

Record decisions here.

Format:
- Date:
- Decision:
- Reason:
- Alternatives:
- Consequences:

- Date: 2026-06-12
- Decision: Reestructurar .claude/ a esquema válido de Claude Code.
- Reason: settings.json usaba claves no soportadas; hooks no registrados; agentes sin frontmatter; skill sports-analytical-system empaquetado como .skill no descubrible; rutas absolutas rotas en settings.local.json tras mover el proyecto.
- Alternatives: Mantener estructura decorativa (rechazado: nada se ejecutaba).
- Consequences: Hooks activos (format, secrets, tests), permisos deny para data/, agentes invocables como subagentes, skill analítico cargable. settings.local.json se regenerará al aprobar comandos.

- Date: 2026-06-12
- Decision: En modo live, verificar `active` del sport_key vía /sports de The Odds API antes de pedir scores/odds; si está inactivo o el key no existe, omitir el fetch con log explícito y devolver salida vacía.
- Reason: Liga MX (y la mayoría de ligas europeas) fuera de temporada producían DataFrames vacíos en silencio, indistinguibles de un fallo de proveedor; un key con typo causaba 404 sin contexto.
- Alternatives: No chequear y documentar el comportamiento (rechazado: ambigüedad operativa); fallar con excepción si inactivo (rechazado: pararía el run multi-deporte diario).
- Consequences: /sports no consume cuota y se cachea por cliente; el chequeo es best-effort (si falla, el flujo normal continúa). Logs distinguen "fuera de temporada" (WARNING) de "key inválido" (ERROR).

- Date: 2026-06-12
- Decision: Usar el scoreboard público de ESPN (site.api.espn.com) como vendor de resultados históricos para todas las ligas salvo MLB (que sigue en MLB Stats API), con store local CSV append-only por liga en data/historical/ y dedup por (date, home, away) donde la fila existente siempre gana.
- Reason: The Odds API /scores solo cubre 3 días; ESPN es gratuito, sin key, cubre las 17 ligas mapeadas y los nombres coinciden con The Odds API en NBA/WNBA (verificado).
- Alternatives: Vendor de pago con SLA (rechazado por ahora: costo); ampliar daysFrom de The Odds API (imposible: cap de 3); scraping (rechazado: fragilidad y ToS).
- Consequences: Endpoint no oficial — el esquema puede cambiar sin aviso; el script de backfill reporta conteos por liga para detectar roturas. Riesgo de mismatch de nombres en soccer (KI-002). Raw data preservada: re-ingestas nunca mutan filas.

- Date: 2026-06-12
- Decision: Crear RUN_DIARIO.bat en la raíz de ESTE repo (backfill incremental 10 días no bloqueante + pipeline live, ligas en variable LEAGUES) en lugar de modificar el RUN_DIARIO.bat de Proyectos\38.
- Reason: El de Proyectos\38 pertenece a otra plataforma (estructura .venv/bat_scripts/picks_report.py inexistente aquí); este repo no tenía ningún .bat pese a que CLAUDE.md lo referencia.
- Alternatives: Editar el de Proyectos\38 (rechazado: codebase distinto); encadenar ambos proyectos (rechazado: acoplamiento sin confirmar relación).
- Consequences: CLAUDE.md y realidad ya coinciden. Un fallo de backfill solo avisa y el pipeline continúa con el histórico almacenado. Pendiente aclarar si Proyectos\38 es versión vieja de esta plataforma.

- Date: 2026-06-12
- Decision: En ligas 3-way, el backtest evalúa P(local | no empate) contra outcomes sin empates y reporta la calibración del empate por separado (en vez de la probabilidad incondicional contra frecuencias sin empates).
- Reason: La versión anterior inflaba mecánicamente el ECE (Liga MX 0.162 → 0.057 tras el fix con los mismos datos); comparar probabilidad incondicional contra frecuencias condicionales es metodológicamente inválido.
- Alternatives: Brier multiclase 3-way (válido, pospuesto: pierde comparabilidad directa con las ligas 2-way en el mismo reporte).
- Consequences: Métricas binarias comparables entre familias; el empate tiene su propia métrica (y destapó KI-004).

- Date: 2026-06-12
- Decision: Overrides de rating por liga viven en configs/leagues/ratings.yaml (generado por scripts/tune_ratings.py --write, grid search walk-forward por log loss) y se fusionan en _league_meta para cualquier deporte.
- Reason: La ventaja local varía fuertemente por liga (WNBA 30 vs NBA 75 Elo); el default único por familia penalizaba la calibración. Config, no código, igual que las ligas soccer.
- Alternatives: Hardcodear en LEAGUE_OVERRIDES del registry (rechazado: requiere tocar código por liga); estimar online dentro del Elo (rechazado por ahora: más complejidad, menos auditable).
- Consequences: Borrar el YAML restaura los defaults de familia (rollback trivial). Valores in-sample: re-tunear tras cambios de temporada y re-validar con partidos nuevos antes de confiar.

- Date: 2026-06-12
- Decision: Dixon-Coles entra como parámetro de configuración por liga (dc_rho en ratings.yaml, default 0.0 = apagado), tuneado por grid search walk-forward scored por log loss 3-way (1X2), no por la métrica binaria condicional.
- Reason: KI-004 — el Poisson independiente subestimaba el empate en Liga MX; la métrica binaria condicional es insensible a la masa del empate, así que tunear rho requería la multiclase.
- Alternatives: Estimar rho por máxima verosimilitud sobre marcadores exactos (más fiel al paper, pospuesto: requiere modelar tasas por equipo, hoy las λ derivan del Elo); aplicar rho global a todo soccer (rechazado: ligas con distinta tasa de empate).
- Consequences: dc_rho=0 es no-op exacto (hockey/béisbol no afectados); quitar la clave del YAML apaga el ajuste sin tocar código. El run diario consume dc_rho automáticamente vía _league_meta.

- Date: 2026-06-12
- Decision: Solo registrar slugs de ESPN verificados empíricamente (request real con eventos) o confirmados contra su catálogo de ligas; las ligas sin vendor verificable (Frauen-Bundesliga) quedan sin registrar y documentadas como issue, nunca con un slug adivinado.
- Reason: Reglas de veracidad del proyecto (no inventar disponibilidad de proveedores); un slug inválido falla silencioso (404→vacío tras el fix) y se confundiría con "liga sin partidos".
- Alternatives: Registrar candidatos plausibles y esperar a que fallen (rechazado: indistinguible de fuera-de-temporada).
- Consequences: chile y uwcl registrados con evidencia; frauen_bundesliga → KI-005 (vendor alternativo pendiente).

- Date: 2026-06-12
- Decision: No persistir parámetros tuneados (ratings.yaml) para ligas con muestra evaluable insuficiente tras warmup (caso UWCL: 15 partidos); esas ligas operan con defaults de familia hasta acumular histórico. Además, nunca correr dos tune_ratings --write concurrentes (read-modify-write sobre el mismo YAML).
- Reason: Un parámetro estimado sobre ~15 partidos es ruido con apariencia de calibración (modeling-rules: baselines y muestras adecuadas); la escritura concurrente puede pisar entradas de otras ligas.
- Alternatives: Bajar warmup para ligas chicas (rechazado: ratings sin asentar contaminan la evaluación); lock de archivo (innecesario: secuenciar basta a esta escala).
- Consequences: UWCL sin override hasta nueva temporada; el tuning de WNCAAB espera al batch.

- Date: 2026-06-12
- Decision: El store de resultados identifica juegos con game_id del vendor (gamePk statsapi, id ESPN) en la clave de dedup; entre fuentes distintas (histórico vs scores de The Odds API) el merge decide por (día, home, away) con el histórico ganando, porque los ids no son comparables entre vendors.
- Reason: La clave (date, home, away) colapsaba doubleheaders (21 juegos MLB reales perdidos en 365 días); pero usar game_id entre fuentes habría contado dos veces el mismo juego en el solape de 3 días del pipeline.
- Alternatives: Clave con marcador incluido (rechazado: doubleheaders pueden repetir marcador); migración in-place de CSVs legacy (rechazado: imposible obtener ids sin re-fetch — se regeneraron los 19 stores desde fuente, que es gratuita y reproducible).
- Consequences: Esquema v2 con columna game_id; migración automática de CSVs legacy (id vacío); doubleheaders preservados (verificado: MLB 2,439 = 2,418 + 21 exacto).

- Date: 2026-06-12
- Decision: El provider de MLB exige campo score presente y excluye detailedState Postponed/Cancelled/Suspended; prohibido rellenar scores ausentes con defaults.
- Reason: statsapi marca pospuestos como abstractGameState=Final sin scores; el default `.get("score", 0)` fabricó 24 empates 0-0 que contaminaron Elo y backtest (audit 2026-06-12).
- Alternatives: Filtrar solo 0-0 aguas abajo (rechazado: trata el síntoma; un juego suspendido con marcador parcial pasaría igual).
- Consequences: Dato faltante = fila excluida, nunca inventada (regla de veracidad aplicada al parsing).

- Date: 2026-06-12
- Decision: La expansión de grillas de tuning se detiene cuando la curva de log loss se aplana y la muestra subyacente es chica, aunque el óptimo quede técnicamente en frontera (caso Chile dc_rho +0.35 con ~30 empates observados y tasa atípica vs histórico de la liga).
- Reason: Perseguir el mínimo in-sample en muestras chicas ajusta ruido con apariencia de calibración (multiple testing sobre el mismo histórico).
- Alternatives: Extender hasta el límite teórico del tau (~0.5) (rechazado: la mejora marginal era 0.001 de log loss); no persistir el valor de frontera (considerado: se persistió porque el gap del empate quedó cerrado, con flag de re-validación obligatoria).
- Consequences: UCL (+0.30) y Chile (+0.35) marcados para re-validación out-of-sample con la temporada nueva antes de operar.

- Date: 2026-06-12
- Decision: El feature de abridor MLB v1 (carreras permitidas por apertura) queda APAGADO (pitcher_bound 0.0 en ratings.yaml) tras rechazo empírico; la infraestructura (Event.pitchers, observe(), StartersStore, flag "Starter unknown") se mantiene activa para la v2 con FIP por apertura.
- Reason: Grid walk-forward 4x4: cualquier peso del factor empeora el log loss monotónicamente — la señal RA mezcla bullpen y ofensa rival y duplica al Elo. El fix real de MLB era tilt_scale 0.8→0.4 (sobreconfianza), que llevó a Brier 0.2474 < baseline 0.2491.
- Alternatives: Mantener el factor con bound chico (rechazado: 0.10 también empeora); esperar a FIP antes de mergear infraestructura (rechazado: el flag de abridor desconocido y la captura de probables ya aportan en producción).
- Consequences: MLB estima con Poisson tilt 0.4 sin ajuste de pitcher; juegos sin abridor anunciado no generan candidatos; v2 FIP = cambiar la fuente del rating, no la tubería.

- Date: 2026-06-12
- Decision: Plan de odds históricas en 3 bloques por costo/valor: A) captura propia diaria (forward, gratis) con reducción a 1 región por cuota; B) histórico soccer de football-data.co.uk (gratis, cierre Pinnacle, multi-temporada); C) histórico US majors pospuesto hasta que B demuestre edge (no pagar por validar ligas que no baten ni el baseline).
- Reason: Verificado con requests reales: The Odds API histórico requiere plan de pago (401 en el actual); football-data.co.uk responde gratis con cierre de Pinnacle incluso para Liga MX. Cuota gratuita (500/mes) no soporta us,eu diario (~540/mes).
- Alternatives: Pagar The Odds API ya (rechazado: primero demostrar edge barato en soccer); scraping de archivos US (pendiente verificación de calidad, bloque C).
- Consequences: Cada día de operación genera dataset out-of-sample propio; el ROI realizado multi-temporada llega primero para soccer.

- Date: 2026-06-15
- Decision: El cap de exposición diaria (`max_daily_exposure_pct`) se hace cumplir escalando PROPORCIONALMENTE todos los stakes positivos del día para que su suma no supere `bankroll*cap_pct`; las filas de stake 0 (paused / edge implausible) se excluyen y no se tocan; los recortados se marcan `daily_exposure_scaled`.
- Reason: El parámetro estaba en config pero nunca se aplicaba (KI-008); el cap por apuesta no controla la exposición agregada del día. El escalado proporcional es neutral respecto a la selección de picks.
- Alternatives: Priorizar por edge y cortar los de menor edge (rechazado por ahora: cambia la política de selección, decisión aparte); exponer el parámetro por env-var (rechazado: se dejó solo YAML).
- Consequences: Ningún día compromete más del cap; el flag deja rastro auditable; `_finalize` cuenta accionables por `stake>0` (un escalado sigue siendo accionable).

- Date: 2026-06-15
- Decision: El emparejamiento de probable pitchers a eventos live aplica el normalizador de nombres del adaptador a ambos lados de la clave `(home, away)`, igual que `_merge_results`.
- Reason: Eventos (The Odds API) y pitchers (MLB Stats API) usan grafías distintas; el match por nombre crudo fallaba en silencio y dejaba MLB sin candidatos (KI-009).
- Alternatives: Mantener match crudo y confiar en que los nombres MLB coinciden (rechazado: falla con reubicaciones como Athletics y cualquier divergencia de vendor).
- Consequences: Cierra un contribuyente de KI-006; no resuelve la población de StarterRatings (H4, abierto).

- Date: 2026-06-15
- Decision: Repuntar `origin` a la URL canónica `sports-quant-platform.git` (sin `-elo`) tras verificar con `git ls-remote` que el repo `-elo` fue renombrado a ese nombre y es el mismo (misma historia git).
- Reason: GitHub redirige la URL vieja con "This repository moved"; depender del redirect es frágil. La memoria advertía de un repo homónimo DISTINTO, por eso se verificó la identidad antes de repuntar (remote main = f6b5919 commit nuestro; rama remota = HEAD local).
- Alternatives: Dejar el origin viejo y confiar en el redirect (rechazado: frágil); repuntar sin verificar (rechazado: riesgo de pushear al repo equivocado advertido en memoria).
- Consequences: push/fetch directos sin redirect; memoria git-remote-elo actualizada; si reaparece un repo homónimo distinto, vuelve la trampa.

- Date: 2026-06-16
- Decision: Vertical de tenis v1: league id = clave de torneo de The Odds API; Elo de jugador TOUR-WIDE (atp/wta) ajustado con resultados ESPN; SOLO singles y moneyline; liquidacion por nombre de jugador normalizado + fecha (sin event_id comun entre proveedores), reutilizando settle_candidates con marcadores sinteticos 1-0.
- Reason: The Odds API no da scores de tenis y sus claves son por torneo; el rating en tenis es por jugador y tour-wide, no por torneo. ESPN (gratis, no oficial) si da resultados. Cerrar el hueco de auditabilidad sin sobre-construir (handicap/total de games = fase posterior).
- Alternatives: league id = tour (atp/wta) con fetch multi-torneo (rechazado: rompe el supuesto 1 liga = 1 sport_key del pipeline); pagar un proveedor de datos de tenis (rechazado: ESPN cubre singles gratis).
- Consequences: el tenis genera picks y se audita end-to-end; depende del orden settle(09:00)->run(10:00) para recuperar jugadores/fecha de predictions_<liga>.csv; ESPN no oficial => parser defensivo + tests + vigilar log. No habilita operar (falta cierre real/OOS).

- Date: 2026-06-16
- Decision: Construir la infraestructura v2 de abridor (FIP por apertura) pero dejarla APAGADA (pitcher_signal="ra" por defecto, mlb.pitcher_bound 0.0) tras validacion walk-forward: FIP solo empata al baseline (mejor ganancia −0.0007 log-loss en bound 0.05, por debajo del margen de aceptacion 0.002; ECE empeora).
- Reason: Misma disciplina que rechazo v1: no activar una senal que no bate al baseline por un margen aceptable; perseguir el bound 0.05 seria overfitting sobre senal fina. FIP es menos malo que RA pero el Elo de equipo + tilt ya captura la mayor parte.
- Alternatives: Activar bound 0.05 (rechazado: ganancia despreciable y peor calibracion); descartar el codigo v2 (rechazado: infra + 2.438 starts backfilleados sirven para un v3 mejor especificado sin re-fetch).
- Consequences: Produccion sin cambios; pitcher_signal="fip" disponible para experimentar; resultado negativo documentado (KI-006). v3 posible: FIP con ajuste por oponente, ponderacion por recencia o senal de matchup.

- Date: 2026-06-21
- Decision: La persistencia de liquidaciones (`_persist_settled`) reconcilia esquemas tomando la UNIÓN de columnas (orden del archivo previo + campos nuevos) y reescribiendo el `settled_<liga>.csv` completo alineado, en vez de apendar con `mode="a"`. Auto-sana archivos escritos por un esquema anterior.
- Reason: El esquema de `BetCandidate` evoluciona (se añadió `calibrated_probability`); un append a ciegas escribía el orden nuevo bajo el header viejo y desalineaba cada valor al releer, corrompiendo la auditoría de ROI y los inputs de calibración (KI-011). El dedup ya leía el archivo previo completo, así que reescribir no añade costo de I/O relevante.
- Alternatives: Reindexar las filas nuevas al header viejo (rechazado: descartaría silenciosamente las columnas nuevas como calibrated_probability); migración one-off de los CSV viejos (rechazado: la reescritura por unión ya los auto-sana en la próxima liquidación que los toque).
- Consequences: settled_*.csv siempre alineados y con superconjunto de columnas; mantiene idempotencia del dedup; cubierto por tests/test_settle_persist.py.

- Date: 2026-06-21
- Decision: Ante un fallo de pipeline de una liga en `run_all.py`, se llama `_finalize(lg, [], [], mode)` en el `except` para archivar y limpiar los picks de esa liga, en vez de dejar el `candidates_<liga>.csv` del día anterior intacto.
- Reason: Un fallo transitorio dejaba picks viejos que el reporte mostraba como del día (presentación engañosa). `_finalize` ya archiva en archive/ antes de limpiar, así que los picks sin liquidar quedan recuperables; respeta el orden documentado settle(09:00)->run(10:00).
- Alternatives: Dejar el archivo intacto (rechazado: el reporte muestra picks viejos como del día); marcar la liga como "fetch failed" sin limpiar (rechazado: más complejo y el archivo seguiría mostrándose en el reporte).
- Consequences: tras un fallo, la liga no aparece con picks del día anterior; un fallo no transitorio podría reescribir a vacío repetidamente (inofensivo). Sin test dedicado nuevo (cambio de robustez).

- Date: 2026-06-21
- Decision: CI en GitHub Actions (`ruff check src tests` + `pytest -q`, Python 3.11+3.12) y config de ruff en pyproject que IGNORA E701/E702 (one-liners `if: return` y `;` deliberados, p. ej. settle._grade y fixtures), conservando el resto del set default + pyflakes.
- Reason: 173 tests sin nada que los corra automáticamente en Windows+Task Scheduler. El config de ruff se perdió en la re-importación; los 21 "errores" eran 19 de estilo intencional + 2 reales (corregidos).
- Alternatives: Reescribir los one-liners para cumplir E701/E702 (rechazado: cambia código de negocio por estilo que el proyecto eligió); CI en windows-latest (rechazado por ahora: el código es cross-platform, ubuntu es más rápido/barato; conmutable si hace falta).
- Consequences: regresiones detectadas en push/PR cuando haya remoto; hasta entonces `make lint`/`make test` localmente.

- Date: 2026-06-21
- Decision: Portar del proyecto 2 (`_archive/2`) SOLO la penalización de EV por desacuerdo modelo-mercado (no el ensemble ni el techo 0.075) y ACTIVARLA tras validación OOS. El penalty (`gap*0.35` +anomalía +pocos books) se pliega en una probabilidad efectiva `p_eff=p-penalty/d` que alimenta edge y Kelly, así recorta también el stake. `estimated_edge` se mantiene RAW.
- Reason: edges irreales por sobreconfianza (KI-012). El diagnóstico mostró que anclar más al mercado + penalizar el desacuerdo es la dirección correcta. La activación se gateó por evidencia: walk-forward sobre odds capturadas (1654 apuestas) ROI −0.74%→+0.37% y exposición ~a la mitad (MLB y WNBA mejoran). El retrospectivo de 93 apuestas NO bastaba (sesgo de selección).
- Alternatives: Subir market_shrink plano (rechazado: no escala con el desacuerdo); portar también el blend 60% mercado y el techo 0.075 (pospuesto: un cambio a la vez, el techo necesita su propia prueba); dejar la penalización OFF (rechazado: la evidencia OOS la respalda).
- Consequences: menos apuestas y mitad de exposición en producción; sigue ≈ break-even e in-sample en parámetros (no es claim de rentabilidad). Coeficientes a 0 = desactivar. Nuevos campos de auditoría en BetCandidate (adjusted_edge/edge_penalty/books_count).

- Date: 2026-06-21
- Decision: El bankroll para staking se deriva de un ledger (inicial + PnL realizado de settled_*.csv con data_label=="real" + ajustes manuales), NO de un store de transacciones paralelo. Gated por flag `bankroll_dynamic` (default OFF); solo el entrypoint live lo inyecta.
- Reason: el bankroll estático ignoraba el PnL realizado (KI-013). settled_*.csv ya es fuente de verdad deduplicada; un ledger paralelo arriesga doble conteo. Mantener el flag OFF y la inyección solo en run_all evita acoplar los tests (que llaman run_league directo) al contenido de data/bets.
- Alternatives: Ledger de transacciones completo (rechazado: redundante con settled_*.csv); mutar Settings.bankroll en load() leyendo el ledger (rechazado: haría los tests no deterministas); restar stakes pendientes del balance disponible (pospuesto a v2: con el ciclo SETTLE→RUN no hay apuestas del día colocadas al dimensionar).
- Consequences: staking fiel a la banca real cuando se active; balance auditado por scripts/bankroll_status.py (937.28 actual); demo nunca toca la banca real; pendiente activar en producción.

- Date: 2026-06-22
- Decision: Habilitar el OOS de tenis persistiendo resultados ESPN TOUR-WIDE bajo la clave de tour (results_atp.csv / results_wta.csv), no por torneo, y emparejando order-insensible (frozenset de jugadores normalizados) SOLO para family=="tennis"; los deportes de equipo mantienen el emparejamiento ordenado (la ventaja local distingue los dos juegos de una serie). validate_oos omite el freezing de parámetros para tenis (Elo neutral).
- Reason: el tenis daba 0 OOS por dos bloqueos: sin resultados en ResultsStore y matching ordenado mientras el tenis no tiene home/away. El Elo de tenis es por jugador y tour-wide; las odds son por torneo. La reorientación de marcadores del backtest ya existía, así que solo faltaba el matching simétrico + la fuente de resultados.
- Alternatives: persistir resultados por torneo (rechazado: el Elo es tour-wide, duplicaría datos); usar frozenset para todos los deportes (rechazado: conflaría local vs visitante en deportes de equipo); fetch de resultados de tenis dentro del backtest (rechazado: el backfill persistido es reutilizable y auditable).
- Consequences: el OOS de tenis corre (Halle/Queen's/German Open emparejan; Wimbledon 0 por calendario; Bad Homburg 0 → KI-014). ROI = ruido a 3-9 apuestas/torneo (capacidad, no señal). NFL OOS sigue bloqueado por calendario, no por datos.

- Date: 2026-06-22
- Decision: El reporte HTML diario gana interactividad client-side replicando el proyecto 2: pills toggleables por deporte (multi-select) en Picks reemplazando el dropdown; orden por columna genérico en todas las tablas server-rendered (Auditoría/Patrones, incl. hit_rate); y filtros por deporte/mercado/rango-de-fecha en Historial. Sin assets externos (sigue autónomo).
- Reason: pedido del usuario para filtrar/ordenar como en `_archive/2/data/output/picks_report_all.html`, pero para todos los deportes. Las tablas de Auditoría/Patrones/Historial eran HTML estático; se añadió JS genérico en vez de re-renderizar server-side.
- Alternatives: mantener el dropdown y añadir botones (rechazado: redundante, filtran el mismo campo); re-render server-side por filtro (rechazado: el reporte es un archivo estático, mejor client-side); embeber el historial como JSON y renderizar client-side como los picks (pospuesto: filtrar filas con data-* es más simple y suficiente).
- Consequences: Picks filtra por pills + stats reactivos; tablas ordenables asc/desc (numeric-aware); Historial filtrable por 3 ejes con contador; initSortable/initHistory corren aunque no haya picks.

- Date: 2026-06-22
- Decision: Bajar `max_plausible_edge` de 0.15 a 0.075 (techo del proyecto 2) en configs/default.yaml. El default del dataclass se mantiene en 0.15 (no romper el test pinned ni cambiar el comportamiento de RiskConfig() directo).
- Reason: validación OOS sobre odds capturadas con la penalización de EV activa: MLB (n=1174→652) ROI test +0.41%→+2.42% con profit +19→+51 y mitad de exposición; agregado +0.24%→+0.71%, exposición ~a la mitad. Marca los edges crudos sobreconfiados (>7.5%) que no se realizan. Reduce riesgo sin sacrificar ROI (en MLB lo mejora).
- Alternatives: dejar 0.15 (rechazado: la evidencia OOS favorece 0.075); bajar también el default del dataclass (rechazado: rompería test_risk_config_has_plausibility_cap_default y acoplaría tests); bajar más agresivo (no probado).
- Consequences: producción apuesta menos y con mitad de exposición; WNBA empeora en muestra chica (n=62, ruido); sigue ≈ break-even sobre proxy de cierre de un snapshot → control de riesgo, no rentabilidad. Reversible (una línea en YAML). Cierra el pendiente del techo 0.075.

- Date: 2026-06-22
- Decision: Primera señal específica por deporte: factor de PARQUE para MLB sobre el TOTAL (sqp.models.park.ParkFactors), estimado como carreras de local vs de visita del equipo local (aísla el parque del nivel ofensivo), escalando ambas lambdas. Activado `mlb.park_bound: 0.10` en ratings.yaml y mlb/totals DES-PAUSADO en default.yaml (van juntos: con totals pausado el factor no tiene efecto live).
- Reason: MLB totals era el mercado débil (OOS −17.1%, por eso estaba pausado). El park factor lo da vuelta OOS a +2.8% (held-out −15.9%→+3.8%/+7.0%) y sube MLB global +2.4%→+7.8%; generaliza en ambas mitades y ambos bounds (0.10/0.20). Es la primera señal por deporte que bate al baseline (el abridor solo empataba, KI-006). 0.10 sobre 0.20 por menos sobre-corrección.
- Alternatives: rest/B2B basketball (pospuesto: solo WNBA tiene OOS, n=170 ruido) o portero NHL (pospuesto: 0 cobertura OOS + alto riesgo de rechazo como el abridor); park factor vía liga-promedio en vez de home-vs-away (rechazado: confunde el parque con el nivel del equipo); dejar park ON pero totals pausado (rechazado: el factor solo afecta totals, no tendría efecto). park_bound default 0.0 (no-op) para envío seguro, activado solo tras validar OOS.
- Consequences: producción apuesta totals de MLB con ajuste de parque; re-pausar si el ROI realizado de totals vuelve a negativo. Una temporada / proxy de cierre de un snapshot / sin IC → no es rentabilidad demostrada. Infra ParkFactors reutilizable para otras ligas si se valida.

- Date: 2026-06-22
- Decision: Construir la señal de rest/back-to-back para basketball (sqp.models.rest.RestModel, ajuste al margen del local por descanso diferencial) pero dejarla APAGADA (rest_points_per_day 0.0, no-op) tras validación OOS NEGATIVA. No se activa en ninguna liga.
- Reason: apuntaba al mercado débil restante (WNBA spreads OOS −11.3%). En la ventana completa lucía fuerte (spreads −6%→+18%) pero NO generaliza: en el held-out el mejor valor de ALL (1.0) empeora spreads (−38%→−48%), es no-monótono en el parámetro, y las muestras son minúsculas (22-25 ALL, 7-10 held-out). Misma disciplina que rechazó el abridor MLB: no activar una señal que no bate al baseline fuera de muestra.
- Alternatives: activar rppd=2.0 (rechazado: el único que ayuda en held-out, pero inconsistente con ALL y sobre n=10 = ruido); descartar el código (rechazado: infra reutilizable, ships OFF, se re-valida cuando NBA/WNBA acumulen odds); probar en NBA (pospuesto: NBA tiene ~1 evento de odds capturado, 0 cobertura OOS).
- Consequences: producción sin cambios (no-op); RestModel disponible para experimentar y re-validar; resultado negativo documentado. Confirma que HOY solo MLB tiene muestra OOS confiable para validar señales.

- Date: 2026-06-22
- Decision: Romper el cuello de botella de cobertura OOS con backfill histórico de pago (backfill_historical_odds.py), gastando créditos con autorización explícita por tramos: primero un test chico (NFL 14d), luego NBA+NHL ~90d. NO se backfillea NFL aún.
- Reason: la captura forward solo crece desde hoy y NBA/NHL/NFL terminaron/están fuera de temporada → sin el histórico de pago no tendrían OOS hasta su próxima temporada. El test confirmó que /historical funciona en el plan (la memoria asumía 401) y el costo (30/llamada). NBA/NHL playoffs (abril-junio 2026) están EN la ventana reciente y tienen resultados → backfill barato y útil; NFL reciente son aperturas futuras (inútil), su temporada 2025 queda fuera del alcance "reciente-primero" del script.
- Alternatives: backfill full NHL+NBA+NFL (rechazado: ~10.800 créd > cuota; NFL reciente inútil); solo forward gratis (rechazado: NBA/NHL no se cubrirían hasta próxima temporada); gastar sin test (rechazado: la memoria decía 401, había que confirmar el endpoint primero).
- Consequences: NHL con n=188 (primera muestra OOS usable fuera de MLB), NBA n=67 (marginal). Cuota baja a 2.842. NFL OOS pendiente de una mejora --start/--end del script. Toda acción que gasta créditos se confirma explícitamente con el usuario (irreversible). El modelo pierde en NBA/NHL playoffs → cobertura para validar, no operar.

- Date: 2026-06-23
- Decision: Tras fit de calibradores por (liga, mercado) con `train_calibration.py --rebuild`, el ÚNICO calibrador MLB que se persiste es `mlb_spreads` (iso + beta); `mlb_h2h` y `mlb_totals` quedan SIN modelo (no-op) porque el gate auto-sanador detectó que la calibración EMPEORA su ECE out-of-sample. Con calibración ya `enabled: true` (method isotonic), el iso de mlb_spreads aplica a estimaciones live.
- Reason: disciplina OOS idéntica a la de las señales por deporte: persistir solo lo que mejora la métrica fuera de muestra. mlb_spreads raw ECE 0.0839 → iso 0.0810 / beta 0.0711 (mejora). mlb_h2h (0.1019→0.1182, n_val 38) y mlb_totals (0.0484 ya tight →0.1130, n_val 35) empeoran → el gate los descarta y limpia cualquier modelo previo, dejándolos en no-op seguro.
- Alternatives: forzar calibración de h2h/totals (rechazado: empeora OOS); cambiar `method` global a beta para capturar el mejor ECE de spreads 0.0711 (pospuesto: afecta a TODAS las ligas/mercados, decisión aparte); calibrar el moneyline contra el set per-game de 8.383 juegos en vez de graded bets (pospuesto: requiere otra ruta de entrenamiento — el calibrador hoy entrena sobre outcomes de apuestas colocadas por mercado).
- Consequences: producción aplica iso a spreads MLB; h2h/totals MLB sin tocar. La sobreconfianza per-game del moneyline (bins 0.5–0.7, ECE per-game 0.0188) NO queda corregida (muestra h2h colocada ~186, chica/sesgada). Sin cambio de código; rollback = borrar `data/models/mlb_spreads_calibration_*.joblib`. Vigilar ROI realizado de spreads tras unos días. SUPERSEDED el mismo día por la decisión `method: auto` (per-grupo) de abajo.

- Date: 2026-06-23
- Decision: La calibración pasa de un `method` GLOBAL a selección por (liga, mercado) vía `method: auto`. `train_calibration` registra el método ganador (menor ECE OOS entre los que baten al raw) en `data/models/calibration_methods.json`; `apply_calibration` con `method="auto"` resuelve por grupo desde ese registro y cae a no-op si no hay entrada / modelo / método válido. `configs/default.yaml` queda en `method: auto`.
- Reason: `method` global forzaba un trade-off: con `beta` global mlb_spreads mejoraba (ECE 0.0810→0.0711) pero nhl_h2h perdía su calibración (su beta se descartó, solo persistió iso → caía a no-op); con `isotonic` global pasaba lo inverso. El método óptimo varía por grupo, igual que la persistencia del modelo ya era por grupo. Auto deja que cada (liga, mercado) use su mejor calibrador validado OOS.
- Alternatives: dejar `beta` global (rechazado: sacrifica nhl_h2h); dejar `isotonic` global (rechazado: deja 0.0711→0.0810 en spreads); persistir un solo modelo "mejor" por grupo en vez de ambos + registro (rechazado: el doble persistido permite cambiar el criterio de selección sin re-fitear, y el registro es auto-sanador); guardar el ECE junto al modelo y elegir en apply-time (rechazado: más I/O por candidato; el registro JSON es O(1) y se cachea trivialmente).
- Consequences: registro `{mlb_spreads: beta, nhl_h2h: isotonic}`; producción calibra AMBOS a la vez (verificado: spreads 0.60→0.5825 beta, nhl_h2h 0.60→0.5789 iso; mlb_h2h/totals no-op). Un retrain que deja de ayudar a un grupo borra su entrada (no-op seguro). Rollback: `method: isotonic|beta` en YAML vuelve al esquema global. Tests test_calibrator.py 7→11; suite 196 passed; ruff limpio. La firma de `apply_calibration` con método desconocido ahora es no-op (antes caía a beta) — más seguro.

- Date: 2026-07-02
- Decision: Plan de remediación de la auditoría técnica completa ejecutado en rama `audit/remediation-2026-07-02` (3 commits: 6915a66 fase 2, 5f242c1 fase 3, 99f61b8 fase 4). Piezas clave: (a) `requirements.lock` como constraints de pip en CI (reproducibilidad; pyproject conserva los pisos); (b) pip-audit BLOQUEANTE en CI tras triage (idna→3.18, urllib3→2.7.0; lock re-auditado limpio); (c) superpowers-main DES-TRACKEADA de git pero conservada en disco (el plugin carga desde ese path); (d) hook de tests movido de PostToolUse (suite completa por edición) a Stop (una vez por turno, centinela `.claude/.tests-pending`, guard `stop_hook_active`); (e) guard de drift de esquema en OddsStore.append_snapshot (unión de columnas + reescritura atómica, mismo patrón KI-011); (f) rotación de logs por tamaño (`scripts/rotate_log.cmd`, >5MB→.1) en los 7 BAT; (g) helpers de probabilidad extraídos a `sqp/pipeline/probabilities.py` con re-import en daily (API intacta); (h) CI: job windows-latest + cobertura informativa en el leg 3.12; (i) duplicados .claude eliminados (MemoriaPersistente.skill anidado, zip residual, workflow full-system-audit duplicado del comando; colisión low-cost-mode resuelta deshabilitando la copia de usuario).
- Reason: hallazgos de la auditoría 2026-07-02 (sin críticos de código; deuda estructural y de reproducibilidad). Restricciones respetadas: sin cambios de comportamiento de negocio, sin eliminar funcionalidad (agentes especialistas conservados pese al solape con skills quant-*).
- Alternatives: pinear en pyproject (rechazado: rompe rangos de compatibilidad); acotar el hook de tests a "tests afectados" por heurística de nombre (rechazado: puede saltarse regresiones; Stop mantiene la suite completa); borrar superpowers-main del disco (rechazado: rompería la carga del plugin).
- Consequences: 277 tests verdes (1 nuevo, TDD), ruff limpio, 0 vulnerabilidades conocidas en el lock. Los hooks nuevos aplican desde la PRÓXIMA sesión (snapshot al inicio). El lock se regenera deliberadamente al subir deps (header documenta cómo). KI-015 RESUELTO; KI-017 (tenis e2e) y KI-018 (filtro "nan" Línea) registrados y ABIERTOS. Rama sin push (deny git push): merge/push del usuario.

- Date: 2026-07-27
- Decision: REDEFINICIÓN DEL OBJETIVO DEL PROYECTO (decisión de Carlos): el fin último es MAXIMIZAR EL PORCENTAJE DE ACIERTOS de los picks; bankroll, ROI y CLV dejan de ser los objetivos rectores ("No me sirve el bankroll, ni ROI, ni nada que haga que el porcentaje de aciertos sea bajo"). Propuesta aceptada conceptualmente, implementación PENDIENTE: "modo precisión" — `pick_mode: accuracy` conviviendo con el modo edge; selección por probabilidad estimada calibrada (blend modelo + no-vig del consenso) sobre umbral configurable (inicio 0.70), SOLO moneyline/ganador, prioridad a ligas mejor calibradas (WNCAAB/NCAAB, MLB ml), KPI = hit rate por liga y banda de probabilidad, calibración como control de cumplimiento del umbral.
- Reason: tras 7 meses la evidencia dice que el sistema no bate al cierre (CLV mediano 0.00% con n=300, gate vacío, OOS −5.32%), pero la estimación de probabilidades SÍ funciona (MLB per-game ECE 0.0188; WNCAAB Brier 0.188). El selector por edge trabaja activamente CONTRA el acierto (elige underdogs/discrepancias); spreads/totals tienen techo estructural ~50-55% de acierto por diseño de la casa. Para el objetivo nuevo, la parte validada de la plataforma es exactamente la necesaria.
- Alternatives: seguir optimizando ROI/CLV (rechazado por Carlos como objetivo); subir hit rate dentro del modo edge con filtros (rechazado: el criterio de selección es el problema, no un filtro encima); reconstruir la plataforma (innecesario: ratings, calibradores, captura, liquidación y reporte se reutilizan tal cual — cambio quirúrgico del criterio de selección + reporte).
- Consequences: el shadow mode y la honestidad estadística se mantienen (cada pick reporta probabilidad estimada, nunca certeza; advertencia dada: acierto alto ≠ ganancia a cuotas de favorito). El gate de CLV deja de ser la regla rectora de salida bajo el objetivo nuevo (pendiente decidir qué gate aplica al modo precisión: propuesto = cumplimiento del umbral prometido por banda). PRÓXIMA SESIÓN: implementar modo precisión. Hallazgo colateral vigente para el modo edge si se retoma: la masa de CLV=0.00 exactos sugiere entrada al precio de cierre (timing) — sin investigar.

- Date: 2026-08-02
- Decision: OBJETIVO SACROSANTO (directiva de Carlos, textual: "El fin del sistema es ganar dinero, eso escríbelo sobre piedra. Es sacrosanto."). La rentabilidad realizada es el fin último y definitivo del proyecto; supersede la redefinición del 2026-07-27 (hit rate como objetivo) y consolida el revert a `pick_mode: edge` del 2026-07-31 (commit f6c2130).
- Reason: el modo accuracy (activo 07-28→07-31) demostró en producción que maximizar hit rate pierde dinero por construcción (favoritos a cuotas 1.07–1.16, breakeven 93.5% a 1.07). El operador revirtió a edge el 07-31 y el 08-02 fijó la rentabilidad como objetivo sacrosanto.
- Alternatives: mantener hit rate como objetivo rector (superado por el propio operador); objetivo mixto sin jerarquía (rechazado: ambigüedad en decisiones de selección).
- Consequences: toda decisión de selección/riesgo/evaluación se juzga por contribución a la rentabilidad; el hit rate se reporta SIEMPRE contra el breakeven por cuota (`breakeven_hit_rate`/`hit_rate_margin`), nunca en absoluto. Las reglas de honestidad siguen intactas: ganar dinero es el objetivo, no un logro afirmable — a 2026-08-02 no hay edge demostrado (shadow activo, gate de CLV vacío, OOS −5.32% en la regla edge/Kelly). Cualquier reactivación del modo accuracy exige evidencia de rentabilidad esperada.

- Date: 2026-07-28
- Decision: Modo precisión IMPLEMENTADO y ACTIVADO en producción (`picks: {mode: accuracy, accuracy_threshold: 0.70}` en configs/default.yaml). Detalles de diseño: (a) selección = probabilidad de decisión calibrada (blend modelo + no-vig) >= umbral INCLUSIVE, SOLO h2h, nunca sobre mercado incompleto (sin ancla no-vig); (b) stake PLANO (bankroll*max_stake_pct) en lugar de Kelly — sin objetivo de EV no hay fracción óptima; (c) la cadena de stake 0 (paused/suspect/shadow/clv_gate) aplica intacta y cada pick lleva flag `accuracy_mode`; (d) la revocación por edge del segundo pase SALTA los picks accuracy (el guard de cambio de abridor sí aplica); (e) el KPI por banda (segments.py) se mide sobre la probabilidad CALIBRADA cuando existe, con bandas finas >=0.70; (f) default del dataclass sigue "edge" (Settings() directo byte-idéntico; producción activa por yaml, patrón park_bound), env PICK_MODE/ACCURACY_THRESHOLD ganan; (g) validate() exige umbral en [0.5, 1.0) — 1.0 afirmaría certeza.
- Reason: decisión estratégica del 2026-07-27 (objetivo = % de aciertos); el selector por edge favorece underdogs/discrepancias y trabaja contra el acierto; los favoritos calibrados de alta probabilidad son la parte validada de la plataforma.
- Alternatives: mantener Kelly en modo accuracy (rechazado: dimensiona por edge, sin sentido bajo el objetivo nuevo); permitir spreads/totals sobre umbral (rechazado: techo estructural ~50-55% por diseño de línea); que la revalidación re-chequee el umbral en vez de saltar (pospuesto a v2: requiere recomputar la probabilidad con el snapshot, no solo el precio); activar por defecto en el dataclass (rechazado: rompería demo/tests byte-idénticos con Settings() directo).
- Consequences: el run diario genera picks por probabilidad (con shadow todos a stake 0); modo edge conmutable (PICK_MODE=edge); el gate de CLV deja de ser la regla rectora de salida — PENDIENTE definir el gate del modo precisión (propuesta: cumplimiento del umbral por banda). 3 tests de mecánica edge fijados a pick_mode="edge". 436 tests verdes.

- Date: 2026-08-04
- Decision: Autorizar `claude-fable-5` como modelo de la conversación principal de Claude Code y mantener Opus/Haiku como modelos de subagentes; completar el routing con rutas explícitas para los 13 loops cuantitativos.
- Reason: la configuración principal ya seleccionaba Fable 5 por decisión del operador, mientras la política y las pruebas lo declaraban no disponible; el hook de palabras clave no representaba el decision engine cuantitativo.
- Alternatives: sustituir Fable 5 por Opus (rechazado por decisión explícita del operador); dejar el hook como recomendación parcial (rechazado: inyectaba loops incorrectos).
- Consequences: política principal/subagentes separada; 24 rutas validadas contra loops y agentes existentes; incidente cuantitativo tiene prioridad sobre el incidente general.

- Date: 2026-08-04
- Decision: Restablecer promoción humana por defecto para calibradores (`calibration.auto_promote: false`) y conservar la función automática únicamente como opt-in explícitamente aprobado.
- Reason: `ORCHESTRATOR.md`, `autonomy-policy.md` y los loops prohíben promoción automática; el YAML activo contradecía esa fuente autoritativa.
- Alternatives: reescribir todas las políticas para permitir promoción automática (rechazado: ampliaría riesgo y contradecía la regla vigente Train ≠ promote).
- Consequences: el run diario deja candidatos en staging; el registro live solo cambia por una acción aprobada. Los gates de la función opcional y su log permanecen probados.
