FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
# -c requirements.lock: mismas versiones que produccion/CI; un scikit-learn o
# joblib distinto puede des-serializar mal los artefactos .joblib (M-14).
RUN pip install --no-cache-dir -e . -c requirements.lock
# Usuario sin privilegios: el CMD no necesita root (auditoria 2026-07-29, S-7).
RUN useradd --create-home --uid 10001 sqp && chown -R sqp:sqp /app
USER sqp
ENV SQP_MODE=demo
CMD ["python", "scripts/run_daily.py", "--sports", "mlb", "nba", "nfl", "nhl", "--mode", "demo"]
