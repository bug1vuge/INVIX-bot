COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f compose.yaml -f compose.prod.yaml

.PHONY: help up up-prod down ps logs scale test lint fmt

help:
	@echo "up        build and start the stack on http://localhost (no TLS)"
	@echo "up-prod   build and start with the TLS edge (needs DOMAIN in .env)"
	@echo "down      stop the stack (volumes are kept)"
	@echo "ps        show containers and health"
	@echo "logs      follow logs, e.g. make logs s=bot"
	@echo "scale     change replicas, e.g. make scale api=3 bot=3 web=3"
	@echo "test      run all test suites"
	@echo "lint      run linters"

up:
	$(COMPOSE) up -d --build

up-prod:
	$(COMPOSE_PROD) up -d --build

down:
	$(COMPOSE_PROD) down

ps:
	$(COMPOSE_PROD) ps

logs:
	$(COMPOSE_PROD) logs -f --tail=100 $(s)

api ?= 2
bot ?= 2
web ?= 2
scale:
	$(COMPOSE_PROD) up -d --no-recreate --scale api=$(api) --scale bot=$(bot) --scale web=$(web)

test:
	cd services/api && uv run pytest -q
	cd services/bot && uv run pytest -q
	cd services/web && npm run typecheck

lint:
	cd services/api && uv run ruff check . && uv run ruff format --check .
	cd services/bot && uv run ruff check . && uv run ruff format --check .
	cd services/web && npm run lint

fmt:
	cd services/api && uv run ruff format . && uv run ruff check --fix .
	cd services/bot && uv run ruff format . && uv run ruff check --fix .
