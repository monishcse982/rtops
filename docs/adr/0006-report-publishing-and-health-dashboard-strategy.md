# ADR 0006: Report Publishing And Health Dashboard Strategy

## Status

Accepted, amended

## Context

The repository already generates two kinds of test artifacts:

- functional test evidence and Allure outputs
- performance test artifacts such as Locust HTML, CSV, and JSON outputs

We also already have a local Kubernetes-based development workflow and a growing need to make test evidence easier to retain and review beyond the machine that generated it.

At the same time, we want a lightweight runtime dashboard for service and infrastructure visibility, but we do not want to mix that concern into test artifact browsing or build an alerting system yet.

We discussed three related needs:

1. a repeatable way to trigger functional and performance test runs
2. a way to publish generated reports to S3-compatible storage
3. a basic health dashboard for runtime visibility

## Initial Decision

We initially decided to treat report publishing and runtime health monitoring as related but separate concerns.

The initial direction was:

1. Reports will be published to S3-compatible object storage.
2. MinIO will be used for local development to emulate S3.
3. Functional test reports are mandatory and must always be publishable.
4. Performance test reports should use the same publishing path when generated.
5. A small HTTP report index should expose published reports and recent run metadata.
6. Runtime health dashboards should remain separate from report browsing.
7. GitHub Actions should be the primary orchestration layer for combining test execution, report publication, and artifact retention.
8. The cluster should remain the system under test, not the default home for running the full functional and performance suites.

## Initial Report Storage Strategy

Local development was expected to use MinIO as the S3-compatible report store.

The report storage model should support:

- timestamped historical runs
- stable latest pointers
- lightweight metadata per run

A representative object layout is:

```text
test-reports/
  functional/
    <run-id>/
      ...
    latest/
      ...
  performance/
    <run-id>/
      ...
    latest/
      ...
```

Each published run should include metadata such as:

- report type
- timestamp
- environment
- branch and commit when available
- report entrypoint

## Initial Report Publishing Flow

Reports were expected to be published after each relevant test run rather than requiring a separate manual archival workflow.

The expected path is:

1. run functional or performance tests
2. generate artifacts locally or in GitHub Actions
3. publish artifacts to S3-compatible storage
4. update latest pointers or equivalent metadata
5. expose report links through the report HTTP layer

Functional report publishing is the baseline requirement. Performance reports should follow the same shape so the system remains consistent.

## Initial HTTP Access Strategy

We decided not to rely on `python -m http.server` as the intended report-serving solution.

It is acceptable for one-off debugging, but it is not the preferred report experience because it does not provide:

- a useful landing page
- latest-report discovery
- run metadata
- a stable browsing experience

The preferred direction is a small Python HTTP app, such as a minimal FastAPI-based report index, that:

- shows latest functional and performance reports
- links to published artifacts in object storage
- optionally lists recent historical runs
- keeps the UI intentionally simple

## Runtime Health Dashboard Strategy

Runtime health monitoring should be a separate surface from test report browsing.

The initial dashboard should focus on visibility only, including:

- API health
- infrastructure dependency health
- Kubernetes readiness and restart signals
- basic service-level status

Alerting is explicitly out of scope for this phase.

This keeps the first dashboard useful without prematurely committing to operational paging or incident workflows.

## Execution Model

## Local Development

The local `Makefile` remains a convenience entrypoint and orchestration layer.

Its role is to help developers trigger:

- functional test runs
- performance test runs
- local report publishing
- local report UI access
- local dashboard access

The `Makefile` should call shared scripts rather than owning all execution logic directly.

## GitHub Actions

GitHub Actions should be the primary home for combined validation and reporting workflows.

In practice:

- functional tests should run from Actions
- performance tests should run from Actions, preferably as explicit or manual workflows rather than every PR
- report artifacts should be retained and published from Actions

The cluster remains the system under test, not the place where the full functional and performance suites primarily live.

## Learning From The Kubernetes Job Attempt

We explored running the full functional and performance suites as Kubernetes Jobs after cluster setup completed.

That experiment was useful, but it also made the tradeoffs obvious:

- the app image and the test-runner image started to blur together
- test execution became coupled to cluster-specific runtime details
- report publishing configuration had to be pushed into Kubernetes config and secrets
- reruns and debugging became more operationally heavy than the value justified

The experiment confirmed that the code, cluster, and tests can each work independently, but that Kubernetes Jobs are not the best default composition layer for full-suite orchestration in this project.

The better home for that orchestration is GitHub Actions, where sequencing, artifact retention, and report publication are more natural.

This is not a reversal of the underlying reporting goals. It is a refinement of where the orchestration should live.

## Amendment: GitHub Pages Before S3/MinIO

After implementing the first report-publishing path, we chose GitHub Pages as the current public report surface instead of S3/MinIO.

The updated near-term decision is:

1. E2E Allure HTML reports are published to GitHub Pages.
2. Locust HTML reports are published to GitHub Pages.
3. Each run gets a run-specific URL.
4. Each report type gets a stable `latest` URL.
5. GitHub Actions job summaries print direct report links.
6. S3/MinIO remains a valid future option, but it is no longer required for the current portfolio/demo flow.

This keeps the report publishing path simpler and more visible while the project is still proving its quality automation story.

Current report URLs:

- E2E latest report: `https://monishcse982.github.io/rtops/e2e/latest/`
- Performance latest report: `https://monishcse982.github.io/rtops/perf/latest/`

Representative sample reports:

- Perf Test Report: `https://monishcse982.github.io/rtops/perf/26568507164/local/20260528-101211/report.html`
- E2E Test Report: `https://monishcse982.github.io/rtops/e2e/26568280652/`

## Script-First Design

Core execution logic should live in reusable scripts or small utilities so it can be invoked from:

- local `Makefile` targets
- GitHub Actions workflows
- later CI or automation paths if needed

This avoids duplicating the same execution logic across local and CI workflows.

## Separation Of Concerns

This ADR intentionally keeps the following concerns separate:

- test execution
- report publishing
- report browsing
- runtime health monitoring

They are connected in workflow but should not be collapsed into one component or one UI prematurely.

## Consequences

### Positive

- Test artifacts become easier to retain and review over time.
- Local development can use a realistic S3-compatible flow without requiring AWS.
- GitHub-hosted code and GitHub-hosted workflows stay aligned in one platform.
- Report browsing and runtime health can evolve independently.
- The project avoids over-coupling test execution to Kubernetes runtime details.

### Tradeoffs

- The solution introduces more moving parts than local-only file output.
- Report metadata and latest-pointer handling need explicit implementation.
- The dashboard and report UI are intentionally separate, which means more than one surface to maintain.
- Full post-deploy validation inside the cluster is deferred; if needed later, it should likely be a small smoke layer rather than the full suites.

## Current Scope

At the time of this ADR:

- functional and performance reports exist locally
- timestamped performance report output is in place
- E2E and performance reports are published to GitHub Pages from GitHub Actions
- local Kubernetes-based development is already part of the project workflow
- no health dashboard exists yet

## Follow-Up

- Keep GitHub Pages report publishing stable before adding another storage backend.
- Revisit MinIO/S3 only if report retention, metadata, or access-control needs outgrow GitHub Pages.
- Add a first health dashboard focused on service and infrastructure visibility.
- If post-deploy validation is later needed, define it separately as a lightweight smoke strategy instead of reusing the full functional or performance suites.
