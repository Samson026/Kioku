.PHONY: help install install-dev dev run test test-unit test-integration test-cov lint format type-check quality build-wheel docker-build docker-run docker-save docker-deploy deploy clean check-env

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
	@echo "Build:"
	@echo "  make build-wheel      Build Python wheel into dist/"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build        Build Docker image (builds wheel first)"
	@echo "  make docker-run          Run Docker container directly"
	@echo "  make docker-compose-up   Build and run with docker-compose (recommended)"
	@echo "  make docker-compose-down Stop docker-compose services"
	@echo "  make docker-compose-logs View docker-compose logs"
	@echo "  make docker-save         Save Docker image to kioku.tar"
	@echo "  make docker-deploy       Save and scp Docker image to PI_HOST"
	@echo ""
	@echo "Deploy:"
	@echo "  make deploy           Scp wheel to PI_HOST"
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

# Build targets
build-wheel:
	rm -rf dist/ build/
	pip wheel --no-deps -w dist/ .

# Docker targets
docker-build:
	docker build -t kioku:latest .

docker-run:
	docker run -d -p 8000:8000 --env-file .env \
		-v kioku-cache:/root/.cache/huggingface \
		-e HF_HOME=/root/.cache/huggingface \
		kioku:latest

docker-compose-up:
	docker-compose up -d --build

docker-compose-down:
	docker-compose down

docker-compose-logs:
	docker-compose logs -f

docker-save:
	docker save kioku:latest -o kioku.tar

docker-deploy: docker-save
	scp kioku.tar $(PI_HOST):~/
	ssh $(PI_HOST) 'docker load -i ~/kioku.tar'

# Deploy wheel directly
deploy: build-wheel
	scp dist/*.whl $(PI_HOST):~/

# Utility targets
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create one with required environment variables."; \
		exit 1; \
	fi

clean:
	rm -rf dist/ build/ *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf **/__pycache__/
	rm -rf **/*.pyc
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
