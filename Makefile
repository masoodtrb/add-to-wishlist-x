# Makefile for Docker management

.PHONY: help dev prod build clean logs shell test

# Default target
help:
	@echo "Available commands:"
	@echo "  dev          - Start development environment"
	@echo "  prod         - Start production environment"
	@echo "  build        - Build Docker images"
	@echo "  clean        - Clean up containers and volumes"
	@echo "  logs         - Show logs for all services"
	@echo "  shell        - Open shell in API container"
	@echo "  test         - Run tests"
	@echo "  stop         - Stop all services"
	@echo "  restart      - Restart all services"

# Development environment
dev:
	@echo "Starting development environment..."
	docker-compose up -d
	@echo "Services started:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Flower: http://localhost:5555"
	@echo "  - Redis: localhost:6379"

# Production environment
prod:
	@echo "Starting production environment..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "Production services started"

# Build images
build:
	@echo "Building Docker images..."
	docker-compose build

# Clean up
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose down -v
	docker-compose -f docker-compose.prod.yml down -v
	docker system prune -f

# Show logs
logs:
	docker-compose logs -f

# Production logs
logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

# Open shell in API container
shell:
	docker-compose exec api bash

# Production shell
shell-prod:
	docker-compose -f docker-compose.prod.yml exec api bash

# Run tests
test:
	docker-compose exec api python -m pytest

# Stop services
stop:
	docker-compose down
	docker-compose -f docker-compose.prod.yml down

# Restart services
restart:
	docker-compose restart

# Production restart
restart-prod:
	docker-compose -f docker-compose.prod.yml restart

# Health check
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health || echo "API is not responding"

# Production health check
health-prod:
	@echo "Checking production service health..."
	@curl -f http://localhost:8000/health || echo "API is not responding"
