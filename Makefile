.PHONY: run lint test fmt setup

run:
	.venv/bin/python mydeck/main.py

lint:
	.venv/bin/mypy . --ignore-missing-imports

fmt:
	.venv/bin/black .

setup:
	python -m venv .venv
	.venv/bin/pip install .[dev]
