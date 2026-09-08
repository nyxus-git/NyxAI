.PHONY: help setup install dev test test-all test-cov evaluate lint clean pull-model voice service-install service-start service-stop service-status service-logs toggle-ui ptt

PYTHON := .venv/bin/python
PIP    := .venv/bin/pip

# ─── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "NyxAI — Developer Commands"
	@echo "────────────────────────────────────────"
	@echo "  make install         Install Python dependencies"
	@echo "  make dev             Start FastAPI dev server (auto-reload)"
	@echo "  make voice           Start push-to-talk voice chat CLI (agent mode)"
	@echo "  make test            Run full test suite (all phases)"
	@echo "  make test-cov        Run tests with coverage report"
	@echo "  make evaluate        Run PRD Section 31 system benchmark suite"
	@echo "  make pull-model      Pull the default Ollama model"
	@echo "  make service-install Install systemd user services & build UI"
	@echo "  make service-start   Start all NyxAI systemd user services"
	@echo "  make service-stop    Stop all NyxAI systemd user services"
	@echo "  make service-status  Check persistent service status"
	@echo "  make service-logs    Follow systemd user journal logs"
	@echo "  make toggle-ui       Toggle Companion UI (SUPER+J)"
	@echo "  make ptt             Push-To-Talk voice trigger (SUPER+SPACE)"
	@echo "  make lint            Run ruff linter"
	@echo "  make clean           Remove __pycache__ and .pyc files"
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

# ─── Run tests (all phases) ───────────────────────────────────────────────────
test:
	.venv/bin/pytest api/tests/ tests/ -v --tb=short

test-all: test

# ─── Run tests with coverage ───────────────────────────────────────────────────
test-cov:
	.venv/bin/pytest api/tests/ tests/ -v --tb=short --cov=api --cov=core --cov=voice --cov=tools --cov=safety --cov-report=term-missing

# ─── Evaluation benchmark suite (PRD Section 31) ───────────────────────────────
evaluate:
	$(PYTHON) evaluation/evaluate.py --mock

# ─── Push-to-talk voice chat CLI ──────────────────────────────────────────────
voice:
	$(PYTHON) scripts/voice_chat.py --mode agent

# ─── Voice CLI (companion mode) ───────────────────────────────────────────────
voice-companion:
	$(PYTHON) scripts/voice_chat.py --mode companion

# ─── Companion Web UI (Phase 4) ────────────────────────────────────────────────
ui:
	cd apps/companion && npm install && npm run dev

companion-ui: ui

# ─── Persistent Deployment (Phase 8) ───────────────────────────────────────────
service-install:
	./scripts/install.sh

service-start:
	./scripts/run.sh start

service-stop:
	./scripts/run.sh stop

service-status:
	./scripts/run.sh status

service-logs:
	./scripts/run.sh logs

toggle-ui:
	./scripts/run.sh toggle

ptt:
	./scripts/run.sh ptt

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
