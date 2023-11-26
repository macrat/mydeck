.PHONY: run lint test fmt setup

run:
	.venv/bin/python -m mydeck

lint:
	.venv/bin/mypy . --ignore-missing-imports

fmt:
	.venv/bin/black .

setup:
	python -m venv .venv
	.venv/bin/pip install .[dev]
