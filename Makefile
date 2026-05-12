.PHONY: dev-backend dev-frontend migrate test shell \
        docker-dev docker-down docker-logs docker-shell docker-ps \
        docker-migrate docker-createsuperuser

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
	docker-compose up --build

docker-down:
	docker-compose down -v

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

docker-shell:
	docker-compose exec web python manage.py shell

docker-migrate:
	docker-compose exec web python manage.py migrate

docker-createsuperuser:
	docker-compose exec web python manage.py createsuperuser
