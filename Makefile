dev-backend:
	cd backend && python manage.py runserver
dev-frontend:
	cd frontend && npm start
migrate:
	cd backend && python manage.py migrate
test:
	cd backend && python manage.py test