# Chameleon Audio System - Development Makefile
# ===============================================

.PHONY: help install test test-unit test-integration test-performance test-all
.PHONY: benchmark lint format clean coverage docs ci smoke
.PHONY: build package deploy run demo

# Default target
help:
	@echo "Chameleon Audio System - Development Commands"
	@echo "=============================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install         Install dependencies"
	@echo "  install-dev     Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-performance Run performance tests only"
	@echo "  smoke           Run smoke tests (critical tests)"
	@echo "  coverage        Run tests with coverage report"
	@echo ""
	@echo "Quality & Benchmarks:"
	@echo "  lint            Run code linting"
	@echo "  format          Format code"
	@echo "  benchmark       Run performance benchmarks"
	@echo "  benchmark-quick Run quick benchmarks"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci              Run full CI pipeline"
	@echo "  ci-fast         Run fast CI checks"
	@echo ""
	@echo "Documentation:"
	@echo "  docs            Generate documentation"
	@echo "  docs-serve      Serve documentation locally"
	@echo ""
	@echo "Utilities:"
	@echo "  clean           Clean build artifacts"
	@echo "  demo            Run system demo"
	@echo "  run             Run main application"

# Variables
PYTHON := python3
PIP := pip3
PROJECT_NAME := chameleon
TEST_DIR := .
SRC_DIR := .

# Installation
install:
	@echo "Installing Chameleon dependencies..."
	$(PIP) install -r requirements.txt

install-dev:
	@echo "Installing development dependencies..."
	$(PIP) install pytest pytest-cov pytest-xdist pytest-html
	$(PIP) install black flake8 mypy isort
	$(PIP) install coverage bandit safety

# Testing
test: test-unit test-integration
	@echo "All tests completed ✅"

test-unit:
	@echo "Running unit tests..."
	$(PYTHON) test_framework.py unit

test-integration:
	@echo "Running integration tests..."
	$(PYTHON) test_framework.py integration

test-performance:
	@echo "Running performance tests..."
	$(PYTHON) test_framework.py performance

test-all: test-unit test-integration test-performance
	@echo "All test suites completed ✅"

smoke:
	@echo "Running smoke tests..."
	$(PYTHON) test_runner.py --smoke

coverage:
	@echo "Running tests with coverage..."
	$(PYTHON) test_framework.py coverage

# Advanced test runner
test-runner:
	@echo "Running advanced test suite..."
	$(PYTHON) test_runner.py

test-runner-parallel:
	@echo "Running tests in parallel..."
	$(PYTHON) test_runner.py --type unit --type integration

test-runner-critical:
	@echo "Running critical tests only..."
	$(PYTHON) test_runner.py --priority critical

# Quality checks
lint:
	@echo "Running code linting..."
	@echo "Checking Python syntax..."
	$(PYTHON) -m py_compile *.py
	@echo "Running flake8..."
	-flake8 --max-line-length=100 --ignore=E203,W503 *.py
	@echo "Running mypy..."
	-mypy --ignore-missing-imports *.py

format:
	@echo "Formatting code..."
	black --line-length 100 *.py
	isort *.py

security:
	@echo "Running security checks..."
	bandit -r . -f json -o security_report.json
	safety check --json --output safety_report.json

# Benchmarks
benchmark:
	@echo "Running comprehensive benchmarks..."
	$(PYTHON) benchmark_suite.py

benchmark-quick:
	@echo "Running quick benchmarks..."
	$(PYTHON) benchmark_suite.py --quick

benchmark-category:
	@echo "Running latency benchmarks..."
	$(PYTHON) benchmark_suite.py --category latency
	@echo "Running throughput benchmarks..."
	$(PYTHON) benchmark_suite.py --category throughput

# CI/CD
ci:
	@echo "Running full CI pipeline..."
	$(PYTHON) continuous_integration.py

ci-fast:
	@echo "Running fast CI checks..."
	$(PYTHON) continuous_integration.py --stages syntax_check unit_tests quality_checks

