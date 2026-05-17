IMAGE=rtops-api:dev
CLUSTER=rtops
NS=rtops
K3D_CONFIG=k8s/local/k3d-cluster.yaml
KUSTOMIZE_DIR=k8s/base
LOCUST_CONFIG=tests/perf/locust.local.conf
LOCUST_HOST?=http://localhost:8000
LOCUST_USERS?=10
LOCUST_SPAWN_RATE?=2
LOCUST_RUN_TIME?=1m
TMP_DIR=.tmp
API_PORT_FORWARD_PID=$(TMP_DIR)/api-port-forward.pid
API_PORT_FORWARD_LOG=$(TMP_DIR)/api-port-forward.log

.DEFAULT_GOAL := help

.PHONY: help setup teardown locust locust-headless

help:
	@echo "make setup            Create the k3d cluster, deploy the stack, run migrations and seed data, and port-forward the API"
	@echo "make teardown         Stop the API port-forward and delete the local k3d cluster"
	@echo "make locust           Start the Locust UI against the local API"
	@echo "make locust-headless  Run Locust headless with LOCUST_USERS, LOCUST_SPAWN_RATE, and LOCUST_RUN_TIME"

setup:
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		echo "Cluster $(CLUSTER) already exists"; \
	else \
		k3d cluster create --config $(K3D_CONFIG); \
	fi
	kubectl wait --for=condition=Ready nodes --all --timeout=180s
	docker build -t $(IMAGE) .
	k3d image import $(IMAGE) -c $(CLUSTER)
	kubectl apply -k $(KUSTOMIZE_DIR)
	kubectl rollout status statefulset/postgres -n $(NS) --timeout=180s
	kubectl rollout status statefulset/rabbitmq -n $(NS) --timeout=180s
	kubectl rollout status statefulset/cache -n $(NS) --timeout=180s
	kubectl delete job migration -n $(NS) --ignore-not-found
	kubectl apply -f $(KUSTOMIZE_DIR)/migration.yml
	kubectl wait --for=condition=complete job/migration -n $(NS) --timeout=180s
	kubectl rollout status deployment/api -n $(NS) --timeout=180s
	kubectl delete job seed -n $(NS) --ignore-not-found
	kubectl apply -f $(KUSTOMIZE_DIR)/seed-job.yml
	kubectl wait --for=condition=complete job/seed -n $(NS) --timeout=180s
	mkdir -p $(TMP_DIR)
	@if [ -f $(API_PORT_FORWARD_PID) ] && kill -0 "$$(cat $(API_PORT_FORWARD_PID))" >/dev/null 2>&1; then \
		echo "API port-forward already running on $(LOCUST_HOST)"; \
	else \
		rm -f $(API_PORT_FORWARD_PID); \
		(kubectl port-forward svc/api 8000:8000 -n $(NS) > $(API_PORT_FORWARD_LOG) 2>&1 & echo $$! > $(API_PORT_FORWARD_PID)); \
		echo "API port-forward started on $(LOCUST_HOST)"; \
	fi

teardown:
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
	@rm -f $(API_PORT_FORWARD_LOG)
	@echo "Deleting k3d cluster $(CLUSTER)..."
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		k3d cluster delete $(CLUSTER); \
		echo "Deleted cluster $(CLUSTER)"; \
	else \
		echo "Cluster $(CLUSTER) does not exist."; \
	fi

locust:
	uv run locust --config $(LOCUST_CONFIG) --host $(LOCUST_HOST)

locust-headless:
	uv run locust --config $(LOCUST_CONFIG) --host $(LOCUST_HOST) --headless -u $(LOCUST_USERS) -r $(LOCUST_SPAWN_RATE) -t $(LOCUST_RUN_TIME)
