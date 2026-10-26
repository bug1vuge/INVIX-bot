# Compose files are picked from COMPOSE_FILE in .env: compose.yaml locally,
# compose.yaml:compose.prod.yaml on the server (adds the TLS edge).
COMPOSE := docker compose

.PHONY: help up down ps logs scale test lint fmt

help:
	@echo "up        build and start the stack"
	@echo "down      stop the stack (volumes are kept)"
	@echo "ps        show containers and health"
	@echo "logs      follow logs, e.g. make logs s=bot"
	@echo "scale     change replicas, e.g. make scale api=3 bot=3 web=3"
	@echo "test      run all test suites"
	@echo "lint      run linters"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps -a

logs:
	$(COMPOSE) logs -f --tail=100 $(s)

api ?= 2
bot ?= 2
web ?= 2
scale:
	$(COMPOSE) up -d --no-recreate --scale api=$(api) --scale bot=$(bot) --scale web=$(web) api bot web

test:
	cd services/api && uv run pytest -q
	cd services/bot && uv run pytest -q
	cd services/web && npm run typecheck

lint:
	cd services/api && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd services/bot && uv run ruff check . && uv run ruff format --check . && uv run mypy bot
	cd services/web && npm run lint

fmt:
	cd services/api && uv run ruff format . && uv run ruff check --fix .
	cd services/bot && uv run ruff format . && uv run ruff check --fix .
