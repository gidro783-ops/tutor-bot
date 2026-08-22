.PHONY: help install dev test lint run backup

help: ## Показать команды
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
	pip install -r requirements.txt

dev: ## Зависимости + инструменты разработки (ruff, pytest)
	pip install -r requirements-dev.txt

test: ## Pytest (БД, безопасность, логика) + смоук-тест
	python -m pytest tests/ -q
	python tests/smoke_test.py

lint: ## Проверка кода (ruff)
	ruff check .

run: ## Запуск бота
	python main.py

backup: ## Ручной бэкап базы в data/backups/
	python -m services.backup
