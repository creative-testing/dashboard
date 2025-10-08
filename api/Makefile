.PHONY: help dev test run worker lint format clean db-migrate db-upgrade db-downgrade

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Setup development environment (venv + deps)
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements-api.txt
	@echo "✅ Dev environment ready. Activate: source .venv/bin/activate"

test: ## Run tests
	.venv/bin/pytest tests/ -v --cov=app --cov-report=term-missing

run: ## Run API server (dev mode with reload)
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker: ## Run background worker (RQ)
	.venv/bin/python worker.py

lint: ## Run linters (ruff + black check)
	.venv/bin/ruff check app/ tests/
	.venv/bin/black --check app/ tests/

format: ## Format code (black + isort)
	.venv/bin/black app/ tests/
	.venv/bin/isort app/ tests/

clean: ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

db-migrate: ## Create new migration (usage: make db-migrate MSG="description")
	.venv/bin/alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## Apply migrations (upgrade to head)
	.venv/bin/alembic upgrade head

db-downgrade: ## Rollback last migration
	.venv/bin/alembic downgrade -1

db-reset: ## Reset database (WARNING: drops all data)
	@echo "⚠️  This will DROP all tables. Press Ctrl+C to cancel..."
	@sleep 3
	.venv/bin/alembic downgrade base
	.venv/bin/alembic upgrade head

# Quick start aliases
start: run ## Alias for run
install: dev ## Alias for dev

.DEFAULT_GOAL := help