ci-github:
	@echo "Creating GitHub Actions workflow..."
	$(PYTHON) continuous_integration.py --create-workflow

# Documentation
docs:
	@echo "Documentation already available:"
	@echo "  - FINAL_SYSTEM_DOCUMENTATION.md (Complete system docs)"
	@echo "  - README.md (Getting started)"
	@echo "  - main.py --help (CLI reference)"

docs-serve:
	@echo "Starting local documentation server..."
	@echo "Open http://localhost:8000 in your browser"
	$(PYTHON) -m http.server 8000

# Utilities
clean:
	@echo "Cleaning build artifacts..."
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf test_results/
	rm -rf ci_artifacts/
	rm -rf *.pyc
	rm -rf benchmark_report_*.json
	rm -rf test_report_*.json
	rm -rf test_report_*.html
	rm -rf security_report.json
	rm -rf safety_report.json
	@echo "Clean completed ✅"

# Demos and examples
demo:
	@echo "Running Chameleon demo..."
	$(PYTHON) main.py demo

demo-voice:
	@echo "Running voice processing demo..."
	$(PYTHON) main.py voice demo

demo-stream:
	@echo "Running streaming demo..."
	$(PYTHON) main.py stream demo

demo-ml:
	@echo "Running ML demo..."
	$(PYTHON) main.py ml demo

# Run application
run:
	@echo "Starting Chameleon Audio System..."
	$(PYTHON) main.py

run-interactive:
	@echo "Starting interactive mode..."
	$(PYTHON) main.py interactive

run-server:
	@echo "Starting audio server..."
	$(PYTHON) main.py server start

# Development workflow
dev-setup: install-dev
	@echo "Setting up development environment..."
	@echo "Creating test directories..."
	mkdir -p test_results
	mkdir -p ci_artifacts
	@echo "Development setup complete ✅"

dev-test: lint test-unit
	@echo "Development test cycle complete ✅"

dev-full: lint test-all benchmark-quick
	@echo "Full development cycle complete ✅"

# Performance monitoring
perf-monitor:
	@echo "Starting performance monitoring..."
	$(PYTHON) -c "from performance import PerformanceMonitor; m = PerformanceMonitor(); m.start_monitoring(); input('Press Enter to stop...'); print(m.get_stats())"

# Quality gates
quality-gate: lint test-unit
	@echo "Quality gate checks..."
	@echo "✅ Code quality passed"

# Build and package (for future use)
build:
	@echo "Build step - currently not needed for Python project"

package:
	@echo "Packaging Chameleon..."
	$(PYTHON) setup.py sdist bdist_wheel

# Deployment (placeholder)
deploy:
	@echo "Deployment not configured yet"

# File watchers (using Python watchdog if available)
watch-tests:
	@echo "Watching files for test execution..."
	@echo "Install watchdog: pip install watchdog"
	-$(PYTHON) -c "import watchdog; print('Starting file watcher...')" && \
	watchmedo shell-command --patterns="*.py" --command="make test-unit" .

# Project stats
stats:
	@echo "Project Statistics:"
	@echo "==================="
	@echo "Python files: $$(find . -name '*.py' | wc -l)"
	@echo "Total lines: $$(find . -name '*.py' -exec wc -l {} + | tail -1)"
	@echo "Functions: $$(grep -r '^def ' *.py | wc -l)"
	@echo "Classes: $$(grep -r '^class ' *.py | wc -l)"
	@echo "Tests: $$(grep -r '^    def test_' *.py | wc -l)"

# Git hooks (development)
install-hooks:
	@echo "Installing git hooks..."
	@echo '#!/bin/bash\nmake quality-gate' > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed ✅"

# Quick commands
quick-test: test-unit
	@echo "Quick test completed ✅"

quick-check: lint quick-test
	@echo "Quick check completed ✅"

# All-in-one targets
full-check: clean lint test-all benchmark-quick ci-fast
	@echo "Full system check completed ✅"

release-check: clean lint test-all benchmark coverage security
	@echo "Release readiness check completed ✅"