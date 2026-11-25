.PHONY: install lint typecheck test cov build

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check src tests

typecheck:
	mypy --strict src

test:
	pytest

cov:
	pytest --cov=receivables_radar --cov-report=term-missing --cov-fail-under=90

build:
	python -m build
