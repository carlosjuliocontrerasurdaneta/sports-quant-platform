FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
RUN pip install --no-cache-dir -e .
ENV SQP_MODE=demo
CMD ["python", "scripts/run_daily.py", "--sports", "mlb", "nba", "nfl", "nhl", "--mode", "demo"]
