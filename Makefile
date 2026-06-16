.PHONY: start stop logs restart build

start:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

build:
	docker compose build
