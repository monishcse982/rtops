IMAGE=rtops-api:dev
CLUSTER=rtops
NS=rtops
K8S_BASE_DIR=k8s/base
KUSTOMIZE_DIR=k8s/overlays/local
LOCUST_CONFIG=tests/perf/locust.local.conf
LOCUST_HOST?=http://localhost:8000
LOCUST_USERS?=10
LOCUST_SPAWN_RATE?=2
LOCUST_RUN_TIME?=1m
TMP_DIR=.tmp
API_PORT_FORWARD_PID=$(TMP_DIR)/api-port-forward.pid
API_PORT_FORWARD_LOG=$(TMP_DIR)/api-port-forward.log
POSTGRES_PORT_FORWARD_PID=$(TMP_DIR)/postgres-port-forward.pid
POSTGRES_PORT_FORWARD_LOG=$(TMP_DIR)/postgres-port-forward.log
CACHE_PORT_FORWARD_PID=$(TMP_DIR)/cache-port-forward.pid
CACHE_PORT_FORWARD_LOG=$(TMP_DIR)/cache-port-forward.log

.DEFAULT_GOAL := help

.PHONY: help up down clean k8s-e2e locust locust-headless

help:
	@echo "make up               Create the k3d cluster, deploy the stack, run migrations and seed data, and port-forward local services"
	@echo "make down             Stop local port-forwards and delete the local k3d cluster"
	@echo "make clean            Remove Python caches, test caches, local temp files, and build artifacts"
	@echo "make k8s-e2e          Run E2E tests against the local k3d deployment"
	@echo "make locust           Start the Locust UI against the local API"
	@echo "make locust-headless  Run Locust headless with LOCUST_USERS, LOCUST_SPAWN_RATE, and LOCUST_RUN_TIME"

up:
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		echo "Cluster $(CLUSTER) already exists"; \
	else \
		k3d cluster create $(CLUSTER) --servers 1 --agents 1 --wait --timeout 120s; \
	fi
	kubectl wait --for=condition=Ready nodes --all --timeout=180s
	docker build -t $(IMAGE) .
	k3d image import $(IMAGE) -c $(CLUSTER)
	kubectl delete job migration seed -n $(NS) --ignore-not-found
	kubectl apply -k $(KUSTOMIZE_DIR)
	kubectl rollout status statefulset/postgres -n $(NS) --timeout=180s
	kubectl rollout status statefulset/rabbitmq -n $(NS) --timeout=180s
	kubectl rollout status statefulset/cache -n $(NS) --timeout=180s
	kubectl wait --for=condition=complete job/migration -n $(NS) --timeout=180s
	kubectl rollout status deployment/api -n $(NS) --timeout=180s
	kubectl wait --for=condition=complete job/seed -n $(NS) --timeout=180s
	mkdir -p $(TMP_DIR)
	@if [ -f $(API_PORT_FORWARD_PID) ] && kill -0 "$$(cat $(API_PORT_FORWARD_PID))" >/dev/null 2>&1; then \
		echo "API port-forward already running on $(LOCUST_HOST)"; \
	else \
		rm -f $(API_PORT_FORWARD_PID); \
		(kubectl port-forward svc/api 8000:8000 -n $(NS) > $(API_PORT_FORWARD_LOG) 2>&1 & echo $$! > $(API_PORT_FORWARD_PID)); \
		echo "API port-forward started on $(LOCUST_HOST)"; \
	fi
	@if [ -f $(POSTGRES_PORT_FORWARD_PID) ] && kill -0 "$$(cat $(POSTGRES_PORT_FORWARD_PID))" >/dev/null 2>&1; then \
		echo "Postgres port-forward already running on localhost:5432"; \
	else \
		rm -f $(POSTGRES_PORT_FORWARD_PID); \
		(kubectl port-forward svc/postgres 5432:5432 -n $(NS) > $(POSTGRES_PORT_FORWARD_LOG) 2>&1 & echo $$! > $(POSTGRES_PORT_FORWARD_PID)); \
		echo "Postgres port-forward started on localhost:5432"; \
	fi
	@if [ -f $(CACHE_PORT_FORWARD_PID) ] && kill -0 "$$(cat $(CACHE_PORT_FORWARD_PID))" >/dev/null 2>&1; then \
		echo "Cache port-forward already running on localhost:6379"; \
	else \
		rm -f $(CACHE_PORT_FORWARD_PID); \
		(kubectl port-forward svc/cache 6379:6379 -n $(NS) > $(CACHE_PORT_FORWARD_LOG) 2>&1 & echo $$! > $(CACHE_PORT_FORWARD_PID)); \
		echo "Cache port-forward started on localhost:6379"; \
	fi

down:
	@echo "Stopping API port-forward..."
	@if [ -f $(API_PORT_FORWARD_PID) ]; then \
		pid=$$(cat $(API_PORT_FORWARD_PID)); \
		if kill -0 $$pid >/dev/null 2>&1; then \
			kill $$pid; \
			echo "Stopped API port-forward $$pid"; \
		fi; \
		rm -f $(API_PORT_FORWARD_PID); \
	else \
		echo "No API port-forward PID file found."; \
	fi
	@echo "Stopping Postgres port-forward..."
	@if [ -f $(POSTGRES_PORT_FORWARD_PID) ]; then \
		pid=$$(cat $(POSTGRES_PORT_FORWARD_PID)); \
		if kill -0 $$pid >/dev/null 2>&1; then \
			kill $$pid; \
			echo "Stopped Postgres port-forward $$pid"; \
		fi; \
		rm -f $(POSTGRES_PORT_FORWARD_PID); \
	else \
		echo "No Postgres port-forward PID file found."; \
	fi
	@echo "Stopping cache port-forward..."
	@if [ -f $(CACHE_PORT_FORWARD_PID) ]; then \
		pid=$$(cat $(CACHE_PORT_FORWARD_PID)); \
		if kill -0 $$pid >/dev/null 2>&1; then \
			kill $$pid; \
			echo "Stopped cache port-forward $$pid"; \
		fi; \
		rm -f $(CACHE_PORT_FORWARD_PID); \
	else \
		echo "No cache port-forward PID file found."; \
	fi
	@rm -f $(API_PORT_FORWARD_LOG) $(POSTGRES_PORT_FORWARD_LOG) $(CACHE_PORT_FORWARD_LOG)
	@echo "Deleting k3d cluster $(CLUSTER)..."
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		k3d cluster delete $(CLUSTER); \
		echo "Deleted cluster $(CLUSTER)"; \
	else \
		echo "Cluster $(CLUSTER) does not exist."; \
	fi

clean:
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".hypothesis" -o -name ".tox" -o -name ".nox" \) -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build dist *.egg-info .coverage .coverage.* coverage.xml htmlcov junit.xml reports allure-results allure-report $(TMP_DIR)

k8s-e2e:
	DATABASE_URL="$$(grep '^DATABASE_URL=' $(K8S_BASE_DIR)/secret.env | cut -d= -f2- | sed 's/@postgres:/@localhost:/')" \
	API_URL=http://localhost:8000 \
	REDIS_URL=redis://localhost:6379/0 \
	uv run pytest tests/e2e -q -s

locust:
	uv run locust --config $(LOCUST_CONFIG) --host $(LOCUST_HOST)

locust-headless:
	uv run locust --config $(LOCUST_CONFIG) --host $(LOCUST_HOST) --headless -u $(LOCUST_USERS) -r $(LOCUST_SPAWN_RATE) -t $(LOCUST_RUN_TIME)
