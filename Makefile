.PHONY: help install test benchmark clean docker-build docker-run api setup

help:
	@echo "Chameleon Audio System - Make Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup      - Run initial setup and verification"
	@echo "  make install    - Install optional dependencies"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test       - Run all tests"
	@echo "  make benchmark  - Run performance benchmarks"
	@echo "  make lint       - Run code quality checks"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"
	@echo "  make docker-compose - Start all services"
	@echo ""
	@echo "Development:"
	@echo "  make api        - Start API server"
	@echo "  make gui        - Launch GUI interface"
	@echo "  make examples   - Run example scripts"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      - Clean temporary files"
	@echo "  make format     - Format code with black"

setup:
	python3 scripts/setup.py

install:
	pip install -r requirements.txt
	pip install -r requirements_optional.txt

test:
	python3 tests/test_audio.py

benchmark:
	python3 scripts/benchmark.py

lint:
	@which flake8 > /dev/null || pip install flake8
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics

format:
	@which black > /dev/null || pip install black
	black --line-length 120 *.py examples/*.py scripts/*.py tests/*.py

docker-build:
	docker build -t chameleon-audio:latest .

docker-run:
	docker run -it --rm -v $(PWD)/data:/data chameleon-audio:latest

docker-compose:
	docker-compose up

api:
	python3 api_server.py

gui:
	python3 audio_gui.py

examples:
	@echo "Running basic examples..."
	python3 examples/basic_usage.py
	@echo ""
	@echo "Running advanced demo..."
	python3 examples/advanced_demo.py
	@echo ""
	@echo "Running real-world examples..."
	python3 examples/real_world_examples.py

clean:
	rm -f *.wav *.pyc *.pyo
	rm -rf __pycache__ .pytest_cache
	rm -f test_audio.wav test_output.wav
	rm -f benchmark_report.json config.json
	rm -f commercial_*_broadcast.wav
	rm -f podcast_*.wav master_*.wav
	rm -f complex_audio.wav streamed_output.wav adaptive_output.wav
	rm -f test_batch_*.wav batch_config.json
	rm -f broadcast_delivery_report.json
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.DEFAULT_GOAL := help