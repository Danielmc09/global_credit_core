.PHONY: setup run stop clean migrate test logs

setup:
	@echo "🚀 Setting up the project..."
	cp .env.example .env
	docker-compose build
	docker-compose up -d postgres redis
	@echo "⏳ Waiting for database to be ready..."
	sleep 5
	@echo "✅ Setup complete! Run 'make run' to start the application"

run:
	@echo "🏃 Starting all services..."
	docker-compose up

run-bg:
	@echo "🏃 Starting all services in background..."
	docker-compose up -d
	@echo "✅ Services running. Check logs with 'make logs'"

stop:
	@echo "🛑 Stopping all services..."
	docker-compose down

clean:
	@echo "🧹 Cleaning up containers, volumes, and cache..."
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete"

migrate:
	@echo "🗄️  Running database migrations..."
	docker-compose exec backend alembic upgrade head

test:
	@echo "🧪 Running tests..."
	docker-compose exec backend pytest -v

test-cov:
	@echo "🧪 Running tests with coverage..."
	docker-compose exec backend pytest -v --cov=app --cov-report=term-missing --cov-report=html

test-unit:
	@echo "🧪 Running unit tests only..."
	docker-compose exec backend pytest -v -m unit tests/test_strategies.py

test-integration:
	@echo "🧪 Running integration tests only..."
	docker-compose exec backend pytest -v -m integration tests/test_api.py

test-workers:
	@echo "🧪 Running worker tests only..."
	docker-compose exec backend pytest -v tests/test_workers.py

test-frontend:
	@echo "🧪 Running frontend tests..."
	docker-compose exec frontend npm test

test-frontend-cov:
	@echo "🧪 Running frontend tests with coverage..."
	docker-compose exec frontend npm run test:coverage

test-frontend-watch:
	@echo "🧪 Running frontend tests in watch mode..."
	docker-compose exec frontend npm run test:watch

test-all:
	@echo "🧪 Running ALL tests (backend + frontend)..."
	@make test
	@make test-frontend

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-worker:
	docker-compose logs -f worker

shell-backend:
	docker-compose exec backend bash

shell-db:
	docker-compose exec postgres psql -U credit_user -d credit_db

load-test:
	@echo "🔥 Running load test with 200 requests (default)..."
	docker-compose exec backend python3 /app/app/scripts/load_test.py 200

load-test-%:
	@echo "🔥 Running load test with $* requests..."
	docker-compose exec backend python3 /app/app/scripts/load_test.py $*

help:
	@echo "Available commands:"
	@echo "  make setup      - Initial project setup"
	@echo "  make run        - Start all services (foreground)"
	@echo "  make run-bg     - Start all services (background)"
	@echo "  make stop       - Stop all services"
	@echo "  make clean      - Remove containers and volumes"
	@echo "  make migrate    - Run database migrations"
	@echo ""
	@echo "Backend Tests:"
	@echo "  make test       - Run backend tests"
	@echo "  make test-cov   - Run backend tests with coverage"
	@echo "  make test-unit  - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-workers - Run worker tests only"
	@echo ""
	@echo "Load Testing:"
	@echo "  make load-test        - Run load test with 200 requests (default)"
	@echo "  make load-test-<num>  - Run load test with specified number of requests"
	@echo "    Examples:"
	@echo "      make load-test        # 200 requests (default)"
	@echo "      make load-test-500    # 500 requests"
	@echo "      make load-test-50     # 50 requests"
	@echo "      make load-test-1000   # 1000 requests"
	@echo ""
	@echo "Frontend Tests:"
	@echo "  make test-frontend - Run frontend tests"
	@echo "  make test-frontend-cov - Run frontend tests with coverage"
	@echo "  make test-frontend-watch - Run frontend tests in watch mode"
	@echo ""
	@echo "All Tests:"
	@echo "  make test-all   - Run ALL tests (backend + frontend)"
	@echo ""
	@echo "Logs & Shell:"
	@echo "  make logs       - View all logs"
	@echo "  make shell-backend - Open backend container shell"
	@echo "  make shell-db   - Open PostgreSQL shell"
