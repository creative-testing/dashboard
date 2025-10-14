# Repository Guidelines

## Branch Strategy & Production Safety
`master` powers the live Meta Ads dashboard—never push or merge into it without explicit owner approval. Daily work happens on `saas-mvp`; create topic branches from there and open PRs back into `saas-mvp`. Production data comes from GitHub Actions and Render jobs, so avoid editing `data/optimized` manually; use the refresh scripts instead. When deploying, keep the two GitHub workflows separate: use the fast code-only deploy for UI tweaks and the auto-refresh workflow for data updates.

## Project Structure & Module Organization
The FastAPI backend sits in `api/app` with routers under `api/app/routers`, domain logic in `api/app/services`, and schemas in `api/app/schemas`. Alembic migrations live in `api/alembic`, while backend tests mirror features inside `api/tests`. Marketing dashboards and static assets are under `docs/`, and automation helpers live in `scripts/` (`scripts/dev`, `scripts/production`). Large fetch baselines stay in `baseline_90d_daily.json.zst`; treat it as read-only.

## Build, Test, and Development Commands
From `api/`, run `make dev` to create `.venv` and install dependencies, `make run` for the local API on `http://localhost:8000`, and `make test` for the full pytest + coverage suite. Use `make lint` or `make format` to enforce Ruff/Black before committing. To rehearse the data pipeline locally, execute `bash refresh_local.sh`; it chains fetch, transform, and copy steps.

## Coding Style & Naming Conventions
Python modules use 4-space indents, 100-character lines, and explicit type hints. Name routers and services after the domain (`routers/auth.py`, `services/tenant.py`), keep route slugs kebab-case, and define environment variables in SCREAMING_SNAKE_CASE. Scripts should use snake_case filenames and start with a short docstring describing the entrypoint.

## Testing Guidelines
Pytest discovers files named `test_*.py`; follow that pattern (`api/tests/test_stripe_webhook.py`). Group shared fixtures in `conftest.py` and favor behavioral assertions over implementation details. Aim to keep coverage consistent with `pyproject.toml` defaults by running `make test`. Before shipping anything touching fetch or transforms, run `./api/test_refresh.py` and `./api/test_dashboard_flow.sh` for end-to-end checks.

## Commit & Pull Request Guidelines
History favors concise, emoji-prefixed subjects such as `🚀 Add Render deployment configuration`. Keep the first line under 72 characters and add context or `Refs #123` lines in the body when relevant. PRs should link to issues, include validation steps (`make test`, `make lint`, refresh scripts when relevant), and attach screenshots or logs for UI/API changes. Request review from the module owner (API, dashboards, or data pipeline) and call out migrations or configuration updates explicitly.
