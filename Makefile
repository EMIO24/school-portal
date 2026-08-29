COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then echo docker compose; else echo docker-compose; fi)

.PHONY: dev-backend dev-frontend migrate test shell \
        docker-dev docker-up docker-build docker-down docker-logs docker-shell docker-ps \
        docker-migrate docker-createsuperuser fresh

# ── Local dev (no Docker) ─────────────────────────────────────────────────

dev-backend:
	cd backend && python manage.py runserver

dev-frontend:
	cd frontend && npm start

migrate:
	cd backend && python manage.py migrate

test:
	cd backend && python manage.py test

shell:
	cd backend && python manage.py shell

# ── Docker (local dev with docker-compose) ────────────────────────────────

docker-dev:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) up --build

docker-up:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) up

docker-build:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) build

docker-down:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) down -v --remove-orphans

docker-logs:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) logs -f

docker-ps:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) ps

docker-shell:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) exec web python manage.py shell

docker-migrate:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) exec web python manage.py migrate

docker-createsuperuser:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) exec web python manage.py createsuperuser

fresh:
	@docker version >/dev/null 2>&1 || (echo "Docker is not available. Start Docker Desktop and enable WSL integration for this distro."; exit 1)
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE) up --build
