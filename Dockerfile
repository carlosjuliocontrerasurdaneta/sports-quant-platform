# ALCANCE DE ESTA IMAGEN: entorno de DEMO y referencia, NO una replica de
# produccion (AUD-LOW-004, 2026-09-06). Produccion corre en Windows bajo el
# Programador de tareas con Python 3.14 (los .bat fijan SQP_PYTHON a Python314,
# y por eso CI anadio esa pata en la matriz); aqui se fija 3.11, que es el SUELO
# que declara pyproject. El comentario de abajo afirmaba "mismas versiones que
# produccion", y del interprete era falso.
#
# Ademas NADIE CONSTRUYE esta imagen: .github/workflows/ci.yml no tiene ningun
# paso de docker build, asi que puede romperse sin que ninguna puerta lo note.
# Antes de confiar en ella para algo real: construirla, y decidir entonces si se
# alinea la base con 3.14.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
# -c requirements.lock: mismas versiones de LIBRERIAS que produccion/CI (el
# interprete difiere, ver arriba); un scikit-learn o joblib distinto puede
# des-serializar mal los artefactos .joblib (M-14).
RUN pip install --no-cache-dir -e . -c requirements.lock
# Usuario sin privilegios: el CMD no necesita root (auditoria 2026-07-29, S-7).
RUN useradd --create-home --uid 10001 sqp && chown -R sqp:sqp /app
USER sqp
ENV SQP_MODE=demo
CMD ["python", "scripts/run_daily.py", "--sports", "mlb", "nba", "nfl", "nhl", "--mode", "demo"]
