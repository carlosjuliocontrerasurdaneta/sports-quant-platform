# -c requirements.lock: mismas versiones que CI, Docker y produccion. Sin el, el
# entorno local derivaba del pineado, y un joblib/scikit-learn distinto puede
# des-serializar mal los artefactos .joblib (auditoria 2026-07-29, S-11).
install:
	pip install -e ".[dev]" -c requirements.lock
test:
	pytest -q
demo:
	python scripts/run_daily.py --sports mlb nba nfl nhl --mode demo
lint:
	ruff check src scripts tests
types:
	mypy src
# Las tres puertas que CI aplica, en un solo comando local.
check: lint types test
