# ADR 0007: EC2 Single-Box Deployment And Registry Strategy

## Status

Accepted

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

1. The application stack will run on one EC2 instance using Docker Compose.
2. GitHub Actions will remain the orchestration layer for build, deployment, and test workflows.
3. The deployment path will use a container registry rather than `git pull` on the server.
4. GitHub Container Registry (GHCR) will be the first registry choice.
5. The EC2 host will pull published images from GHCR and restart the stack with Docker Compose.
6. E2E and performance workflows should target the deployed environment rather than always bootstrapping a fresh stack inside the workflow runner.
7. GitHub service containers and workflow-local Docker Compose remain valid for isolated CI validation, but they are not the deployment platform for the persistent environment.
8. MinIO may be hosted on the same EC2 instance as part of the deployed stack for report storage.

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
4. the EC2 host pulls the new image
5. Docker Compose restarts the stack
6. health checks confirm the service is back up
7. separate workflows can then run E2E or performance tests against the deployed URL

This keeps deployment and test execution separate while still allowing GitHub Actions to coordinate both.

## Scope Of The Single-Box Environment

The first EC2 environment may include:

- API service
- Postgres
- RabbitMQ
- Redis or Valkey
- background consumers
- MinIO for report storage

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

- Deployment workflows should now be designed around image publication and remote host restart, not in-cluster job execution.
- E2E and performance workflows should be able to target a stable deployed base URL.
- Report publishing can later point to MinIO on the same EC2 box without changing the overall orchestration model.
- Docker Compose files may need a deployment-oriented variant separate from local development if host-specific concerns grow.

## Follow-Up

- Add a GitHub Actions workflow that builds and pushes images to GHCR.
- Add a deployment workflow that updates the EC2 host and restarts the stack.
- Define Docker Compose image references for registry-pulled deployment.
- Add GitHub secrets needed for EC2 access and registry authentication.
- Update E2E and performance workflows to target the deployed environment instead of assuming a workflow-local stack.
- Decide whether MinIO belongs in the deployed Compose stack immediately or after the base deploy flow is stable.
