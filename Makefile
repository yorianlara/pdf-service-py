.PHONY: help build up down restart logs logs-web logs-worker logs-redis test clean health

help:
	@echo "Comandos disponibles:"
	@echo "  make build       - Construir las imágenes Docker"
	@echo "  make up          - Iniciar todos los servicios"
	@echo "  make down        - Detener todos los servicios"
	@echo "  make restart     - Reiniciar todos los servicios"
	@echo "  make logs        - Ver logs de todos los servicios"
	@echo "  make logs-web    - Ver logs del servicio web"
	@echo "  make logs-worker - Ver logs del worker"
	@echo "  make logs-redis  - Ver logs de Redis"
	@echo "  make test        - Ejecutar tests del servicio"
	@echo "  make health      - Verificar estado del servicio"
	@echo "  make clean       - Limpiar contenedores y volúmenes"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Servicios iniciados. Esperando 5 segundos..."
	@sleep 5
	@make health

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-worker:
	docker-compose logs -f worker

logs-redis:
	docker-compose logs -f redis

test:
	@echo "Ejecutando tests..."
	python test_service.py

health:
	@echo "Verificando estado del servicio..."
	@curl -s http://localhost:8200/health | python -m json.tool || echo "❌ Servicio no disponible"

clean:
	docker-compose down -v
	@echo "Limpiando archivos temporales..."
	@rm -f test_*.pdf temp_*.html
	@echo "✓ Limpieza completa"

# Comandos útiles adicionales
shell-web:
	docker exec -it pdf_web /bin/bash

shell-worker:
	docker exec -it pdf_worker /bin/bash

redis-cli:
	docker exec -it pdf_redis redis-cli

# Ver jobs en Redis
redis-jobs:
	@echo "Jobs en cola:"
	@docker exec pdf_redis redis-cli LLEN rq:queue:pdf_jobs
	@echo "\nMetadata de jobs:"
	@docker exec pdf_redis redis-cli --scan --pattern "pdf_meta:*"