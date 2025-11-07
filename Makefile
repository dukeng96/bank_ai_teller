.PHONY: setup test fmt lint run

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

fmt:
	ruff check --select I --fix . || true
	ruff format .

lint:
	ruff check .
	mypy src

test:
	pytest -q --maxfail=1 --disable-warnings

run:
	python -m samples.demo_run happy
