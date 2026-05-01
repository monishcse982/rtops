IMAGE=rtops-api:dev
CLUSTER=rtops
NS=rtops
KUSTOMIZE_DIR=k8s/base
K3D_CONFIG=k8s/local/k3d-cluster.yaml

.PHONY: build import deploy migrate seed status logs port-forward port-forward-api port-forward-rabbitmq port-forward-postgres port-forward-cache port-forward-all stop-port-forward cluster-up wait-cluster wait-infra wait-api down cluster-down reset reset-all all

build:
	docker build -t $(IMAGE) .

import:
	k3d image import $(IMAGE) -c $(CLUSTER)

cluster-up:
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		echo "Cluster $(CLUSTER) already exists"; \
	else \
		k3d cluster create --config $(K3D_CONFIG); \
	fi

wait-infra:
	kubectl rollout status statefulset/postgres -n $(NS) --timeout=180s
	kubectl rollout status statefulset/rabbitmq -n $(NS) --timeout=180s
	kubectl rollout status statefulset/cache -n $(NS) --timeout=180s

wait-api:
	kubectl rollout status deployment/api -n $(NS) --timeout=180s

wait-cluster:
	kubectl wait --for=condition=Ready nodes --all --timeout=180s

down:
	@if kubectl get namespace $(NS) >/dev/null 2>&1; then \
		kubectl delete -k $(KUSTOMIZE_DIR) --ignore-not-found; \
	else \
		echo "Namespace $(NS) does not exist. Nothing to delete."; \
	fi

cluster-down:
	@if k3d cluster list | awk 'NR > 1 {print $$1}' | grep -qx "$(CLUSTER)"; then \
		k3d cluster delete $(CLUSTER); \
	else \
		echo "Cluster $(CLUSTER) does not exist. Nothing to delete."; \
	fi

deploy:
	kubectl apply -k $(KUSTOMIZE_DIR)

migrate:
	kubectl delete job migration -n $(NS) --ignore-not-found
	kubectl apply -f k8s/base/migration.yml
	kubectl wait --for=condition=complete job/migration -n $(NS) --timeout=180s
	kubectl logs job/migration -n $(NS)

seed:
	kubectl delete job seed -n $(NS) --ignore-not-found
	kubectl apply -f $(KUSTOMIZE_DIR)/seed-job.yml
	kubectl wait --for=condition=complete job/seed -n $(NS) --timeout=180s
	kubectl logs job/seed -n $(NS)

status:
	kubectl get pods,svc,pvc,jobs -n $(NS)

logs:
	kubectl logs deployment/api -n $(NS)

port-forward:
	@echo "API is not port-forwarded by default. Run it locally with: uv run uvicorn app.main:app --reload"

port-forward-api:
	kubectl port-forward svc/api 8000:8000 -n $(NS)

port-forward-rabbitmq:
	kubectl port-forward svc/rabbitmq 5672:5672 15672:15672 -n $(NS)

port-forward-postgres:
	kubectl port-forward svc/postgres 5432:5432 -n $(NS)

port-forward-cache:
	kubectl port-forward svc/cache 6379:6379 -n $(NS)

port-forward-all:
	mkdir -p .tmp
	(kubectl port-forward svc/rabbitmq 5672:5672 15672:15672 -n $(NS) > .tmp/rabbitmq-port-forward.log 2>&1 & echo $$! > .tmp/rabbitmq-port-forward.pid)
	(kubectl port-forward svc/postgres 5432:5432 -n $(NS) > .tmp/postgres-port-forward.log 2>&1 & echo $$! > .tmp/postgres-port-forward.pid)
	(kubectl port-forward svc/cache 6379:6379 -n $(NS) > .tmp/cache-port-forward.log 2>&1 & echo $$! > .tmp/cache-port-forward.pid)
	@echo "Port forwards started:"
	@echo "  RabbitMQ UI:   http://localhost:15672"
	@echo "  RabbitMQ AMQP: localhost:5672"
	@echo "  Postgres:   localhost:5432"
	@echo "  Valkey:     localhost:6379"
	@echo "Logs and PIDs are in .tmp/"

stop-port-forward:
	@if ls .tmp/*-port-forward.pid >/dev/null 2>&1; then \
		for pidfile in .tmp/*-port-forward.pid; do \
			pid=$$(cat $$pidfile); \
			if kill -0 $$pid >/dev/null 2>&1; then \
				kill $$pid; \
				echo "Stopped port-forward process $$pid"; \
			fi; \
			rm -f $$pidfile; \
		done; \
	else \
		echo "No port-forward PID files found."; \
	fi

all: stop-port-forward cluster-up wait-cluster build import deploy wait-infra migrate wait-api seed status port-forward-all

reset: down all

reset-all: stop-port-forward cluster-down cluster-up wait-cluster build import deploy wait-infra migrate wait-api seed status port-forward-all
