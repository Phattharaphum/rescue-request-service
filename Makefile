.PHONY: install lint test test-unit test-integration build local-start local-stop deploy-dev deploy-prod clean

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

lint:
	python -m ruff check src/ tests/
	python -m black --check src/ tests/

format:
	python -m black src/ tests/
	python -m isort src/ tests/

test: test-unit

test-unit:
	python -m pytest tests/unit/ -v

test-integration:
	python -m pytest tests/integration/ -v

build:
	sam build --template-file template.yaml

local-db-start:
	cd local && docker-compose up -d dynamodb-local
	sleep 3
	cd local/dynamodb && bash create_tables.sh

local-db-stop:
	cd local && docker-compose down

local-start: local-db-start
	sam local start-api --template-file template.local.yaml --docker-network rescue-net --env-vars .env.json

local-stop: local-db-stop

deploy-dev:
	sam deploy --config-env default

deploy-prod:
	sam deploy --config-env prod

clean:
	rm -rf .aws-sam/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

validate:
	sam validate --template-file template.yaml
