.PHONY: install lint test test-unit test-integration build local-start local-stop local-db-start local-db-stop deploy-dev deploy-prod clean validate

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
	cd local && (docker compose up -d localstack || docker-compose up -d localstack)
	powershell -NoProfile -ExecutionPolicy Bypass -Command "$$env:DYNAMODB_ENDPOINT='http://localhost:4566'; $$env:AWS_REGION='ap-southeast-1'; $$env:AWS_ACCESS_KEY_ID='test'; $$env:AWS_SECRET_ACCESS_KEY='test'; & './local/dynamodb/create_tables.ps1'"

local-db-stop:
	cd local && (docker compose down || docker-compose down)

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
