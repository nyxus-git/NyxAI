.PHONY: help setup install dev test lint clean pull-model

PYTHON := .venv/bin/python
PIP    := .venv/bin/pip

# ─── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "NyxAI — Developer Commands"
	@echo "────────────────────────────────────────"
	@echo "  make install      Install Python dependencies"
	@echo "  make dev          Start FastAPI dev server (auto-reload)"
	@echo "  make test         Run test suite"
	@echo "  make pull-model   Pull the default Ollama model"
	@echo "  make lint         Run ruff linter"
	@echo "  make clean        Remove __pycache__ and .pyc files"
	@echo ""

# ─── Create venv + install dependencies ──────────────────────────────────────
setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "\nDone. Run 'make dev' to start NyxAI."

# ─── Install dependencies (assumes venv already exists) ───────────────────────
install:
	$(PIP) install -r requirements.txt

# ─── Start development server ──────────────────────────────────────────────────
dev:
	.venv/bin/uvicorn api.app.main:app --reload --host 127.0.0.1 --port 8000

# ─── Run tests ─────────────────────────────────────────────────────────────────
test:
	.venv/bin/pytest api/tests/ -v --tb=short

# ─── Run tests with coverage ───────────────────────────────────────────────────
test-cov:
	.venv/bin/pytest api/tests/ -v --tb=short --cov=api --cov=core --cov-report=term-missing

# ─── Pull recommended Ollama model ────────────────────────────────────────────
pull-model:
	@echo "Pulling qwen2.5:3b — this may take a few minutes..."
	ollama pull qwen2.5:3b
	@echo "Done. Run 'make dev' to start NyxAI."

# ─── Lint ──────────────────────────────────────────────────────────────────────
lint:
	.venv/bin/ruff check . --fix

# ─── Clean compiled files ──────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
