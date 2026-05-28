# ADR 0007: EC2 Single-Box Deployment And Registry Strategy

## Status

Accepted, amended

## Context

The project now has three related execution needs:

1. a lightweight CI workflow for validation and unit tests
2. an environment where the service can stay deployed between runs
3. a path to run manual or post-deploy E2E and performance tests against that deployed environment

We considered a few deployment and execution models:

- running the full stack only inside GitHub-hosted workflow jobs with Docker Compose
- using GitHub service containers as the deployment environment
- deploying to one persistent EC2 instance and reusing it across workflows
- moving immediately to a more AWS-native architecture such as ECR, CodeDeploy, or managed service-heavy infrastructure

The key constraint is that we want a real, reusable environment for demonstrations, E2E validation, performance testing, and report hosting without committing to a large AWS surface area too early.

We also want to preserve room for later learning around managed service integration rather than forcing the entire architecture into that path immediately.

## Decision

We will use a single EC2 instance as the first deployed environment for this project.

Specifically:

1. The application stack will run on one EC2 instance.
2. GitHub Actions will remain the orchestration layer for build, deployment, and test workflows.
3. The deployment path will use a container registry rather than `git pull` on the server.
4. GitHub Container Registry (GHCR) will be the first registry choice.
5. The EC2 host will pull published images from GHCR.
6. E2E and performance workflows should target the deployed environment rather than always bootstrapping a fresh stack inside the workflow runner.
7. GitHub service containers and workflow-local Docker Compose remain valid for isolated CI validation, but they are not the deployment platform for the persistent environment.
8. Kubernetes will be the deployment model for the hosted test environment.

## Why GHCR First

We considered both Amazon ECR and GitHub Container Registry.

GHCR is the preferred first step because:

- source control already lives on GitHub
- workflows already run in GitHub Actions
- GHCR keeps source, CI, and image publishing on one platform
- it avoids introducing extra AWS registry setup before the deployment path itself is stable

This does not rule out ECR later. It only means GHCR is the lower-friction first registry for this phase.

## Why Not GitHub Service Containers

GitHub service containers are useful for workflow-scoped dependencies such as databases, caches, or brokers that exist only for the lifetime of one job.

They are not a persistent deployed environment because:

- they are tied to a single workflow run
- they are destroyed when the job ends
- later workflows cannot reuse them as a stable target

For this project, that makes them useful for isolated CI validation, but not for the long-lived environment that E2E and performance workflows should hit.

## Deployment Model

The expected deployment flow is:

1. GitHub Actions builds the application image
2. GitHub Actions pushes the image to GHCR
3. GitHub Actions connects to the EC2 host
4. the EC2 host updates the local repository checkout
5. the deployment workflow writes runtime-only Kubernetes secret material on the host
6. `kubectl apply -k k8s/overlays/ec2` deploys the stack to k3s
7. migration and seed jobs run in Kubernetes
8. health checks confirm the service is back up
9. separate workflows run E2E or performance tests against the deployed Kubernetes environment

This keeps deployment and test execution separate while still allowing GitHub Actions to coordinate both.

## Amendment: EC2 Runs k3s Instead Of Docker Compose

The initial single-box direction was proven with Docker Compose, but the project moved to k3s on EC2 for the hosted test environment.

This change better matches the project goals because:

- Kubernetes manifests were already part of the project.
- Local development already uses k3d and kustomize overlays.
- The hosted environment now exercises the same deployment model as local Kubernetes.
- Deployment behavior, migration jobs, seed jobs, service readiness, and port-forwarding are closer to the system the tests are meant to validate.
- The project can demonstrate Kubernetes-oriented test infrastructure without jumping to a full managed cloud platform.

The EC2 instance is still intentionally single-box. The change is from Docker Compose orchestration to lightweight Kubernetes orchestration, not from a simple environment to a large production cloud setup.

## Scope Of The Single-Box Environment

The first EC2 environment may include:

- API service
- Postgres
- RabbitMQ
- Redis or Valkey
- background consumers
- migration and seed jobs

This is intentionally a pragmatic baseline, not the final cloud architecture.

## Tradeoffs

### Positive

- Lower cost than a managed-service-heavy AWS setup.
- Much simpler to bring up and tear down when not in use.
- Easy to understand operationally during the first deployment phase.
- Good fit for demos, portfolio review, and manual E2E/performance runs.
- Preserves GitHub Actions as the single orchestration surface.

### Negative

- Less initial exposure to AWS managed-service wiring such as RDS or Amazon MQ.
- Tighter resource sharing because the application, infrastructure, and report storage live on one host.
- Lower fidelity to a production-style multi-service cloud deployment.
- Heavier performance runs may be constrained by sharing a single box with all dependencies.
- Some Kubernetes operations still require host preparation, such as kubeconfig access, image pull secrets, and runtime secret files.

## Learning Strategy

Using one EC2 host does not close off deeper AWS infrastructure learning.

Instead, it defines a baseline that can later evolve deliberately.

Likely future upgrades, if useful, are:

1. move Postgres to RDS
2. move RabbitMQ to Amazon MQ
3. move cache to ElastiCache if needed
4. move the registry from GHCR to ECR if tighter AWS integration becomes valuable

That phased approach keeps the initial deployment tractable while still leaving room for managed-service learning later.

## Consequences

- Deployment workflows should now be designed around image publication and kustomize-based Kubernetes deployment.
- E2E and performance workflows should target the EC2 k3s environment through controlled tunnels or exposed service endpoints.
- Reports are currently published to GitHub Pages from GitHub Actions.
- Docker Compose remains useful for local or historical context, but it is no longer the primary hosted deployment model.

## Follow-Up

- Keep the GHCR build-and-push workflow stable.
- Keep the EC2 k3s deployment workflow stable.
- Keep E2E and performance workflows targeting the deployed Kubernetes environment.
- Keep k3s host setup documented enough that the environment can be recreated.
