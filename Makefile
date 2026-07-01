install:
	pip install -e ".[dev]"
test:
	pytest -q
demo:
	python scripts/run_daily.py --sports mlb nba nfl nhl --mode demo
lint:
	ruff check src scripts tests
