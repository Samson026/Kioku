.PHONY: help install install-dev dev run test test-unit test-integration test-cov lint format type-check quality docker-build docker-run clean check-env

# Default target - show help
help:
	@echo "Kioku Development Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Run development server with auto-reload"
	@echo "  make run              Run production server"
	@echo "  make check-env        Verify .env file exists"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-cov         Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run flake8 linting"
	@echo "  make format           Format code with black and isort"
	@echo "  make type-check       Run mypy type checking"
	@echo "  make quality          Run all quality checks (lint + type-check)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-run       Run Docker container"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache"

# Installation targets
install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt

# Development server
dev: check-env
	uvicorn kioku.app:app --reload --host 0.0.0.0 --port 8000

# Production server
run: check-env
	uvicorn kioku.app:app --host 0.0.0.0 --port 8000

# Testing targets
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v -m "not slow"

test-integration:
	pytest tests/integration/ -v

test-cov:
	pytest tests/ -v --cov=kioku --cov-report=html --cov-report=term

# Code quality targets
lint:
	flake8 kioku/ tests/

format:
	black kioku/ tests/
	isort kioku/ tests/

type-check:
	mypy kioku/

quality: lint type-check
	@echo "All quality checks passed!"

# Docker targets
docker-build:
	docker build -t kioku:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env kioku:latest

# Utility targets
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create one with required environment variables."; \
		exit 1; \
	fi

clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf **/__pycache__/
	rm -rf **/*.pyc
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
