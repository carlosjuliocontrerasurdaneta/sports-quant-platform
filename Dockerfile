FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
# -c requirements.lock: mismas versiones que produccion/CI; un scikit-learn o
# joblib distinto puede des-serializar mal los artefactos .joblib (M-14).
RUN pip install --no-cache-dir -e . -c requirements.lock
ENV SQP_MODE=demo
CMD ["python", "scripts/run_daily.py", "--sports", "mlb", "nba", "nfl", "nhl", "--mode", "demo"]
