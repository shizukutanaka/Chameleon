# Chameleon Audio Tool - Commercial Build System

.PHONY: help install develop test test-all lint format security benchmark docs build publish docker clean

help:
	@echo "Chameleon Audio Tool - Commercial Build Targets"
	@echo "  install     Install package in development mode"
	@echo "  develop     Install development dependencies and hooks"
	@echo "  test        Run unit and integration tests"
	@echo "  test-all    Run full test suite with coverage report"
	@echo "  lint        Run static analysis (flake8, mypy)"
	@echo "  format      Format source using black and isort"
	@echo "  security    Execute security scanners (bandit, safety)"
	@echo "  benchmark   Execute performance benchmarks"
	@echo "  docs        Build HTML documentation"
	@echo "  build       Build distribution packages"
	@echo "  publish     Publish artifacts to PyPI"
	@echo "  docker      Build production Docker image"
	@echo "  clean       Remove build artifacts and caches"

install:
	pip install -e .

develop:
	pip install -e .[dev]
	pre-commit install || true

test:
	pytest tests -v

test-all:
	pytest tests -v --cov=audio_tool --cov-report=term --cov-report=html

lint:
	flake8 audio_tool.py tests
	mypy audio_tool.py tests --ignore-missing-imports

format:
	black audio_tool.py tests
	isort audio_tool.py tests

security:
	bandit -r audio_tool.py tests
	safety check --full-report || true

benchmark:
	pytest tests/performance -v --benchmark-only --benchmark-save-data

docs:
	sphinx-build -b html docs docs/_build/html

build:
	python -m build

publish: build
	twine upload dist/*

docker:
	docker build -t chameleon-audio:latest .
	docker tag chameleon-audio:latest chameleon-audio:1.0.0

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -rf docs/_build
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +