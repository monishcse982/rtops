# R-Tops: Real-Time Order Processing Test Platform

R-Tops is a FastAPI-based order processing service used as a realistic system under test for quality engineering work. The backend is event-driven and uses PostgreSQL, RabbitMQ, Redis, Docker, Kubernetes, Locust, Pytest, Allure, and GitHub Actions.

The project is intentionally testing-focused. The application gives the automation suite something real to validate: API behavior, order lifecycle workflows, event/outbox behavior, database-backed state, Kubernetes deployment, and baseline performance under load.

## Project Focus

This repository is being developed as a portfolio-quality SDET / quality engineering project. The main focus areas are:

- API and end-to-end test automation
- Data validation around orders, products, and outbox events
- Event-driven workflow validation
- Locust performance tests with user journeys and repeatable load shapes
- Allure and Locust report publishing through GitHub Pages
- CI/CD workflows for validation, image publishing, deployment, and remote test execution
- Local Kubernetes and single-node EC2 Kubernetes deployment

## System Under Test

The backend models a simple commerce/order platform:

- Product listing, lookup, filtering, and sorting
- Order creation with single and multiple line items
- Order state transitions through payment, readiness, shipping, and delivery
- Outbox-backed event publishing
- RabbitMQ consumers for event-driven order lifecycle processing
- PostgreSQL persistence
- Redis-backed cache support

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy and Alembic
- PostgreSQL
- RabbitMQ
- Redis
- Pytest
- Allure
- Locust
- Docker and Docker Compose
- Kubernetes with kustomize overlays
- k3d for local Kubernetes
- k3s on EC2 for the hosted test environment
- GHCR for container images
- GitHub Actions and GitHub Pages

## Repository Layout

```text
app/                 FastAPI app, models, routers, services, event consumers
alembic/             Database migrations
tests/unit/          Unit and integration-style tests around core behavior
tests/e2e/           API E2E tests with Allure reporting
tests/perf/          Locust performance users, load shape, and config
k8s/base/            Shared Kubernetes manifests
k8s/overlays/local/  Local k3d deployment overlay
k8s/overlays/ec2/    EC2 k3s deployment overlay using GHCR images
scripts/             Test/report helper scripts
docs/adr/            Architecture decision records
.github/workflows/   CI, image, deploy, E2E, and performance workflows
```

## Local Setup

Install dependencies with `uv`:

```sh
uv sync --frozen --all-groups
```

Run local checks:

```sh
uv run pre-commit run --all-files
uv run pytest tests/unit -q
```

## Local Kubernetes

The main local environment uses k3d and the Kubernetes manifests in `k8s/base` plus `k8s/overlays/local`.

Bring up the local stack:

```sh
make up
```

This creates the k3d cluster, builds/imports the API image, deploys PostgreSQL, RabbitMQ, Redis, the API, runs migrations, seeds data, and starts local port-forwards.

Run E2E tests against the local Kubernetes deployment:

```sh
make k8s-e2e
```

Run Locust locally:

```sh
make locust
```

Run Locust headless:

```sh
make locust-headless
```

Tear down the local cluster:

```sh
make down
```

Clean generated Python/test/report artifacts:

```sh
make clean
```

## GitHub Actions

Current workflows:

- `ci.yml`: installs dependencies, runs pre-commit, and runs unit tests.
- `build-and-push.yml`: builds the API image and pushes it to GHCR.
- `deploy-k8s.yml`: deploys the Kubernetes stack to the EC2 k3s environment.
- `e2e-k8s.yml`: runs E2E tests against the EC2 Kubernetes environment and publishes the Allure report.
- `perf-k8s.yml`: runs a Locust smoke baseline against the EC2 Kubernetes environment and publishes the Locust report.
- `deploy.yml`, `e2e.yml`, and `perf.yml`: earlier non-Kubernetes workflow variants retained while the project transitions toward the Kubernetes path.

## Published Reports

Reports are published to GitHub Pages.

- E2E latest report: `https://monishcse982.github.io/rtops/e2e/latest/`
- Performance latest report: `https://monishcse982.github.io/rtops/perf/latest/`

Each workflow run also publishes a run-specific report URL in the GitHub Actions job summary.

## Performance Testing Notes

Locust scenarios are organized around API-level user behavior:

- product browsing
- order actions
- order journey flows

The normal entrypoint is:

```sh
uv run locust --config tests/perf/locust.local.conf --host http://localhost:8000
```

The EC2 Kubernetes performance workflow uses a small explicit smoke shape and publishes the baseline report even when the service records request failures. Those failures are preserved in the Locust report. This keeps the workflow useful for observing baseline behavior without hiding the system's current limits.

## Documentation

- [Project Overview](docs/project_overview.md)
- [ADR 0001: Functional Testing Approach](docs/adr/0001-functional-testing-approach.md)
- [ADR 0002: Performance Testing Approach](docs/adr/0002-performance-testing-approach.md)
- [ADR 0003: Test Data and Environment Strategy](docs/adr/0003-test-data-and-environment-strategy.md)
- [ADR 0004: Performance Test Execution Strategy](docs/adr/0004-performance-test-execution-strategy.md)
- [ADR 0005: Test Reporting Strategy](docs/adr/0005-test-reporting-strategy.md)
- [ADR 0006: Report Publishing and Health Dashboard Strategy](docs/adr/0006-report-publishing-and-health-dashboard-strategy.md)
- [ADR 0007: EC2 Single Box Deployment and Registry Strategy](docs/adr/0007-ec2-single-box-deployment-and-registry-strategy.md)

## Attribution

The backend application in this repository was adapted from the open-source backend project [sebadp/FastAPI-RabbitMQ-Event-driven-design](https://github.com/sebadp/FastAPI-RabbitMQ-Event-driven-design) by Sebastián Dávila.

I updated the backend to run on current dependencies and built the testing, performance, reporting, and test-infrastructure work around it.

Original backend credit:

- Sebastián Dávila
- Source backend project: [FastAPI-RabbitMQ-Event-driven-design](https://github.com/sebadp/FastAPI-RabbitMQ-Event-driven-design)
